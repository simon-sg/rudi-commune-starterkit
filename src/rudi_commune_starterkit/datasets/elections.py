"""JDD « Résultats élections » — municipales 2026, 1er tour, fichier déjà agrégé par commune.

Scrutin choisi le 2026-11-07 (le plus récent disponible, le plan laissait le choix exact
« à confirmer en implémentation ») : Ministère de l'Intérieur, dataset data.gouv.fr
« Elections municipales 2026 - Résultats du premier tour », ressource « Résultats -
Communes » (14 Mo, CSV ``;``, **déjà agrégée au niveau commune** — contrairement à
l'hypothèse du plan, ce scrutin précis n'a pas besoin de
``agregation_scrutin.agreger_bureau_vers_commune()`` : une commune = une ligne, le code
``Code commune`` est déjà sur 5 caractères, aucun souci de padding rencontré). Format
« large » confirmé : un bloc de 13 colonnes répété par liste candidate (jusqu'à 13 blocs
dans le fichier national, la plupart vides pour une petite commune) — le passage large →
long est fait ici directement (``_blocs_liste``), ``agregation_scrutin.py`` restant
disponible pour un futur scrutin qui nécessiterait réellement une agrégation bureau→commune.

**Second tour non inclus en v1** (toutes les communes n'en ont pas eu besoin ; une commune
donnée peut ne pas apparaître dans le fichier du 2nd tour) — report v2 explicite, comme
acté avec l'utilisateur sur le multi-scrutins.
"""

from __future__ import annotations

import csv
import os
import re

from rudi_harvest_toolkit.contacts import extraire_contacts_datagouv
from rudi_harvest_toolkit.datagouv import get_dataset_metadata, selectionner_ressource
from rudi_harvest_toolkit.download_cache import telecharger
from rudi_harvest_toolkit.http import session
from rudi_harvest_toolkit.pivot import (
    LICENCES_DATAGOUV_CONNUES,
    construire_licence,
    construire_rudi_metadata,
    media_filtre,
)
from rudi_harvest_toolkit.tabular import lire_csv_filtre

from .. import licences, organisations
from ..resultat import ResultatConnecteur, StatutConnecteur
from ._commun import contacts_pour_producer, geography_pour_commune, local_id_jdd

CLE = organisations.ELECTIONS
THEME = "citizenship"
TITRE = "Résultats élections municipales"
SYNOPSIS_PATRON = "Résultats du 1er tour des municipales 2026 à {commune} ({code_insee})"
DESCRIPTION_PATRON = (
    "Résultats du premier tour des élections municipales 2026 pour la commune de "
    "{commune} ({code_insee}), par liste candidate - inscrits, votants, abstention, "
    "exprimés et voix par liste. Sourcé auprès du Ministère de l'Intérieur. Ne couvre que "
    "le 1er tour ; limité à ce seul scrutin (pas d'historique multi-scrutins en v1)."
)
FREQUENCE_MAJ = "ponctuelle (un scrutin)"

_DATASET_ID = "elections-municipales-2026-resultats-du-premier-tour"
_COLONNE_COMMUNE = "Code commune"
_RE_BLOC = re.compile(r"^Libellé de liste (\d+)$")

_CHAMPS_TOTAUX = (
    "Inscrits", "Votants", "Abstentions", "Exprimés", "Blancs", "Nuls",
)
_CHAMPS_BLOC = (
    "numero_panneau", "libelle_liste", "libelle_abrege", "nuance", "voix",
    "pourcentage_exprimes", "elu", "sieges_conseil_municipal", "sieges_conseil_communautaire",
)
_COLONNES_CSV = (
    ("code_insee", "commune")
    + tuple(f"totaux_{champ}" for champ in _CHAMPS_TOTAUX)
    + _CHAMPS_BLOC
)


def _lignes_csv(resultat_commune: dict) -> list[dict]:
    """Dénormalise le résultat d'une commune en lignes CSV : une ligne par liste
    candidate, totaux de la commune répétés sur chaque ligne (onglet tableau du portail —
    ``application/json`` n'y est pas reconnu)."""
    entete = {"code_insee": resultat_commune["code_insee"], "commune": resultat_commune["commune"]}
    entete.update({f"totaux_{champ}": v for champ, v in resultat_commune["totaux"].items()})
    return [{**entete, **bloc} for bloc in resultat_commune["listes"]]


