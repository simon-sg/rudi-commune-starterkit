"""JDD « Entreprises » — recherche-entreprises.api.gouv.fr, filtré par commune.

Source paginée (25 résultats/page max) : jamais une seule requête pour une commune de
taille courante (confirmé le 2026-11-07 : 1639 résultats pour Gévezé, ~4200 habitants,
avant même filtrage par état administratif) — donc **FILE combiné** (toutes les pages
récupérées puis fusionnées en un seul JSON), jamais FILE hybride (voir le plan, § Modèle
de média).
"""

from __future__ import annotations

import csv
import os

from rudi_harvest_toolkit.description import construire_description_structuree
from rudi_harvest_toolkit.pivot import construire_rudi_metadata, media_filtre

from .. import licences, organisations
from ..resultat import ResultatConnecteur, StatutConnecteur
from ._commun import (
    COLONNES_CSV_ENTREPRISES,
    contacts_pour_producer,
    date_plus_recente_entreprises,
    geography_pour_commune,
    lignes_csv_entreprises,
    local_id_jdd,
    recherche_entreprises,
    simplifier_resultat_entreprise,
)

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


def _description_enrichie(commune: dict, code_insee: str) -> str:
    return construire_description_structuree(
        quoi=(
            f"Entreprises ayant au moins un établissement actif sur le territoire de "
            f"{commune['nom']} ({code_insee}), avec leurs établissements rattachés."
        ),
        comment_construit=(
            "Extrait de l'API recherche-entreprises.api.gouv.fr (répertoire SIRENE de "
            "l'INSEE), filtré par code commune et état administratif actif, pages "
            "fusionnées en un seul fichier CSV. Instantané figé à la date de moisson, "
            "pas une vue live."
        ),
        structure_variables=[
            "siren, nom_complet, sigle",
            "activite_principale, nature_juridique, catégorie d'entreprise",
            "tranche d'effectif salarié, date de création, état administratif",
            "liste des établissements rattachés (siret, adresse, code postal, "
            "commune, siège ou non)",
        ],
        frequence_maj=FREQUENCE_MAJ,
        source_label="API Recherche d'entreprises (INSEE/DINUM)",
        url_source="https://www.data.gouv.fr/dataservices/api-recherche-dentreprises/",
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
    nom_fichier = f"entreprises_{code_insee}.csv"
    chemin = os.path.join(dossier_sortie, nom_fichier)
    os.makedirs(dossier_sortie, exist_ok=True)
    with open(chemin, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=COLONNES_CSV_ENTREPRISES, delimiter=";")
        writer.writeheader()
        writer.writerows(lignes_csv_entreprises(entreprises))

    producer = organisations.resoudre_producer(
        CLE, mode_producer, commune, description_commune=description_commune,
    )
    contacts = contacts_pour_producer(CLE, producer, commune, email_commune=contact_email_commune)

    media = media_filtre(
        local_id, nom_fichier, commune["nom"],
        caption=f"Entreprises actives à {commune['nom']} (CSV)",
    )

    try:
        licence = licences.licence_pour_jdd(CLE)
    except licences.LicenceInconnueError as e:
        return ResultatConnecteur(StatutConnecteur.ECHEC, message=str(e))

    rudi_metadata = construire_rudi_metadata(
        local_id=local_id,
        titre=f"{TITRE} - {commune['nom']} ({code_insee})",
        synopsis=SYNOPSIS_PATRON.format(commune=commune["nom"], code_insee=code_insee)[:150],
        description=_description_enrichie(commune, code_insee),
        theme=THEME,
        keywords=[
            "entreprises", "SIRENE", "établissements", "activité économique",
            commune["nom"], "INSEE",
        ],
        producer=producer,
        url_source=f"https://recherche-entreprises.api.gouv.fr/search?code_commune={code_insee}",
        url_fiche="https://www.data.gouv.fr/dataservices/api-recherche-dentreprises/",
        date_source=date_plus_recente_entreprises(resultats),
        medias=[media],
        contacts_source=contacts,
        geography=geography_pour_commune(commune),
        licence=licence,
    )

    return ResultatConnecteur(
        StatutConnecteur.PUBLIABLE, rudi_metadata=rudi_metadata, fichiers_filtres=[chemin],
    )


__all__ = ["CLE", "DESCRIPTION_PATRON", "FREQUENCE_MAJ", "SYNOPSIS_PATRON", "THEME", "TITRE", "moissonner"]
