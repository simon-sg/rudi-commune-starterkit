"""JDD « Marchés publics (DECP) » — source remplacée le 2026-11-10 (v3 Axe 4).

**Changement de source, décision actée avec l'utilisateur.** L'ancienne source
(``decp-2022-marches-valides`` sur ``data.economie.gouv.fr``) est touchée par un trou de
remontée AIFE signalé le 18/11/2025, jamais confirmé résolu officiellement. Remplacée par
le jeu consolidé indépendant de Colin Maudry sur data.gouv.fr (dataset
``608c055b35eb4e6ee20eb325``, « Données essentielles de la commande publique
consolidées, format tabulaire ») : mise à jour quasi quotidienne, Licence Ouverte 2.0
confirmée (``license: lov2``), contact réel disponible via ``contact_points``
(``colin@colmo.tech``, rôle « creator », organisation Colmo).

**Dépendre d'un consolidateur indépendant pour un JDD public — réserve assumée et
documentée, pas un abandon du module.** Le producteur RUDI reste « Ministère de
l'Économie et des Finances » (responsable public des données sources, même
consolidées par un tiers) ; si la source se figeait, un avertissement CLI
(``_avertir_si_source_figee``) le signale sans bloquer la publication.

**Changement de modèle de média** : pas de filtre serveur avec cette source (contrairement
à l'export ODS précédent) → téléchargement intégral du CSV.gz (``decp.csv.gz``, ~435 Mo)
puis filtrage local en flux (``filtrer_csv(..., prefixe=True)``, jamais
``lire_csv_filtre()`` qui matérialiserait tout le fichier en mémoire) sur ``acheteur_id``
(SIRET, 14 chiffres) préfixé par le SIREN (9 chiffres) de la commune — jamais de
conversion en ``int`` (un SIRET peut commencer par ``0``). Conséquence : plus de
pré-contrôle ``total_count`` gratuit (coût réseau plus élevé pour une commune sans
marché) — régression de coût assumée, non optimisée dans cette v3.

**Cache partagé, pas par commune** (``DOSSIER_CACHE_DECP``, à la racine du projet, pas
sous ``dossier_sortie``) : 435 Mo par commune serait inacceptable pour un run
multi-communes. TTL court (1 jour, pas les 30 jours par défaut du toolkit) — la source
est mise à jour quasi quotidiennement.

Périmètre v1 inchangé : seuls les marchés (pas les concessions, dataset distinct, hors
socle).

**Axe 4 (v4, 2026-11-11) — glossaire.** Vérifié en direct (``schema.json`` publié par le
dataset, labels déjà clairs pour la quasi-totalité des colonnes) : le seul code
réellement opaque est ``codeCPV`` (nomenclature européenne), glossé via
``construire_description_structuree(glossaire=...)``.
"""

from __future__ import annotations

import csv
import os
from datetime import datetime, timezone

import requests

from rudi_harvest_toolkit.commune import resoudre_siren_commune
from rudi_harvest_toolkit.contacts import extraire_contacts_datagouv
from rudi_harvest_toolkit.datagouv import get_dataset_metadata, selectionner_ressource
from rudi_harvest_toolkit.description import construire_description_structuree
from rudi_harvest_toolkit.download_cache import telecharger
from rudi_harvest_toolkit.http import session
from rudi_harvest_toolkit.pivot import (
    LICENCES_DATAGOUV_CONNUES,
    construire_licence,
    construire_rudi_metadata,
    media_filtre,
)
from rudi_harvest_toolkit.tabular import filtrer_csv

from .. import licences, organisations
from ..resultat import ResultatConnecteur, StatutConnecteur
from ._commun import contacts_pour_producer, geography_pour_commune, local_id_jdd

CLE = organisations.MARCHES_PUBLICS
THEME = "economy"
TITRE = "Marchés publics"
SYNOPSIS_PATRON = "Marchés publics notifiés par la commune de {commune} ({code_insee})"
DESCRIPTION_PATRON = (
    "Données essentielles de la commande publique (DECP) notifiées par la commune de "
    "{commune} ({code_insee}) en tant qu'acheteur public. Sourcées depuis le jeu "
    "consolidé indépendant de Colin Maudry (data.gouv.fr), filtré localement sur le "
    "SIRET de la commune, pas un export serveur. Ne couvre que les marchés (pas les "
    "concessions). Réserve : source tierce consolidée, pas directement l'AIFE/DAE ; un "
    "avertissement est émis si elle venait à se figer."
)
FREQUENCE_MAJ = "quasi quotidienne"

