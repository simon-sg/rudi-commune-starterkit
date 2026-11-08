"""JDD « Budget communal » — DGFiP, « Comptes individuels des communes » (data.economie.gouv.fr).

Source identifiée le 2026-11-07 (le plan la laissait « à confirmer en implémentation ») :
dataset Opendatasoft ``comptes-individuels-des-communes-fichier-global-2023-2024``
(dernier exercice disponible — en réalité 2 exercices, 2023 et 2024, bonus sur
l'hypothèse pessimiste du plan). Filtré par ``dep``/``icom`` (codes DGFiP zero-paddés,
dérivés du code INSEE : ``dep`` = 2 premiers caractères paddés à 3, ``icom`` = 3 derniers
caractères — confirmé Corse-safe : Ajaccio donne ``dep="02A"``). L'export CSV filtré est
une seule URL stable déjà pré-filtrée par la source : **FILE hybride**.

Schéma de colonnes volontairement cryptique (nomenclature DGFiP historique : ``prod``,
``impo1``, ``dgf``...) — non reformaté ici (un FILE hybride republie l'export source tel
quel, voir le plan § Modèle de média) ; la fiche de métadonnées source référencée par
``url_fiche`` documente ces codes.
"""

from __future__ import annotations

from urllib.parse import urlencode

from rudi_harvest_toolkit.fichier_hybride import construire_media_hybride
from rudi_harvest_toolkit.http import session
from rudi_harvest_toolkit.pivot import construire_rudi_metadata

from .. import organisations
from ..resultat import ResultatConnecteur, StatutConnecteur
from ._commun import contacts_pour_producer, local_id_jdd

CLE = organisations.BUDGET
THEME = "economy"
TITRE = "Budget communal"
SYNOPSIS_PATRON = "Comptes individuels de la commune de {commune} ({code_insee})"
DESCRIPTION_PATRON = (
    "Comptes individuels de la commune de {commune} ({code_insee}) - recettes, dépenses "
    "et dotations, sourcés auprès de la DGFiP (Direction générale des Finances publiques) "
    "via data.economie.gouv.fr. Limité au dernier exercice disponible (2023-2024) ; "
    "historique complet non couvert par ce socle."
)
FREQUENCE_MAJ = "annuelle"

_DATASET_ID = "comptes-individuels-des-communes-fichier-global-2023-2024"
_EXPLORE_BASE = f"https://data.economie.gouv.fr/api/explore/v2.1/catalog/datasets/{_DATASET_ID}"


class DepartementNonSupporte(ValueError):
    """Code INSEE d'outre-mer (971-976/98x) — encodage ``dep``/``icom`` de ce dataset non
    vérifié pour ces départements (schéma legacy à 3 chiffres distinct de l'INSEE réel,
    ex. Réunion 974 → ``dep="104"``, confirmé empiriquement sur un seul échantillon, pas
    assez fiable pour généraliser sans risque de donnée silencieusement fausse)."""


def _dep_icom(code_insee: str) -> tuple[str, str]:
    """Scinde un code INSEE en (``dep``, ``icom``) au format DGFiP de ce dataset —
    ``dep`` zero-paddé à 3 caractères (Corse : ``"2A"`` → ``"02A"``, pas un entier),
    ``icom`` les 3 derniers caractères du code INSEE. Mainland + Corse seulement :
    lève :class:`DepartementNonSupporte` pour un code commençant par ``97``/``98``
    (outre-mer), plutôt que de deviner un encodage non vérifié."""
    if code_insee[:2] in ("97", "98"):
        raise DepartementNonSupporte(
            f"budget communal : code INSEE d'outre-mer {code_insee!r} non supporté "
            "(encodage dep/icom DGFiP de ce dataset non vérifié pour les DOM)."
        )
    return code_insee[:2].zfill(3), code_insee[2:]


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
        dep, icom = _dep_icom(code_insee)
    except DepartementNonSupporte as e:
        return ResultatConnecteur(StatutConnecteur.ECHEC, message=str(e))
    where = f"dep='{dep}' AND icom='{icom}'"

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
        media_name=f"budget_{code_insee}.csv",
        media_caption=f"Comptes individuels de la commune - {commune['nom']} (CSV)",
        file_type="text/csv",
        session_http=session_http,
    )

    rudi_metadata = construire_rudi_metadata(
        local_id=local_id,
        titre=f"{TITRE} - {commune['nom']} ({code_insee})",
        synopsis=SYNOPSIS_PATRON.format(commune=commune["nom"], code_insee=code_insee)[:150],
        description=DESCRIPTION_PATRON.format(commune=commune["nom"], code_insee=code_insee),
        theme=THEME,
        keywords=["budget communal", "finances locales", commune["nom"], "DGFiP"],
        producer=producer,
        url_source=url,
        url_fiche=f"https://data.economie.gouv.fr/explore/dataset/{_DATASET_ID}/",
        medias=[media],
        contacts_source=contacts,
    )

    return ResultatConnecteur(
        StatutConnecteur.PUBLIABLE, rudi_metadata=rudi_metadata, fichiers_filtres=[],
    )


__all__ = [
    "CLE", "DepartementNonSupporte", "DESCRIPTION_PATRON", "FREQUENCE_MAJ",
    "SYNOPSIS_PATRON", "THEME", "TITRE", "moissonner",
]
