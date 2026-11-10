"""JDD « Qualité de l'eau potable » — Hub'eau, résultats du contrôle sanitaire.

Confirmé le 2026-11-07 : ``hubeau.eaufrance.fr/api/v1/qualite_eau_potable/resultats_dis``
accepte ``code_commune`` **et** une fenêtre temporelle (``date_min_prelevement``) en
paramètres, et répond en une seule requête jusqu'à ``size=20000`` résultats (3148
résultats reçus en un seul appel pour Gévezé, sans pagination) — une seule URL stable
déjà pré-filtrée par la source : **FILE hybride**. Fenêtre limitée aux 5 dernières années
(plan : « fenêtre de quelques années », pas l'historique complet).

Hub'eau n'est qu'une plateforme d'agrégation nationale ; le producteur réel du contrôle
sanitaire est l'Agence régionale de santé (ARS) — voir ``organisations.py``.

**Axe 2 (v4) : pas de date de mise à jour de jeu exploitable.** ``resultats_dis``
n'expose qu'une ``date_prelevement`` par ligne de résultat, pas une date de mise à jour
du jeu lui-même — aucun autre endpoint Hub'eau vérifié n'en expose une non plus. Ce
module reste donc sans ``date_source`` (``dataset_dates.updated`` absent), documenté
en BACKLOG.md (§ Limites de couverture connues) plutôt qu'un mécanisme inventé.

**Axe 3 (v4) : pas de GeoJSON possible.** ``resultats_dis`` (re-vérifié en direct,
32 champs) ne porte aucune coordonnée géographique ; ``reseaux`` n'est qu'une liste
d'identifiants de réseau de distribution, pas une géométrie. Aucun autre endpoint
Hub'eau vérifié n'en expose une pour ce JDD. Confirmé, pas forcé — documenté en
BACKLOG.md plutôt qu'un géocodage inventé.
"""

from __future__ import annotations

import datetime

from rudi_harvest_toolkit.description import construire_description_structuree
from rudi_harvest_toolkit.fichier_hybride import construire_media_hybride
from rudi_harvest_toolkit.http import session
from rudi_harvest_toolkit.pivot import construire_rudi_metadata

from .. import licences, organisations
from ..resultat import ResultatConnecteur, StatutConnecteur
from ._commun import contacts_pour_producer, geography_pour_commune, local_id_jdd

CLE = organisations.EAU_POTABLE
THEME = "health"
TITRE = "Qualité de l'eau potable"
SYNOPSIS_PATRON = "Résultats du contrôle sanitaire de l'eau potable à {commune} ({code_insee})"
DESCRIPTION_PATRON = (
    "Résultats des analyses de contrôle sanitaire de l'eau destinée à la consommation "
    "humaine, pour les réseaux desservant la commune de {commune} ({code_insee}), sur les "
    "5 dernières années. Producteur réel : l'Agence régionale de santé (ARS) ; Hub'eau "
    "n'est qu'une plateforme nationale d'agrégation, pas le producteur."
)
FREQUENCE_MAJ = "mensuelle"

_HUBEAU_URL = "https://hubeau.eaufrance.fr/api/v1/qualite_eau_potable/resultats_dis"
_FENETRE_ANNEES = 5
_TAILLE_PAGE = 20000


def _description_enrichie(commune: dict, code_insee: str) -> str:
    return construire_description_structuree(
        quoi=(
            f"Résultats des analyses de contrôle sanitaire de l'eau destinée à la "
            f"consommation humaine, pour les réseaux desservant {commune['nom']} "
            f"({code_insee}), sur les {_FENETRE_ANNEES} dernières années."
        ),
        comment_construit=(
            "Extrait de l'API Hub'eau « qualité de l'eau potable » (résultats du "
            "contrôle sanitaire), filtré par code commune et fenêtre temporelle. "
            "Producteur réel : l'Agence régionale de santé (ARS), Hub'eau n'étant "
            "qu'une plateforme nationale d'agrégation, pas le producteur."
        ),
        structure_variables=[
            "Identification du point de prélèvement et de la date d'analyse",
            "Paramètre analysé (libellé et code SISE-Eaux)",
            "Résultat de l'analyse et conformité réglementaire",
        ],
        frequence_maj=FREQUENCE_MAJ,
        source_label="Hub'eau (qualité de l'eau potable)",
        url_source="https://hubeau.eaufrance.fr/page/api-qualite-eau-potable",
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
    date_min = datetime.date.today().replace(year=datetime.date.today().year - _FENETRE_ANNEES)
    url = (
        f"{_HUBEAU_URL}?code_commune={code_insee}"
        f"&date_min_prelevement={date_min.isoformat()}&size={_TAILLE_PAGE}"
    )

    try:
        reponse = session_http.get(url, timeout=30)
        reponse.raise_for_status()
        count = reponse.json().get("count", 0)
    except Exception as e:  # noqa: BLE001
        return ResultatConnecteur(StatutConnecteur.ECHEC, message=str(e))

    if not count:
        return ResultatConnecteur(StatutConnecteur.VIDE)

    local_id = local_id_jdd(CLE, code_insee)
    producer = organisations.resoudre_producer(
        CLE, mode_producer, commune, description_commune=description_commune,
    )
    contacts = contacts_pour_producer(CLE, producer, commune, email_commune=contact_email_commune)

    media = construire_media_hybride(
        local_id, url,
        media_name=f"eau_potable_{code_insee}.json",
        media_caption=f"Contrôle sanitaire de l'eau potable - {commune['nom']} (JSON)",
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
            "eau potable", "contrôle sanitaire", "qualité de l'eau", "santé publique",
            commune["nom"], "ARS", "Hub'eau",
        ],
        producer=producer,
        url_source=url,
        url_fiche="https://hubeau.eaufrance.fr/page/api-qualite-eau-potable",
        medias=[media],
        contacts_source=contacts,
        geography=geography_pour_commune(commune),
        licence=licence,
    )

    return ResultatConnecteur(
        StatutConnecteur.PUBLIABLE, rudi_metadata=rudi_metadata, fichiers_filtres=[],
    )


__all__ = ["CLE", "DESCRIPTION_PATRON", "FREQUENCE_MAJ", "SYNOPSIS_PATRON", "THEME", "TITRE", "moissonner"]