_DATASET_ID = "608c055b35eb4e6ee20eb325"
_COLONNE_ACHETEUR = "acheteur_id"
DOSSIER_CACHE_DECP = ".cache_decp"
_SEUIL_FIGEE_JOURS = 15

_GLOSSAIRE_CODES = {
    "codeCPV": (
        "Code CPV (Common Procurement Vocabulary, nomenclature européenne des "
        "achats publics), code hiérarchique à 8 chiffres + 1 chiffre de contrôle ; "
        "les 2 premiers chiffres indiquent la division (ex. 45 = travaux de "
        "construction). Table de référence complète : simap.ted.europa.eu."
    ),
}


def _avertir_si_source_figee(last_modified: str | None) -> None:
    if not last_modified:
        return
    try:
        date = datetime.fromisoformat(str(last_modified).replace("Z", "+00:00"))
    except ValueError:
        return
    if date.tzinfo is None:
        date = date.replace(tzinfo=timezone.utc)
    age_jours = (datetime.now(timezone.utc) - date).days
    if age_jours > _SEUIL_FIGEE_JOURS:
        print(
            f"[marches_publics] AVERTISSEMENT : source DECP (Colin Maudry) figée depuis "
            f"{age_jours} jours."
        )


def _description_enrichie(commune: dict, code_insee: str) -> str:
    return construire_description_structuree(
        quoi=(
            f"Données essentielles de la commande publique (DECP) notifiées par "
            f"{commune['nom']} ({code_insee}) en tant qu'acheteur public. Marchés "
            f"seulement (les concessions sont un dataset distinct, hors socle)."
        ),
        comment_construit=(
            "Extraites du jeu consolidé indépendant de Colin Maudry (data.gouv.fr), "
            "téléchargé intégralement puis filtré localement sur le SIRET de la "
            "commune (pas un filtre serveur). Dépendre d'un consolidateur "
            "indépendant pour ce JDD public est une réserve assumée, pas un abandon "
            "du module : un avertissement est émis si la source venait à se figer."
        ),
        structure_variables=[
            "Identification du marché (uid, id, nature, objet)",
            "Acheteur et titulaire(s) (acheteur_id, titulaire_id)",
            "Montant, durée et procédure de passation",
            "Dates de notification et modifications éventuelles",
        ],
        frequence_maj=FREQUENCE_MAJ,
        source_label="Données essentielles de la commande publique (Colin Maudry)",
        url_source=f"https://www.data.gouv.fr/datasets/{_DATASET_ID}/",
        glossaire=_GLOSSAIRE_CODES,
        limites=["Périmètre : marchés seulement (pas les concessions, dataset distinct, hors socle)."],
    )


