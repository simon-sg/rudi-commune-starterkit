"""JDD « Établissements scolaires » — annuaire de l'éducation (data.education.gouv.fr).

Confirmé le 2026-11-07 : dataset Opendatasoft ``fr-en-annuaire-education``, filtrable en
une seule requête par ``code_commune`` (exact, pas de préfixe) — 3 établissements réels
trouvés pour Gévezé. Export CSV filtré pré-filtré par la source en une seule URL stable :
**FILE hybride**.

**GeoJSON déposé sur le nœud, jamais hybride (2026-11-14)** : un média hybride dont le
connecteur pointe directement vers l'API externe ODS est, à l'affichage de la carte,
proxyé par l'apigateway du nœud (service ``call-service`` du portail) vers cette URL
externe — un bug connu de double-encodage de la query ``where=`` dans
``RerouteToRequestUrlFilter`` y casse systématiquement cet appel (confirmé et corrigé
sur le nœud local de Simon, mais ce correctif n'a pas vocation à être déployé sur tous
les nœuds tiers — un nœud hébergé par un tiers, le cas normal pour un agent municipal,
peut très bien tourner un apigateway non corrigé). Construire le GeoJSON localement et
le déposer comme un fichier normal sur le nœud (comme ``irve.py``) rend la carte
indépendante de ce proxy, quel que soit le nœud. Le contenu lui-même reste fiable (pas
le piège de coordonnées inversées rencontré sur l'IRVE, voir ``irve.py``) : seul le
mode de publication change, pas la donnée.
"""

from __future__ import annotations

import json
import os
from urllib.parse import urlencode

from rudi_harvest_toolkit.description import construire_description_structuree
from rudi_harvest_toolkit.fichier_hybride import construire_media_hybride
from rudi_harvest_toolkit.geojson import AucuneGeometrieValide, construire_feature_collection
from rudi_harvest_toolkit.http import session
from rudi_harvest_toolkit.http_dates import date_dataset_ods
from rudi_harvest_toolkit.pivot import construire_rudi_metadata, media_filtre
from rudi_harvest_toolkit.tabular import iter_lignes_csv

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


def _description_enrichie(commune: dict, code_insee: str) -> str:
    return construire_description_structuree(
        quoi=(
            f"Établissements scolaires (écoles, collèges, lycées) implantés sur le "
            f"territoire de {commune['nom']} ({code_insee})."
        ),
        comment_construit=(
            "Extrait de l'annuaire de l'éducation (data.education.gouv.fr), filtré "
            "par code commune en une seule requête. Export CSV pré-filtré par la "
            "source, publié tel quel."
        ),
        structure_variables=[
            "Identité de l'établissement (nom, type, statut public/privé)",
            "Adresse et coordonnées géographiques",
            "Niveau d'enseignement et secteur (premier/second degré)",
        ],
        frequence_maj=FREQUENCE_MAJ,
        source_label="Ministère de l'Éducation nationale (annuaire de l'éducation)",
        url_source=f"https://data.education.gouv.fr/explore/dataset/{_DATASET_ID}/",
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
    medias = [media]
    fichiers_filtres: list[str] = []

    # GeoJSON construit localement et déposé sur le nœud (jamais hybride, voir le
    # docstring du module) — second téléchargement du même CSV déjà utilisé par le
    # média hybride ci-dessus (coût accepté, fichier filtré donc petit, même choix
    # que irve.py).
    try:
        lignes = list(iter_lignes_csv(url, session_http=session_http))
        fc = construire_feature_collection(
            lignes, champ_lon="longitude", champ_lat="latitude",
            proprietes=["nom_etablissement", "type_etablissement", "statut_public_prive"],
        )
    except AucuneGeometrieValide:
        fc = None
    except Exception as e:  # noqa: BLE001 — carte en bonus, jamais au prix du CSV déjà publiable
        print(
            "[etablissements_scolaires] AVERTISSEMENT : construction du GeoJSON "
            f"impossible ({commune['nom']}) : {e}"
        )
        fc = None

    if fc is not None:
        nb_omises = len(lignes) - len(fc["features"])
        if nb_omises:
            print(
                f"[etablissements_scolaires] AVERTISSEMENT : {nb_omises} "
                f"établissement(s) sans coordonnées exploitables, absent(s) de la "
                f"carte ({commune['nom']})."
            )
        nom_fichier_geojson = f"etablissements_scolaires_{code_insee}.geojson"
        chemin_geojson = os.path.join(dossier_sortie, nom_fichier_geojson)
        os.makedirs(dossier_sortie, exist_ok=True)
        with open(chemin_geojson, "w", encoding="utf-8") as f:
            json.dump(fc, f, ensure_ascii=False)
        # Ordre obligatoire pour valider_alignement_medias() : le média FILE réellement
        # à uploader (GeoJSON) doit précéder le média FILE hybride déjà complet (CSV) —
        # jamais l'inverse (corruption silencieuse, voir rudi_client.py).
        media_geojson = media_filtre(
            local_id, nom_fichier_geojson, commune["nom"],
            caption=f"Fond de carte (GeoJSON) - Établissements scolaires - {commune['nom']}",
        )
        medias = [media_geojson, media]
        fichiers_filtres = [chemin_geojson]

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
            "établissements scolaires", "écoles", "collèges", "lycées",
            commune["nom"], "Éducation nationale",
        ],
        producer=producer,
        url_source=url,
        url_fiche=f"https://data.education.gouv.fr/explore/dataset/{_DATASET_ID}/",
        date_source=date_dataset_ods(_EXPLORE_BASE, session_http=session_http),
        medias=medias,
        contacts_source=contacts,
        geography=geography_pour_commune(commune),
        licence=licence,
    )

    return ResultatConnecteur(
        StatutConnecteur.PUBLIABLE, rudi_metadata=rudi_metadata, fichiers_filtres=fichiers_filtres,
    )


__all__ = ["CLE", "DESCRIPTION_PATRON", "FREQUENCE_MAJ", "SYNOPSIS_PATRON", "THEME", "TITRE", "moissonner"]
