"""JDD « Valeurs foncières (DVF) » — fichier national unique, filtré par commune.

**Migration d'urgence (Axe 0, v4, 2026-11)** : la source précédente
(``files.data.gouv.fr/geo-dvf/latest/csv/{année}/departements/{dep}.csv.gz``, fichiers
départementaux) était servie par une ressource du dataset explicitement intitulée
``[ARCHIVE] Données au format CSV - livraison avril - suppression au 31/11/2026`` —
annoncée pour suppression. **Vérifié en direct le 2026-11-10** sur le dataset data.gouv.fr
``demandes-de-valeurs-foncieres-geolocalisees`` (id ``5cc1b94a634f4165e96436c1``) : aucune
ressource par département n'existe ailleurs dans ce dataset — seules des ressources
**nationales** sont disponibles (``full-YYYY.csv.gz`` par exercice, et une ressource
unique ``dvf.csv.gz`` couvrant juillet 2021 à juin 2026, 609 Mo). Retenu : la ressource
unique (un seul téléchargement/une seule entrée de cache, plutôt que 6 fichiers annuels à
unifier) — schéma confirmé identique à l'ancienne source départementale (mêmes colonnes,
dont ``date_mutation``, ``code_commune``, ``longitude``/``latitude``), **délimiteur
virgule**, pas point-virgule (contrairement à la plupart des autres sources de ce socle).

**Résolution dynamique de l'URL** (jamais codée en dur) : le nom du fichier physique sur
``static.data.gouv.fr`` change à chaque republication de la ressource (horodatage dans le
chemin) — l'URL est donc résolue à chaque run via
``datagouv.get_dataset_metadata()``/``selectionner_ressource()``, pas une constante.

Plus de sondage par année ni d'union de schéma : un seul fichier, un seul appel réseau. Le
« millésime » n'est plus un concept de la source (c'était un artefact du découpage par
exercice) — les années réellement couvertes pour une commune sont dérivées des valeurs
``date_mutation`` effectivement trouvées (colonne native de la source, pas ajoutée).

**Axe 4 (v4, 2026-11-11) — glossaire.** Vérifié en direct (en-tête + échantillon réel du
fichier source) : la quasi-totalité des codes DVF sont déjà accompagnés de leur libellé en
clair dans une colonne adjacente (``code_type_local``/``type_local``,
``code_nature_culture``/``nature_culture``) — pas besoin d'un glossaire pour ceux-là. Les
deux identifiants réellement non triviaux sans explication (``id_mutation``,
``id_parcelle``) sont glossés via ``construire_description_structuree(glossaire=...)``.
"""

from __future__ import annotations

import csv
import os

from rudi_harvest_toolkit.datagouv import get_dataset_metadata, selectionner_ressource
from rudi_harvest_toolkit.description import construire_description_structuree
from rudi_harvest_toolkit.download_cache import date_fichier_cache, telecharger
from rudi_harvest_toolkit.http import session
from rudi_harvest_toolkit.pivot import construire_rudi_metadata, media_filtre
from rudi_harvest_toolkit.tabular import lire_csv_filtre

from .. import licences, organisations
from ..resultat import ResultatConnecteur, StatutConnecteur
from ._commun import contacts_pour_producer, geography_pour_commune, local_id_jdd

CLE = organisations.IMMOBILIER_DVF
THEME = "housing"
TITRE = "Valeurs foncières (DVF)"
SYNOPSIS_PATRON = "Transactions immobilières (DVF) à {commune} ({code_insee})"
DESCRIPTION_PATRON = (
    "Valeurs foncières (DVF) des transactions immobilières réalisées sur la commune de "
    "{commune} ({code_insee}), sur les années disponibles ({annees}), sourcées auprès "
    "de la DGFiP (fichier national unique, filtré par commune)."
)
FREQUENCE_MAJ = "annuelle"

_DATASET_SLUG = "demandes-de-valeurs-foncieres-geolocalisees"
_MOTIF_RESSOURCE = r"fichier unique"
_FORMAT_RESSOURCE = "csv.gz"
_COLONNE_COMMUNE = "code_commune"
_COLONNE_DATE_MUTATION = "date_mutation"

_GLOSSAIRE_CODES = {
    "id_mutation": (
        "Identifiant d'une transaction (mutation) : une même transaction peut "
        "produire plusieurs lignes si elle porte sur plusieurs locaux/lots."
    ),
    "id_parcelle": (
        "Référence cadastrale de la parcelle (code commune, section et numéro de "
        "parcelle concatenés)."
    ),
}