def moissonner(
    code_insee: str,
    commune: dict,
    *,
    dossier_sortie: str,
    mode_producer: str = "source",
    contact_email_commune: str | None = None,
    session_http=None,
    description_commune: dict | None = None,
) -> ResultatConnecteur:
    session_http = session_http or session

    try:
        siren = resoudre_siren_commune(code_insee, session_http=session_http)
    except Exception as e:  # noqa: BLE001
        return ResultatConnecteur(StatutConnecteur.ECHEC, message=str(e))

    try:
        metadata = get_dataset_metadata(_DATASET_ID, session_http=session_http)
        ressource = selectionner_ressource(metadata, motif_nom=r"^decp\.csv\.gz$")
        chemin_cache = telecharger(
            ressource["url"], dossier=DOSSIER_CACHE_DECP, ttl_jours=1,
            session_http=session_http,
        )
    except requests.exceptions.HTTPError as e:
        # Backlog, fragilité #2 (2026-11-13) : le dataset data.gouv.fr est maintenu
        # par un contributeur externe (Colin Maudry), mis à jour quasi quotidiennement
        # — son identifiant peut un jour devenir invalide sans rapport avec la commune
        # interrogée. Message explicite plutôt que le texte brut de `requests`, pas
        # clair pour un agent municipal non technique (persona de l'exécutable packagé).
        statut = e.response.status_code if e.response is not None else None
        if statut == 404:
            return ResultatConnecteur(
                StatutConnecteur.ECHEC,
                message=(
                    f"Jeu de données DECP introuvable sur data.gouv.fr (dataset "
                    f"{_DATASET_ID!r} — source tierce maintenue par Colin Maudry, "
                    "susceptible de changer d'identifiant sans préavis). Vérifier "
                    f"https://www.data.gouv.fr/datasets/{_DATASET_ID}/ et mettre à "
                    "jour _DATASET_ID dans marches_publics.py si l'identifiant a changé."
                ),
            )
        return ResultatConnecteur(StatutConnecteur.ECHEC, message=str(e))
    except Exception as e:  # noqa: BLE001
        return ResultatConnecteur(StatutConnecteur.ECHEC, message=str(e))

    _avertir_si_source_figee(ressource.get("last_modified"))

    local_id = local_id_jdd(CLE, code_insee)
    nom_fichier = f"marches_publics_{code_insee}.csv"
    chemin = os.path.join(dossier_sortie, nom_fichier)
    os.makedirs(dossier_sortie, exist_ok=True)

    nb_lignes = 0
    try:
        with open(chemin, "w", encoding="utf-8", newline="") as f:
            writer = None
            for ligne in filtrer_csv(chemin_cache, _COLONNE_ACHETEUR, siren, prefixe=True):
                if writer is None:
                    writer = csv.DictWriter(f, fieldnames=list(ligne.keys()), delimiter=";")
                    writer.writeheader()
                writer.writerow(ligne)
                nb_lignes += 1
    except Exception as e:  # noqa: BLE001
        return ResultatConnecteur(StatutConnecteur.ECHEC, message=str(e))

    if not nb_lignes:
        try:
            os.remove(chemin)
        except OSError:
            pass
        return ResultatConnecteur(StatutConnecteur.VIDE)

    try:
        licence_dynamique = construire_licence(
            metadata.get("license"), metadata.get("page"), LICENCES_DATAGOUV_CONNUES,
        )
        licence = licences.licence_pour_jdd(CLE, licence_dynamique=licence_dynamique)
    except licences.LicenceInconnueError as e:
        return ResultatConnecteur(StatutConnecteur.ECHEC, message=str(e))

    producer = organisations.resoudre_producer(
        CLE, mode_producer, commune, description_commune=description_commune,
    )
    contacts = contacts_pour_producer(
        CLE, producer, commune, email_commune=contact_email_commune,
        contacts_dynamiques=extraire_contacts_datagouv(metadata),
    )

    media = media_filtre(
        local_id, nom_fichier, commune["nom"],
        caption=f"Marchés publics notifiés par la commune - {commune['nom']} (CSV)",
    )

    url_dataset = metadata.get("page") or f"https://www.data.gouv.fr/datasets/{_DATASET_ID}/"

    rudi_metadata = construire_rudi_metadata(
        local_id=local_id,
        titre=f"{TITRE} - {commune['nom']} ({code_insee})",
        synopsis=SYNOPSIS_PATRON.format(commune=commune["nom"], code_insee=code_insee)[:150],
        description=_description_enrichie(commune, code_insee),
        theme=THEME,
        keywords=[
            "marchés publics", "DECP", "commande publique", "achat public",
            commune["nom"],
        ],
        producer=producer,
        url_source=url_dataset,
        url_fiche=url_dataset,
        medias=[media],
        contacts_source=contacts,
        geography=geography_pour_commune(commune),
        licence=licence,
        date_source=ressource.get("last_modified"),
    )

    return ResultatConnecteur(
        StatutConnecteur.PUBLIABLE, rudi_metadata=rudi_metadata, fichiers_filtres=[chemin],
    )


__all__ = ["CLE", "DESCRIPTION_PATRON", "FREQUENCE_MAJ", "SYNOPSIS_PATRON", "THEME", "TITRE", "moissonner"]
