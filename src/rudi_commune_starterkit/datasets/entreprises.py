"""JDD « Entreprises » — recherche-entreprises.api.gouv.fr, filtré par commune.

Source paginée (25 résultats/page max) : jamais une seule requête pour une commune de
taille courante (confirmé le 2026-11-07 : 1639 résultats pour Gévezé, ~4200 habitants,
avant même filtrage par état administratif) — donc **FILE combiné** (toutes les pages
récupérées puis fusionnées en un seul JSON), jamais FILE hybride (voir le plan, § Modèle
de média).
"""

from __future__ import annotations

import json
import os

from rudi_harvest_toolkit.pivot import construire_rudi_metadata, media_filtre

from .. import organisations
from ..resultat import ResultatConnecteur, StatutConnecteur
from ._commun import contacts_pour_producer, local_id_jdd, recherche_entreprises, simplifier_resultat_entreprise

CLE = organisations.ENTREPRISES
THEME = "economy"
TITRE = "Entreprises"
SYNOPSIS_PATRON = "Entreprises actives ayant un établissement à {commune} ({code_insee})"
DESCRIPTION_PATRON = (
    "Entreprises ayant au moins un établissement actif sur le territoire de la commune de "
    "{commune} ({code_insee}), sourcées auprès de l'INSEE (répertoire SIRENE) via l'API "
    "recherche-entreprises.api.gouv.fr. Instantané figé à la date de moisson - pas une vue "
    "live ni mise à jour en continu."
)
FREQUENCE_MAJ = "mensuelle"


def moissonner(
    code_insee: str,
    commune: dict,
    *,
    dossier_sortie: str,
    mode_producer: str = "source",
    contact_email_commune: str | None = None,
    session_http=None,
) -> ResultatConnecteur:
    try:
        resultats = recherche_entreprises(
            code_insee, etat_administratif="A", session_http=session_http,
        )
    except Exception as e:  # noqa: BLE001 — statut ECHEC explicite, jamais une exception qui remonte
        return ResultatConnecteur(StatutConnecteur.ECHEC, message=str(e))

    if not resultats:
        return ResultatConnecteur(StatutConnecteur.VIDE)

    entreprises = [simplifier_resultat_entreprise(r) for r in resultats]

    local_id = local_id_jdd(CLE, code_insee)
    nom_fichier = f"entreprises_{code_insee}.json"
    chemin = os.path.join(dossier_sortie, nom_fichier)
    os.makedirs(dossier_sortie, exist_ok=True)
    with open(chemin, "w", encoding="utf-8") as f:
        json.dump(entreprises, f, ensure_ascii=False, indent=2)

    producer = organisations.resoudre_producer(CLE, mode_producer, commune)
    contacts = contacts_pour_producer(CLE, producer, commune, email_commune=contact_email_commune)

    media = media_filtre(
        local_id, nom_fichier, commune["nom"],
        caption=f"Entreprises actives à {commune['nom']} (JSON)",
    )

    rudi_metadata = construire_rudi_metadata(
        local_id=local_id,
        titre=f"{TITRE} - {commune['nom']} ({code_insee})",
        synopsis=SYNOPSIS_PATRON.format(commune=commune["nom"], code_insee=code_insee)[:150],
        description=DESCRIPTION_PATRON.format(commune=commune["nom"], code_insee=code_insee),
        theme=THEME,
        keywords=["entreprises", "SIRENE", commune["nom"], "INSEE"],
        producer=producer,
        url_source=f"https://recherche-entreprises.api.gouv.fr/search?code_commune={code_insee}",
        url_fiche="https://www.data.gouv.fr/dataservices/api-recherche-dentreprises/",
        medias=[media],
        contacts_source=contacts,
    )

    return ResultatConnecteur(
        StatutConnecteur.PUBLIABLE, rudi_metadata=rudi_metadata, fichiers_filtres=[chemin],
    )


__all__ = ["CLE", "DESCRIPTION_PATRON", "FREQUENCE_MAJ", "SYNOPSIS_PATRON", "THEME", "TITRE", "moissonner"]
