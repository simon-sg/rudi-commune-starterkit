"""JDD « Marchés publics (DECP) » — data.economie.gouv.fr, filtré par SIRET acheteur.

Source identifiée le 2026-11-07 (le plan la laissait « à confirmer en implémentation ») :
dataset Opendatasoft ``decp-2022-marches-valides`` (le nom fige le millésime du schéma
DECP, pas la période couverte — contient en réalité des marchés notifiés jusqu'en 2026).
Filtré sur ``acheteur_id`` (SIRET = SIREN de la commune + NIC du siège) via
``startswith(acheteur_id, '{siren}')`` — un ``like`` nu ne fait pas de préfixe sur cette
plateforme, vérifié empiriquement (0 résultat avec ``like``, 13 avec ``startswith`` pour
Gévezé). Export CSV filtré = une seule URL stable déjà pré-filtrée par la source : **FILE
hybride**.

Périmètre v1 : seuls les marchés (pas les concessions, dataset ``decp-2022-concessions-
valides`` distinct, hors socle).
"""

from __future__ import annotations

from urllib.parse import urlencode

from rudi_harvest_toolkit.commune import resoudre_siren_commune
from rudi_harvest_toolkit.fichier_hybride import construire_media_hybride
from rudi_harvest_toolkit.http import session
from rudi_harvest_toolkit.pivot import construire_rudi_metadata

from .. import organisations
from ..resultat import ResultatConnecteur, StatutConnecteur
from ._commun import contacts_pour_producer, local_id_jdd

CLE = organisations.MARCHES_PUBLICS
THEME = "economy"
TITRE = "Marchés publics"
SYNOPSIS_PATRON = "Marchés publics notifiés par la commune de {commune} ({code_insee})"
DESCRIPTION_PATRON = (
    "Données essentielles de la commande publique (DECP) notifiées par la commune de "
    "{commune} ({code_insee}) en tant qu'acheteur public, sourcées via "
    "data.economie.gouv.fr. Ne couvre que les marchés (pas les concessions)."
)
FREQUENCE_MAJ = "mensuelle"

_DATASET_ID = "decp-2022-marches-valides"
_EXPLORE_BASE = f"https://data.economie.gouv.fr/api/explore/v2.1/catalog/datasets/{_DATASET_ID}"


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

    try:
        siren = resoudre_siren_commune(code_insee, session_http=session_http)
    except Exception as e:  # noqa: BLE001
        return ResultatConnecteur(StatutConnecteur.ECHEC, message=str(e))

    where = f"startswith(acheteur_id, '{siren}')"

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
    producer = organisations.resoudre_producer(CLE, mode_producer, commune)
    contacts = contacts_pour_producer(CLE, producer, commune, email_commune=contact_email_commune)

    url = f"{_EXPLORE_BASE}/exports/csv?{urlencode({'where': where})}"
    media = construire_media_hybride(
        local_id, url,
        media_name=f"marches_publics_{code_insee}.csv",
        media_caption=f"Marchés publics notifiés par la commune - {commune['nom']} (CSV)",
        file_type="text/csv",
        session_http=session_http,
    )

    rudi_metadata = construire_rudi_metadata(
        local_id=local_id,
        titre=f"{TITRE} - {commune['nom']} ({code_insee})",
        synopsis=SYNOPSIS_PATRON.format(commune=commune["nom"], code_insee=code_insee)[:150],
        description=DESCRIPTION_PATRON.format(commune=commune["nom"], code_insee=code_insee),
        theme=THEME,
        keywords=["marchés publics", "DECP", "commande publique", commune["nom"]],
        producer=producer,
        url_source=url,
        url_fiche=f"https://data.economie.gouv.fr/explore/dataset/{_DATASET_ID}/",
        medias=[media],
        contacts_source=contacts,
    )

    return ResultatConnecteur(
        StatutConnecteur.PUBLIABLE, rudi_metadata=rudi_metadata, fichiers_filtres=[],
    )


__all__ = ["CLE", "DESCRIPTION_PATRON", "FREQUENCE_MAJ", "SYNOPSIS_PATRON", "THEME", "TITRE", "moissonner"]
