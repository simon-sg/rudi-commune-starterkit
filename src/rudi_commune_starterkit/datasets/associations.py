"""JDD « Associations » — recherche-entreprises.api.gouv.fr, filtré commune + nature
juridique 9220 (associations loi 1901 déclarées), via le répertoire SIRENE.

Confirmé le 2026-11-07 : 104 résultats pour Gévezé avec ce filtre précis — API v1 confirmée
suffisante (pas de repli fichier RNA, reporté en v2 si besoin constaté). Source paginée
(25/page), jamais une seule requête → **FILE combiné**, comme ``entreprises.py``.
"""

from __future__ import annotations

import csv
import os

from rudi_harvest_toolkit.pivot import construire_rudi_metadata, media_filtre

from .. import licences, organisations
from ..resultat import ResultatConnecteur, StatutConnecteur
from ._commun import (
    COLONNES_CSV_ENTREPRISES,
    contacts_pour_producer,
    lignes_csv_entreprises,
    local_id_jdd,
    recherche_entreprises,
    simplifier_resultat_entreprise,
)

CLE = organisations.ASSOCIATIONS
THEME = "citizenship"
TITRE = "Associations"
SYNOPSIS_PATRON = "Associations déclarées à {commune} ({code_insee})"
DESCRIPTION_PATRON = (
    "Associations loi 1901 déclarées (catégorie juridique 9220) ayant au moins un "
    "établissement sur le territoire de la commune de {commune} ({code_insee}), sourcées "
    "auprès de l'INSEE (répertoire SIRENE) via l'API recherche-entreprises.api.gouv.fr. "
    "Instantané figé à la date de moisson - pas une vue live ni mise à jour en continu."
)
FREQUENCE_MAJ = "mensuelle"

_NATURE_JURIDIQUE_ASSOCIATION = "9220"


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
    try:
        resultats = recherche_entreprises(
            code_insee, nature_juridique=_NATURE_JURIDIQUE_ASSOCIATION, session_http=session_http,
        )
    except Exception as e:  # noqa: BLE001
        return ResultatConnecteur(StatutConnecteur.ECHEC, message=str(e))

    if not resultats:
        return ResultatConnecteur(StatutConnecteur.VIDE)

    associations = [simplifier_resultat_entreprise(r) for r in resultats]

    local_id = local_id_jdd(CLE, code_insee)
    nom_fichier = f"associations_{code_insee}.csv"
    chemin = os.path.join(dossier_sortie, nom_fichier)
    os.makedirs(dossier_sortie, exist_ok=True)
    with open(chemin, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=COLONNES_CSV_ENTREPRISES, delimiter=";")
        writer.writeheader()
        writer.writerows(lignes_csv_entreprises(associations))

    producer = organisations.resoudre_producer(
        CLE, mode_producer, commune, description_commune=description_commune,
    )
    contacts = contacts_pour_producer(CLE, producer, commune, email_commune=contact_email_commune)

    media = media_filtre(
        local_id, nom_fichier, commune["nom"],
        caption=f"Associations déclarées à {commune['nom']} (CSV)",
    )

    try:
        licence = licences.licence_pour_jdd(CLE)
    except licences.LicenceInconnueError as e:
        return ResultatConnecteur(StatutConnecteur.ECHEC, message=str(e))

    rudi_metadata = construire_rudi_metadata(
        local_id=local_id,
        titre=f"{TITRE} - {commune['nom']} ({code_insee})",
        synopsis=SYNOPSIS_PATRON.format(commune=commune["nom"], code_insee=code_insee)[:150],
        description=DESCRIPTION_PATRON.format(commune=commune["nom"], code_insee=code_insee),
        theme=THEME,
        keywords=["associations", "loi 1901", "SIRENE", commune["nom"], "INSEE"],
        producer=producer,
        url_source=(
            f"https://recherche-entreprises.api.gouv.fr/search?code_commune={code_insee}"
            f"&nature_juridique={_NATURE_JURIDIQUE_ASSOCIATION}"
        ),
        url_fiche="https://www.data.gouv.fr/dataservices/api-recherche-dentreprises/",
        medias=[media],
        contacts_source=contacts,
        licence=licence,
    )

    return ResultatConnecteur(
        StatutConnecteur.PUBLIABLE, rudi_metadata=rudi_metadata, fichiers_filtres=[chemin],
    )


__all__ = ["CLE", "DESCRIPTION_PATRON", "FREQUENCE_MAJ", "SYNOPSIS_PATRON", "THEME", "TITRE", "moissonner"]
