"""JDD « Élus » — Répertoire National des Élus (RNE), ressource « conseillers municipaux ».

Confirmé le 2026-11-07 : dataset data.gouv.fr ``repertoire-national-des-elus-1``, ressource
« elus-conseiller-municipal-cm.csv » (65 Mo, CSV ``;``, national, jamais filtré par la
source) — fichier national à filtrer localement : **FILE copie**, pas FILE hybride.

**Allowlist de colonnes personnelles, décision explicite du plan — ne jamais l'élargir** :
seules ``nom``, ``prénom``, ``fonction`` et ``date de début de mandat`` sont republiées
(avec le code/libellé de la commune pour le contexte). Le fichier source contient aussi
``date de naissance``, ``catégorie socio-professionnelle`` et ``code sexe`` — **jamais**
republiées ici, même si elles sont déjà publiques côté source : ce n'est pas notre rôle
d'amplifier leur diffusion.
"""

from __future__ import annotations

import csv
import os

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

CLE = organisations.ELUS
THEME = "citizenship"
TITRE = "Élus"
SYNOPSIS_PATRON = "Conseillers municipaux en mandat à {commune} ({code_insee})"
DESCRIPTION_PATRON = (
    "Conseillers municipaux en mandat de la commune de {commune} ({code_insee}), sourcés "
    "auprès du Répertoire National des Élus (RNE, Ministère de l'Intérieur). Limité au "
    "nom, prénom, fonction et date de début de mandat - exclut volontairement la date de "
    "naissance et la catégorie socio-professionnelle, présentes dans la source mais non "
    "republiées ici."
)
FREQUENCE_MAJ = "mensuelle"

_DATASET_ID = "repertoire-national-des-elus-1"

_COLONNE_COMMUNE = "Code de la commune"
_COLONNES_CONSERVEES = (
    "Code de la commune", "Libellé de la commune",
    "Nom de l'élu", "Prénom de l'élu", "Libellé de la fonction", "Date de début du mandat",
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
        metadata = get_dataset_metadata(_DATASET_ID, session_http=session_http)
        ressource = selectionner_ressource(metadata, motif_nom=r"conseiller[s]?-municipa")
        chemin_cache = telecharger(
            ressource["url"], dossier=os.path.join(dossier_sortie, ".cache_rne"),
            session_http=session_http,
        )
        lignes, _entetes = lire_csv_filtre(chemin_cache, _COLONNE_COMMUNE, code_insee)
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

    lignes_allegees = [
        {colonne: ligne.get(colonne) for colonne in _COLONNES_CONSERVEES} for ligne in lignes
    ]

    local_id = local_id_jdd(CLE, code_insee)
    nom_fichier = f"elus_{code_insee}.csv"
    chemin = os.path.join(dossier_sortie, nom_fichier)
    os.makedirs(dossier_sortie, exist_ok=True)
    with open(chemin, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=_COLONNES_CONSERVEES, delimiter=";")
        writer.writeheader()
        writer.writerows(lignes_allegees)

    producer = organisations.resoudre_producer(
        CLE, mode_producer, commune, description_commune=description_commune,
    )
    contacts = contacts_pour_producer(CLE, producer, commune, email_commune=contact_email_commune)

    media = media_filtre(
        local_id, nom_fichier, commune["nom"],
        caption=f"Conseillers municipaux en mandat - {commune['nom']} (CSV)",
    )

    rudi_metadata = construire_rudi_metadata(
        local_id=local_id,
        titre=f"{TITRE} - {commune['nom']} ({code_insee})",
        synopsis=SYNOPSIS_PATRON.format(commune=commune["nom"], code_insee=code_insee)[:150],
        description=DESCRIPTION_PATRON.format(commune=commune["nom"], code_insee=code_insee),
        theme=THEME,
        keywords=["élus", "conseil municipal", "RNE", commune["nom"], "Ministère de l'Intérieur"],
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
