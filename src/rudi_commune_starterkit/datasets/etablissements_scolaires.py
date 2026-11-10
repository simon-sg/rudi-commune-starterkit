"""JDD « Établissements scolaires » — annuaire de l'éducation (data.education.gouv.fr).

Confirmé le 2026-11-07 : dataset Opendatasoft ``fr-en-annuaire-education``, filtrable en
une seule requête par ``code_commune`` (exact, pas de préfixe) — 3 établissements réels
trouvés pour Gévezé. Export CSV filtré pré-filtré par la source en une seule URL stable :
**FILE hybride**.
"""

from __future__ import annotations

from urllib.parse import urlencode

from rudi_harvest_toolkit.fichier_hybride import construire_media_hybride
from rudi_harvest_toolkit.http import session
from rudi_harvest_toolkit.pivot import construire_rudi_metadata

from .. import licences, organisations
from ..resultat import ResultatConnecteur, StatutConnecteur
from ._commun import contacts_pour_producer, geography_pour_commune, local_id_jdd

CLE = organisations.ETABLISSEMENTS_SCOLAIRES
THEME = "education"
TITRE = "Établissements scolaires"
SYNOPSIS_PATRON = "Établissements scolaires de la commune de {commune} ({code_insee})"
DESCRIPTION_PATRON = (
    "Établissements scolaires (écoles, collèges, lycées) implantés sur la commune de "
    "{commune} ({code_insee}), sourcés auprès du Ministère de l'Éducation nationale via "
    "l'annuaire de l'éducation (data.education.gouv.fr)."
)
FREQUENCE_MAJ = "mensuelle"

_DATASET_ID = "fr-en-annuaire-education"
_EXPLORE_BASE = f"https://data.education.gouv.fr/api/explore/v2.1/catalog/datasets/{_DATASET_ID}"


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
    where = f"code_commune='{code_insee}'"

    try:
        reponse = session_http.get(
            f"{_EXPLORE_BASE}/records", params={"where": where, "limit": 1}, timeout=30,
        )
        reponse.raise_for_status()
        total_count = reponse.json().get("total_count", 0)
    except Exception as e:  # noqa: BLE001
        return ResultatConnecteur(StatutConnecteur.ECHEC, message=str(e))

    if not total_count:
        return ResultatConnecteur(StatutConnecteur.VIDE)

    local_id = local_id_jdd(CLE, code_insee)
    producer = organisations.resoudre_producer(
        CLE, mode_producer, commune, description_commune=description_commune,
    )
    contacts = contacts_pour_producer(CLE, producer, commune, email_commune=contact_email_commune)

    url = f"{_EXPLORE_BASE}/exports/csv?{urlencode({'where': where})}"
    media = construire_media_hybride(
        local_id, url,
        media_name=f"etablissements_scolaires_{code_insee}.csv",
        media_caption=f"Établissements scolaires - {commune['nom']} (CSV)",
        file_type="text/csv",
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
        description=DESCRIPTION_PATRON.format(commune=commune["nom"], code_insee=code_insee),
        theme=THEME,
        keywords=["établissements scolaires", "écoles", commune["nom"], "Éducation nationale"],
        producer=producer,
        url_source=url,
        url_fiche=f"https://data.education.gouv.fr/explore/dataset/{_DATASET_ID}/",
        medias=[media],
        contacts_source=contacts,
        geography=geography_pour_commune(commune),
        licence=licence,
    )

    return ResultatConnecteur(
        StatutConnecteur.PUBLIABLE, rudi_metadata=rudi_metadata, fichiers_filtres=[],
    )


__all__ = ["CLE", "DESCRIPTION_PATRON", "FREQUENCE_MAJ", "SYNOPSIS_PATRON", "THEME", "TITRE", "moissonner"]
