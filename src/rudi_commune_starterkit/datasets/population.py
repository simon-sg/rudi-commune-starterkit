"""JDD « Population » — Melodi (INSEE), série historique ``DS_POPULATIONS_HISTORIQUES``.

Confirmé le 2026-11-07 : ``https://api.insee.fr/melodi/data/DS_POPULATIONS_HISTORIQUES?
GEO=COM-{code_insee}`` répond ``200`` **sans authentification** (``accessRights: Public``)
et renvoie déjà, en une seule requête, uniquement les observations de la commune demandée
(23 points pour Gévezé, 1968-2023, mesures ``PMUN``/``PSDC``) — une seule URL stable, déjà
pré-filtrée par la source : **FILE hybride** (voir le plan, § Modèle de média), pas de
fichier local écrit.
"""

from __future__ import annotations

from rudi_harvest_toolkit.fichier_hybride import construire_media_hybride
from rudi_harvest_toolkit.http import session
from rudi_harvest_toolkit.pivot import construire_rudi_metadata

from .. import organisations
from ..resultat import ResultatConnecteur, StatutConnecteur
from ._commun import contacts_pour_producer, local_id_jdd

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

_MELODI_URL = "https://api.insee.fr/melodi/data/DS_POPULATIONS_HISTORIQUES"


def moissonner(
    code_insee: str,
    commune: dict,
    *,
    dossier_sortie: str,
    mode_producer: str = "source",
    contact_email_commune: str | None = None,
    session_http=None,
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
    producer = organisations.resoudre_producer(CLE, mode_producer, commune)
    contacts = contacts_pour_producer(CLE, producer, commune, email_commune=contact_email_commune)

    media = construire_media_hybride(
        local_id, url,
        media_name=f"population_{code_insee}.json",
        media_caption=f"Série historique de population - {commune['nom']} (JSON)",
        file_type="application/json",
        session_http=session_http,
    )

    rudi_metadata = construire_rudi_metadata(
        local_id=local_id,
        titre=f"{TITRE} - {commune['nom']} ({code_insee})",
        synopsis=SYNOPSIS_PATRON.format(commune=commune["nom"], code_insee=code_insee)[:150],
        description=DESCRIPTION_PATRON.format(commune=commune["nom"], code_insee=code_insee),
        theme=THEME,
        keywords=["population", "recensement", commune["nom"], "INSEE", "Melodi"],
        producer=producer,
        url_source=url,
        url_fiche="https://api.insee.fr/catalogue/",
        medias=[media],
        contacts_source=contacts,
    )

    return ResultatConnecteur(
        StatutConnecteur.PUBLIABLE, rudi_metadata=rudi_metadata, fichiers_filtres=[],
    )


__all__ = ["CLE", "DESCRIPTION_PATRON", "FREQUENCE_MAJ", "SYNOPSIS_PATRON", "THEME", "TITRE", "moissonner"]
