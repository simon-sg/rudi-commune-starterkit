"""JDD « Population » — Melodi (INSEE), série historique ``DS_POPULATIONS_HISTORIQUES``.

Confirmé le 2026-11-07 : ``https://api.insee.fr/melodi/data/DS_POPULATIONS_HISTORIQUES?
GEO=COM-{code_insee}`` répond ``200`` **sans authentification** (``accessRights: Public``)
et renvoie déjà, en une seule requête, uniquement les observations de la commune demandée
(23 points pour Gévezé, 1968-2023, mesures ``PMUN``/``PSDC``) — une seule URL stable, déjà
pré-filtrée par la source : **FILE hybride** (voir le plan, § Modèle de média), pas de
fichier local écrit.
"""

from __future__ import annotations

from rudi_harvest_toolkit.description import construire_description_structuree
from rudi_harvest_toolkit.fichier_hybride import construire_media_hybride
from rudi_harvest_toolkit.http import session
from rudi_harvest_toolkit.http_dates import parser_date_iso_stricte
from rudi_harvest_toolkit.pivot import construire_rudi_metadata

from .. import licences, organisations
from ..resultat import ResultatConnecteur, StatutConnecteur
from ._commun import contacts_pour_producer, geography_pour_commune, local_id_jdd

CLE = organisations.POPULATION
THEME = "society"
TITRE = "Population"
SYNOPSIS_PATRON = "Série historique de population de {commune} ({code_insee})"
DESCRIPTION_PATRON = (
    "Série historique de la population municipale de {commune} ({code_insee}), sourcée "
    "auprès de l'INSEE (plateforme Melodi, jeu de données DS_POPULATIONS_HISTORIQUES). "
    "Couvre les recensements disponibles depuis 1968."
)
FREQUENCE_MAJ = "annuelle"

_DATASET_ID = "DS_POPULATIONS_HISTORIQUES"
_MELODI_URL = f"https://api.insee.fr/melodi/data/{_DATASET_ID}"
_MELODI_CATALOG_URL = f"https://api.insee.fr/melodi/catalog/{_DATASET_ID}"


def _date_dataset_melodi(session_http) -> str | None:
    """Date de dernière modification du jeu Melodi (champ ``modified`` de la fiche
    catalogue, ``GET /melodi/catalog/{id}``, sans authentification) — requête de
    métadonnées légère, best-effort, jamais bloquante ni devinée."""
    try:
        reponse = session_http.get(_MELODI_CATALOG_URL, timeout=15)
        reponse.raise_for_status()
        modifie = reponse.json().get("modified")
    except Exception:  # noqa: BLE001
        return None
    return parser_date_iso_stricte(modifie) if modifie else None


def _description_enrichie(commune: dict, code_insee: str) -> str:
    return construire_description_structuree(
        quoi=(
            f"Série historique de la population municipale de {commune['nom']} "
            f"({code_insee}), recensements disponibles depuis 1968."
        ),
        comment_construit=(
            "Extraite de la plateforme Melodi de l'INSEE (jeu de données "
            "DS_POPULATIONS_HISTORIQUES), filtrée sur le code géographique de la "
            "commune en une seule requête, sans authentification requise."
        ),
        structure_variables=[
            "Année du recensement (TIME_PERIOD)",
            "Mesure (POPREF_MEASURE : PMUN pour population municipale, PSDC pour "
            "population sans doubles comptes)",
            "Valeur de la mesure (OBS_VALUE_NIVEAU)",
        ],
        frequence_maj=FREQUENCE_MAJ,
        source_label="INSEE (plateforme Melodi)",
        url_source="https://api.insee.fr/catalogue/",
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
    url = f"{_MELODI_URL}?GEO=COM-{code_insee}"

    try:
        reponse = session_http.get(url, timeout=30)
        reponse.raise_for_status()
        observations = reponse.json().get("observations", [])
    except Exception as e:  # noqa: BLE001
        return ResultatConnecteur(StatutConnecteur.ECHEC, message=str(e))

    if not observations:
        return ResultatConnecteur(StatutConnecteur.VIDE)

    local_id = local_id_jdd(CLE, code_insee)
    producer = organisations.resoudre_producer(
        CLE, mode_producer, commune, description_commune=description_commune,
    )
    contacts = contacts_pour_producer(CLE, producer, commune, email_commune=contact_email_commune)

    media = construire_media_hybride(
        local_id, url,
        media_name=f"population_{code_insee}.json",
        media_caption=f"Série historique de population - {commune['nom']} (JSON)",
        file_type="application/json",
        session_http=session_http,
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
            "population", "recensement", "démographie", "population municipale",
            commune["nom"], "INSEE", "Melodi",
        ],
        producer=producer,
        url_source=url,
        url_fiche="https://api.insee.fr/catalogue/",
        date_source=_date_dataset_melodi(session_http),
        medias=[media],
        contacts_source=contacts,
        geography=geography_pour_commune(commune),
        licence=licence,
    )

    return ResultatConnecteur(
        StatutConnecteur.PUBLIABLE, rudi_metadata=rudi_metadata, fichiers_filtres=[],
    )


__all__ = ["CLE", "DESCRIPTION_PATRON", "FREQUENCE_MAJ", "SYNOPSIS_PATRON", "THEME", "TITRE", "moissonner"]