def _blocs_liste(entetes: list[str], ligne: dict) -> list[dict]:
    blocs = []
    for entete in entetes:
        m = _RE_BLOC.match(entete)
        if not m:
            continue
        i = m.group(1)
        libelle = (ligne.get(f"Libellé de liste {i}") or "").strip()
        if not libelle:
            continue
        blocs.append({
            "numero_panneau": ligne.get(f"Numéro de panneau {i}"),
            "libelle_liste": libelle,
            "libelle_abrege": ligne.get(f"Libellé abrégé de liste {i}"),
            "nuance": ligne.get(f"Nuance liste {i}"),
            "voix": ligne.get(f"Voix {i}"),
            "pourcentage_exprimes": ligne.get(f"% Voix/exprimés {i}"),
            "elu": bool((ligne.get(f"Elu {i}") or "").strip()),
            "sieges_conseil_municipal": ligne.get(f"Sièges au CM {i}"),
            "sieges_conseil_communautaire": ligne.get(f"Sièges au CC {i}"),
        })
    return blocs


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
        metadata = get_dataset_metadata(_DATASET_ID, session_http=session_http)
        ressource = selectionner_ressource(
            # Ancré en début de titre : exclut "Municipales Polynésie française 2026 -
            # Résultats - Communes_..." et "Conseils d'arrondissement..." (même suffixe,
            # titres distincts du même dataset) sans quoi le motif est ambigu.
            metadata, motif_nom=r"^Municipales 2026 - R[ée]sultats - Communes_",
        )
        chemin_cache = telecharger(
            ressource["url"], dossier=os.path.join(dossier_sortie, ".cache_elections"),
            session_http=session_http,
        )
        lignes, entetes = lire_csv_filtre(chemin_cache, _COLONNE_COMMUNE, code_insee)
    except Exception as e:  # noqa: BLE001
        return ResultatConnecteur(StatutConnecteur.ECHEC, message=str(e))

    if not lignes:
        return ResultatConnecteur(StatutConnecteur.VIDE)

    try:
        licence_dynamique = construire_licence(
            metadata.get("license"), metadata.get("page"), LICENCES_DATAGOUV_CONNUES,
        )
        licence = licences.licence_pour_jdd(CLE, licence_dynamique=licence_dynamique)
    except licences.LicenceInconnueError as e:
        return ResultatConnecteur(StatutConnecteur.ECHEC, message=str(e))

    ligne = lignes[0]
    blocs = _blocs_liste(entetes, ligne)

    resultat_commune = {
        "code_insee": code_insee,
        "commune": commune["nom"],
        "totaux": {champ: ligne.get(champ) for champ in _CHAMPS_TOTAUX},
        "listes": blocs,
    }

    local_id = local_id_jdd(CLE, code_insee)
    nom_fichier = f"elections_municipales_2026_t1_{code_insee}.csv"
    chemin = os.path.join(dossier_sortie, nom_fichier)
    os.makedirs(dossier_sortie, exist_ok=True)
    with open(chemin, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=_COLONNES_CSV, delimiter=";")
        writer.writeheader()
        writer.writerows(_lignes_csv(resultat_commune))

    producer = organisations.resoudre_producer(
        CLE, mode_producer, commune, description_commune=description_commune,
    )
    contacts = contacts_pour_producer(
        CLE, producer, commune, email_commune=contact_email_commune,
        contacts_dynamiques=extraire_contacts_datagouv(metadata),
    )

    media = media_filtre(
        local_id, nom_fichier, commune["nom"],
        caption=f"Résultats municipales 2026, 1er tour - {commune['nom']} (CSV)",
    )

    rudi_metadata = construire_rudi_metadata(
        local_id=local_id,
        titre=f"{TITRE} - {commune['nom']} ({code_insee})",
        synopsis=SYNOPSIS_PATRON.format(commune=commune["nom"], code_insee=code_insee)[:150],
        description=DESCRIPTION_PATRON.format(commune=commune["nom"], code_insee=code_insee),
        theme=THEME,
        keywords=["élections", "municipales 2026", commune["nom"], "Ministère de l'Intérieur"],
        producer=producer,
        url_source=f"https://www.data.gouv.fr/fr/datasets/{_DATASET_ID}/",
        url_fiche=f"https://www.data.gouv.fr/fr/datasets/{_DATASET_ID}/",
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
