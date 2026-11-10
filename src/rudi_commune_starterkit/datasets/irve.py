"""JDD « Bornes de recharge électrique (IRVE) » — fichier consolidé national.

Confirmé le 2026-11-07 : le fichier consolidé national (Etalab/ODRE) est servi par
``odre.opendatasoft.com`` (une instance Opendatasoft distincte de
``portail.agenceore.fr``, le portail bloqué par un pare-feu anti-bot pour le JDD
« énergie » — aucun rapport entre les deux, celui-ci est accessible sans restriction).

**Piège de qualité de donnée trouvé en testant, pas une hypothèse** : le champ brut
``code_insee_commune`` (déclaré par l'aménageur de la borne) contient de vraies erreurs —
filtrer dessus seul a renvoyé, pour Gévezé (35120), 8 bornes réelles de Dol-de-Bretagne en
plus des 4 vraies bornes de Gévezé. Le dataset expose un champ ``consolidated_commune``
(nom de commune vérifié/corrigé par la consolidation Etalab) qui, seul, seul évite ce faux
positif (vérifié : 4/4 bornes correctement à Gévezé). **Filtre retenu : l'ET des deux**
(``consolidated_commune`` + ``code_insee_commune``) plutôt que l'un ou l'autre seul — le nom
seul resterait vulnérable à deux communes homonymes dans des départements différents (le
champ ne porte pas le département), le code INSEE seul est démontré peu fiable : la
combinaison élimine les deux risques à la fois, pas seulement le second.

Export CSV filtré par cette combinaison en une seule URL stable : **FILE hybride**.
"""

from __future__ import annotations

from urllib.parse import urlencode

from rudi_harvest_toolkit.description import construire_description_structuree
from rudi_harvest_toolkit.fichier_hybride import construire_media_hybride
from rudi_harvest_toolkit.http import session
from rudi_harvest_toolkit.pivot import construire_rudi_metadata

from .. import licences, organisations
from ..resultat import ResultatConnecteur, StatutConnecteur
from ._commun import contacts_pour_producer, geography_pour_commune, local_id_jdd

CLE = organisations.IRVE
THEME = "transportation"
TITRE = "Bornes de recharge électrique (IRVE)"
SYNOPSIS_PATRON = "Bornes de recharge pour véhicules électriques à {commune} ({code_insee})"
DESCRIPTION_PATRON = (
    "Infrastructures de recharge pour véhicules électriques (IRVE) implantées sur la "
    "commune de {commune} ({code_insee}), issues du fichier consolidé national (Etalab), "
    "filtrées sur le nom de commune vérifié par la consolidation ET le code INSEE déclaré "
    "(le code INSEE brut déclaré par les aménageurs contient des erreurs connues)."
)
FREQUENCE_MAJ = "mensuelle"

_DATASET_ID = "bornes-irve"
_EXPLORE_BASE = f"https://odre.opendatasoft.com/api/explore/v2.1/catalog/datasets/{_DATASET_ID}"


def _echapper_ods(valeur: str) -> str:
    return valeur.replace("'", "''")


def _description_enrichie(commune: dict, code_insee: str) -> str:
    return construire_description_structuree(
        quoi=(
            f"Infrastructures de recharge pour véhicules électriques (IRVE) "
            f"implantées sur le territoire de {commune['nom']} ({code_insee})."
        ),
        comment_construit=(
            "Extraites du fichier consolidé national des IRVE (Etalab/ODRE), filtré "
            "sur le nom de commune vérifié par la consolidation (consolidated_commune) "
            "ET le code INSEE déclaré par l'aménageur. Les deux critères sont combinés "
            "car le code "
            "INSEE brut déclaré contient des erreurs connues (vérifié : il mélange "
            "des bornes de communes voisines) et le nom seul resterait vulnérable à "
            "des communes homonymes dans des départements différents."
        ),
        structure_variables=[
            "Identification de la station et de l'aménageur",
            "Localisation (adresse, coordonnées géographiques, commune consolidée)",
            "Caractéristiques techniques (puissance nominale, type de prise, "
            "nombre de points de charge)",
        ],
        frequence_maj=FREQUENCE_MAJ,
        source_label="Fichier consolidé des IRVE (transport.data.gouv.fr)",
        url_source="https://www.data.gouv.fr/fr/datasets/bornes-de-recharge-pour-vehicules-electriques-3/",
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
    nom_echappe = _echapper_ods(commune["nom"])
    where = f"consolidated_commune='{nom_echappe}' AND code_insee_commune='{code_insee}'"

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
        media_name=f"irve_{code_insee}.csv",
        media_caption=f"Bornes de recharge électrique - {commune['nom']} (CSV)",
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
        description=_description_enrichie(commune, code_insee),
        theme=THEME,
        keywords=[
            "IRVE", "bornes de recharge", "véhicules électriques", "mobilité électrique",
            commune["nom"],
        ],
        producer=producer,
        url_source=url,
        url_fiche="https://www.data.gouv.fr/fr/datasets/bornes-de-recharge-pour-vehicules-electriques-3/",
        medias=[media],
        contacts_source=contacts,
        geography=geography_pour_commune(commune),
        licence=licence,
    )

    return ResultatConnecteur(
        StatutConnecteur.PUBLIABLE, rudi_metadata=rudi_metadata, fichiers_filtres=[],
    )


__all__ = ["CLE", "DESCRIPTION_PATRON", "FREQUENCE_MAJ", "SYNOPSIS_PATRON", "THEME", "TITRE", "moissonner"]