def _description_enrichie(commune: dict, code_insee: str, annees_texte: str) -> str:
    return construire_description_structuree(
        quoi=(
            f"Transactions immobilières (mutations) ayant eu lieu sur le territoire "
            f"de {commune['nom']} ({code_insee}), sur les années disponibles "
            f"({annees_texte})."
        ),
        comment_construit=(
            "Demandes de Valeurs Foncières (DVF) géolocalisées de la DGFiP, fichier "
            "national unique (couvrant juillet 2021 à juin 2026) filtré sur le code "
            "commune."
        ),
        structure_variables=[
            "Identification de la mutation (date, nature, valeur foncière)",
            "Localisation (adresse, code commune, section et numéro de parcelle)",
            "Bien (type de local, surface, nombre de pièces, dépendances)",
        ],
        frequence_maj=FREQUENCE_MAJ,
        source_label="DGFiP (Demandes de Valeurs Foncières)",
        url_source=(
            "https://www.data.gouv.fr/fr/datasets/"
            "demandes-de-valeurs-foncieres-geolocalisees/"
        ),
        glossaire=_GLOSSAIRE_CODES,
        limites=[
            "Les codes type_local/nature_culture sont déjà accompagnés de leur "
            "libellé en clair dans une colonne adjacente du fichier : pas de "
            "glossaire séparé pour ceux-là.",
        ],
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
        meta = get_dataset_metadata(_DATASET_SLUG, session_http=session_http)
        ressource = selectionner_ressource(
            meta, motif_nom=_MOTIF_RESSOURCE, format=_FORMAT_RESSOURCE,
        )
        url = ressource["url"]
        chemin_cache = telecharger(
            url, dossier=os.path.join(dossier_sortie, ".cache_dvf"),
            session_http=session_http,
        )
        lignes, _entetes = lire_csv_filtre(
            chemin_cache, _COLONNE_COMMUNE, code_insee, delimiter=",", gzip=True,
        )
    except Exception as e:  # noqa: BLE001
        return ResultatConnecteur(StatutConnecteur.ECHEC, message=str(e))

    if not lignes:
        return ResultatConnecteur(StatutConnecteur.VIDE)

    annees_trouvees = sorted({
        ligne[_COLONNE_DATE_MUTATION][:4]
        for ligne in lignes
        if ligne.get(_COLONNE_DATE_MUTATION)
    })

    local_id = local_id_jdd(CLE, code_insee)
    nom_fichier = f"immobilier_dvf_{code_insee}.csv"
    chemin = os.path.join(dossier_sortie, nom_fichier)
    os.makedirs(dossier_sortie, exist_ok=True)
    with open(chemin, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=_entetes, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(lignes)

    producer = organisations.resoudre_producer(
        CLE, mode_producer, commune, description_commune=description_commune,
    )
    contacts = contacts_pour_producer(CLE, producer, commune, email_commune=contact_email_commune)

    annees_texte = ", ".join(annees_trouvees)
    media = media_filtre(
        local_id, nom_fichier, commune["nom"],
        caption=f"Valeurs foncières (DVF), {annees_texte} - {commune['nom']} (CSV)",
    )

    try:
        licence = licences.licence_pour_jdd(CLE)
    except licences.LicenceInconnueError as e:
        return ResultatConnecteur(StatutConnecteur.ECHEC, message=str(e))

    rudi_metadata = construire_rudi_metadata(
        local_id=local_id,
        titre=f"{TITRE} - {commune['nom']} ({code_insee})",
        synopsis=SYNOPSIS_PATRON.format(commune=commune["nom"], code_insee=code_insee)[:150],
        description=_description_enrichie(commune, code_insee, annees_texte),
        theme=THEME,
        keywords=[
            "DVF", "valeurs foncières", "immobilier", "transactions immobilières",
            "mutations", commune["nom"], "DGFiP",
        ],
        producer=producer,
        url_source=url,
        url_fiche=(
            "https://www.data.gouv.fr/fr/datasets/"
            "demandes-de-valeurs-foncieres-geolocalisees/"
        ),
        date_source=date_fichier_cache(chemin_cache),
        medias=[media],
        contacts_source=contacts,
        geography=geography_pour_commune(commune),
        licence=licence,
    )

    return ResultatConnecteur(
        StatutConnecteur.PUBLIABLE, rudi_metadata=rudi_metadata, fichiers_filtres=[chemin],
    )


__all__ = [
    "CLE", "DESCRIPTION_PATRON", "FREQUENCE_MAJ",
    "SYNOPSIS_PATRON", "THEME", "TITRE", "moissonner",
]
