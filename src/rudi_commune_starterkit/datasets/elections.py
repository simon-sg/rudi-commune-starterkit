"""JDD « Résultats élections » — jeu agrégé data.gouv.fr, 56 scrutins, 1999-2026.

**v4, Axe 5 complet (incréments A+B+C — fusion + Parquet, jointure élu/sièges
municipales 2026 T1, glossaire nuance + marqueur sieges_disponibles)** : remplace
l'ancien JDD mono-scrutin (« municipales 2026, 1er tour ») par un historique complet,
construit depuis le jeu agrégé data.gouv.fr
« donnees-des-elections-agregees » (id ``6481e741d4cf002ec0efec9d``, producteur réel :
l'équipe data.gouv.fr, pipeline ouvert à partir des fichiers du Ministère de
l'Intérieur — pas le Ministère lui-même). Couvre municipales (2008 T1 seul puis
2014/2020/2026 T1+T2), législatives, présidentielles, européennes (T1 seul, pas de
second tour pour ce type), régionales, départementales et cantonales (précurseur des
départementales) — 1999 à 2026, vérifié par comptage exhaustif du fichier source.

**Format long** (une ligne = un candidat dans un bureau de vote) — contrairement à
l'ancien JDD, déjà agrégé commune par le Ministère. ``agregation_scrutin.
agreger_long_vers_commune()`` fait l'agrégation bureau → commune (totaux et candidats
séparément, les deux fichiers sources n'ayant pas la même granularité de colonnes).
``agreger_bureau_vers_commune()``/``unpivot_candidats()`` (format large) ne sont pas
utilisées ici : elles restent disponibles pour un éventuel futur scrutin publié dans ce
format.

**Volumétrie assumée, pas un gain** : 232 Mo téléchargés par commune et par run
(Parquet, ~12x plus léger que les CSV sources — 2,38 Go — mais ~16x plus que l'ancien
JDD mono-scrutin, 14 Mo). ``pyarrow`` est désormais une dépendance obligatoire du
toolkit (``rudi_harvest_toolkit.tabular.lire_parquet_filtre()``).

**Limites de couverture** (voir BACKLOG.md « Limites de couverture connues ») :
municipales 2008 partielles (communes >3500 hab. seulement), pas de second tour pour
les européennes, colonnes ``elu``/``sieges_*`` disponibles **seulement** pour les
municipales 2026 des communes pourvues dès le premier tour (jointure
``(code_insee, no_panneau)`` avec la source municipales 2026 T1 actuelle, ``2026_
muni_t2`` et tous les autres scrutins non couverts) — enrichissement optionnel,
jamais bloquant pour le reste du JDD (incrément B).
"""

from __future__ import annotations

import csv
import os
import re

from rudi_harvest_toolkit.contacts import extraire_contacts_datagouv
from rudi_harvest_toolkit.datagouv import get_dataset_metadata, selectionner_ressource
from rudi_harvest_toolkit.description import construire_description_structuree
from rudi_harvest_toolkit.download_cache import telecharger
from rudi_harvest_toolkit.http import session
from rudi_harvest_toolkit.pivot import (
    LICENCES_DATAGOUV_CONNUES,
    construire_licence,
    construire_rudi_metadata,
    media_filtre,
)
from rudi_harvest_toolkit.tabular import iter_lignes_csv, lire_csv_filtre, lire_parquet_filtre

from .. import licences, organisations
from ..agregation_scrutin import (
    agreger_long_vers_commune,
    decomposer_id_election,
    joindre_elu_sieges,
    recalculer_ratios,
)
from ..resultat import ResultatConnecteur, StatutConnecteur
from ._commun import contacts_pour_producer, geography_pour_commune, local_id_jdd

CLE = organisations.ELECTIONS
THEME = "citizenship"
TITRE = "Résultats élections"
SYNOPSIS_PATRON = "Résultats électoraux (toutes élections nationales et locales, 1999-2026) à {commune} ({code_insee})"
DESCRIPTION_PATRON = (
    "Historique des résultats électoraux pour la commune de {commune} ({code_insee}) : "
    "présidentielles, législatives, municipales, européennes, régionales, "
    "départementales et cantonales, de 1999 à 2026, par liste ou candidat. Sourcé "
    "auprès du jeu agrégé data.gouv.fr (pipeline construit à partir des données du "
    "Ministère de l'Intérieur)."
)
FREQUENCE_MAJ = "à chaque élection"

_DATASET_ID = "donnees-des-elections-agregees"
_COLONNE_COMMUNE = "code_commune"

# Incrément B (jointure élu/sièges) : seule source à porter ces colonnes, absentes du
# jeu agrégé — même dataset municipales 2026 T1 que l'ancien JDD mono-scrutin, avant
# l'incrément A. Enrichissement optionnel (voir moissonner()) : ne fait jamais échouer
# tout le run si cette source est indisponible, la fusion (incrément A) reste publiable
# sans elle.
_DATASET_ID_MUNICIPALES_2026 = "elections-municipales-2026-resultats-du-premier-tour"
_MOTIF_RESSOURCE_MUNICIPALES_2026 = r"^Municipales 2026 - R[ée]sultats - Communes_"
_COLONNE_COMMUNE_MUNICIPALES_2026 = "Code commune"
_RE_BLOC_LISTE_MUNICIPALES = re.compile(r"^Libellé de liste (\d+)$")

# Incrément C (glossaire nuance) : 2 versions de nuances.csv coexistent dans le jeu
# (circulaires différentes, mêmes codes bloc/nuance pour l'essentiel) — pas de mode
# selectionner_ressource() combinant titre + la_plus_recente, filtrage manuel sur le
# préfixe de titre + format=csv, puis max par last_modified.
_PREFIXE_RESSOURCE_NUANCES = "Dictionnaire des nuances politiques"

_CHAMPS_TOTAUX = ("inscrits", "abstentions", "votants", "blancs", "nuls", "exprimes")
_CHAMPS_BUREAU_GENERAL = ("code_canton", "libelle_canton", "code_circonscription", "libelle_circonscription")
_CHAMPS_IDENTITE_CANDIDAT = (
    "no_panneau", "nuance", "nom", "prenom", "liste",
    "libelle_abrege_liste", "libelle_etendu_liste",
    *_CHAMPS_BUREAU_GENERAL,
)
_COLONNES_GENERALES = (
    "id_election", "code_commune", "code_bv", "libelle_commune", *_CHAMPS_TOTAUX, *_CHAMPS_BUREAU_GENERAL,
)
_COLONNES_CANDIDATS = (
    "id_election", "code_commune", "code_bv", "voix",
    "no_panneau", "nuance", "nom", "prenom", "liste",
    "libelle_abrege_liste", "libelle_etendu_liste",
)
_COLONNES_RATIOS_COMMUNE = (
    "ratio_abstentions_inscrits", "ratio_votants_inscrits", "ratio_blancs_inscrits",
    "ratio_blancs_votants", "ratio_nuls_inscrits", "ratio_nuls_votants",
    "ratio_exprimes_inscrits", "ratio_exprimes_votants",
)
_COLONNES_CSV = (
    ("annee", "type_election", "tour", "code_commune", "libelle_commune")
    + _CHAMPS_BUREAU_GENERAL
    + ("nuance", "liste", "libelle_abrege_liste", "libelle_etendu_liste", "no_panneau",
       "voix", "ratio_voix_inscrits", "ratio_voix_exprimes")
    + ("elu", "sieges_conseil_municipal", "sieges_conseil_communautaire", "libelle_liste",
       "libelle_abrege", "sieges_disponibles")
    + _CHAMPS_TOTAUX
    + _COLONNES_RATIOS_COMMUNE
)


def _index_elu_sieges(entetes: list[str], lignes_municipales: list[dict]) -> dict:
    """Construit l'index ``(code_insee, no_panneau) -> {...}`` depuis le fichier
    municipales 2026 T1 actuel (13 blocs de colonnes répétées par liste,
    ``Numéro de panneau N``/``Libellé de liste N``/``Sièges au CM N``/
    ``Sièges au CC N``) — même pattern de dépivot que l'ancien ``elections.py`` (avant
    l'incrément A).

    ``elu`` est dérivé de ``sieges_conseil_municipal > 0`` : la colonne ``Elu N`` de la
    source est vide sur l'intégralité du fichier (plan v4, § 5.6), le signal réel est
    porté par les sièges."""
    index = {}
    for ligne in lignes_municipales:
        code_insee = str(ligne.get(_COLONNE_COMMUNE_MUNICIPALES_2026) or "").strip()
        for entete in entetes:
            m = _RE_BLOC_LISTE_MUNICIPALES.match(entete)
            if not m:
                continue
            i = m.group(1)
            libelle = (ligne.get(f"Libellé de liste {i}") or "").strip()
            if not libelle:
                continue
            no_panneau = str(ligne.get(f"Numéro de panneau {i}") or "").strip()
            sieges_cm = _vers_int_ou_zero(ligne.get(f"Sièges au CM {i}"))
            index[(code_insee, no_panneau)] = {
                "libelle_liste": libelle,
                "libelle_abrege": ligne.get(f"Libellé abrégé de liste {i}"),
                "sieges_conseil_municipal": sieges_cm,
                "sieges_conseil_communautaire": _vers_int_ou_zero(ligne.get(f"Sièges au CC {i}")),
                "elu": sieges_cm > 0,
            }
    return index


def _vers_int_ou_zero(valeur) -> int:
    valeur = (valeur or "").strip()
    return int(valeur) if valeur else 0


def _resoudre_ressource_nuances(metadata: dict) -> dict | None:
    """Sélectionne la ressource ``nuances.csv`` la plus récente des 2 qui coexistent
    dans le jeu (circulaires différentes) — ``None`` si aucune (dégradation attendue,
    jamais une exception ici)."""
    candidates = [
        r for r in metadata.get("resources", [])
        if str(r.get("title") or "").startswith(_PREFIXE_RESSOURCE_NUANCES)
        and str(r.get("format") or "").lower() == "csv"
    ]
    if not candidates:
        return None
    return max(candidates, key=lambda r: r.get("last_modified") or "")


def _glossaire_nuances_rencontrees(session_http, metadata: dict, nuances_rencontrees: set[str]) -> dict:
    """Glossaire ``{code_nuance: signification}`` restreint aux codes effectivement
    présents dans le CSV publié pour cette commune — sourcé depuis le fichier officiel
    complet du jeu agrégé (``nuances.csv``, ``libelle_nuance``/``signification``), pas
    une curation manuelle partielle (plan v4, § 5.8) : le filtrage par commune réduit
    seulement l'affichage, pas la source, qui reste le fichier complet et faisant
    autorité."""
    if not nuances_rencontrees:
        return {}
    ressource = _resoudre_ressource_nuances(metadata)
    if ressource is None:
        return {}
    glossaire = {}
    for ligne in iter_lignes_csv(ressource["url"], session_http=session_http):
        code = (ligne.get("libelle_nuance") or "").strip()
        if code in nuances_rencontrees and code not in glossaire:
            glossaire[code] = (ligne.get("signification") or "").strip()
    return glossaire


def _enrichir_canton_circonscription(lignes_candidats: list[dict], lignes_generales: list[dict]) -> list[dict]:
    """Joint code_canton/libelle_canton/code_circonscription/libelle_circonscription
    (présents uniquement dans general_results) sur les lignes candidat, au niveau
    bureau (code_bv) — avant l'agrégation commune, pour ne jamais perdre l'information
    d'un découpage électoral différent entre bureaux d'une même commune."""
    lookup = {
        (l.get("id_election"), l.get("code_bv")): {c: l.get(c) for c in _CHAMPS_BUREAU_GENERAL}
        for l in lignes_generales
    }
    vide = {c: None for c in _CHAMPS_BUREAU_GENERAL}
    return [
        {**l, **lookup.get((l.get("id_election"), l.get("code_bv")), vide)}
        for l in lignes_candidats
    ]


def _lignes_csv(candidats_agreges: list[dict], totaux_agreges: list[dict], commune: dict) -> list[dict]:
    totaux_par_id = {t["id_election"]: t for t in totaux_agreges}
    lignes = []
    for cand in candidats_agreges:
        id_el = cand["id_election"]
        totaux = totaux_par_id.get(id_el)
        decomp = decomposer_id_election(id_el)
        ratios_commune = recalculer_ratios(totaux) if totaux else {c: None for c in _COLONNES_RATIOS_COMMUNE}
        inscrits = (totaux or {}).get("inscrits") or 0
        exprimes = (totaux or {}).get("exprimes") or 0
        voix = cand.get("voix") or 0
        lignes.append({
            "annee": decomp["annee"], "type_election": decomp["type_election"], "tour": decomp["tour"],
            "code_commune": cand["code_insee"], "libelle_commune": commune["nom"],
            **{c: cand.get(c) for c in _CHAMPS_BUREAU_GENERAL},
            "nuance": cand.get("nuance"), "liste": cand.get("liste"),
            "libelle_abrege_liste": cand.get("libelle_abrege_liste"),
            "libelle_etendu_liste": cand.get("libelle_etendu_liste"),
            "no_panneau": cand.get("no_panneau"), "voix": voix,
            "ratio_voix_inscrits": round(voix / inscrits, 4) if inscrits else None,
            "ratio_voix_exprimes": round(voix / exprimes, 4) if exprimes else None,
            "elu": cand.get("elu"),
            "sieges_conseil_municipal": cand.get("sieges_conseil_municipal"),
            "sieges_conseil_communautaire": cand.get("sieges_conseil_communautaire"),
            "libelle_liste": cand.get("libelle_liste"),
            "libelle_abrege": cand.get("libelle_abrege"),
            "sieges_disponibles": "sieges_conseil_municipal" in cand,
            **{c: (totaux or {}).get(c) for c in _CHAMPS_TOTAUX},
            **ratios_commune,
        })
    lignes.sort(key=lambda r: (r["annee"], r["type_election"], r["tour"], str(r.get("no_panneau") or "")))
    return lignes


def _description_enrichie(
    commune: dict, code_insee: str, types_trouves: list[str], glossaire_nuances: dict,
) -> str:
    return construire_description_structuree(
        quoi=(
            f"Historique des résultats électoraux pour {commune['nom']} ({code_insee}) : "
            f"{', '.join(sorted(types_trouves))}, de 1999 à 2026, par liste ou candidat."
        ),
        comment_construit=(
            "Extrait du jeu agrégé data.gouv.fr (fichiers Parquet « Résultats généraux » "
            "et « Résultats par candidat »), filtré sur le code commune, agrégé au niveau "
            "commune (group by élection + identité candidat, sommé depuis le niveau bureau "
            "de vote). Mode d'emploi : filtrer la colonne type_election (ex. "
            "« Présidentielles ») et annee (ex. « 2022 ») pour un scrutin donné, tour "
            "(1 ou 2) pour le tour. Exemple : type_election=Présidentielles et "
            "annee=2022 pour la présidentielle 2022 ; tour=2 pour tous les seconds tours."
        ),
        structure_variables=[
            "Identité du scrutin : annee, type_election, tour",
            "Totaux de la commune (inscrits, votants, abstentions, exprimés, blancs, "
            "nuls) et leurs ratios",
            "Par liste ou candidat : nuance, libellé de liste, numéro de panneau, "
            "voix et ratios (inscrits, exprimés)",
            "Élu et sièges (conseil municipal, conseil communautaire) — municipales "
            "2026 premier tour seulement, voir limites ci-dessous",
            "Découpage électoral du bureau : canton, circonscription (quand "
            "applicable)",
        ],
        limites=[
            "Municipales 2008 : communes de plus de 3500 habitants seulement "
            "(partiel, pas disponible pour les communes plus petites cette année-là).",
            "Européennes : premier tour seul (pas de second tour pour ce type "
            "d'élection).",
            "Élu/sièges (conseil municipal, conseil communautaire) disponibles "
            "seulement pour les municipales 2026, et seulement pour les communes "
            "pourvues dès le premier tour (colonne sieges_disponibles = vrai) — le "
            "second tour (2026_muni_t2) et tous les autres scrutins n'ont pas de "
            "sièges exploitables dans la source actuelle (sieges_disponibles = faux).",
        ],
        glossaire=glossaire_nuances or None,
        frequence_maj=FREQUENCE_MAJ,
        source_label="data.gouv.fr (jeu agrégé, à partir des données du Ministère de l'Intérieur)",
        url_source=f"https://www.data.gouv.fr/fr/datasets/{_DATASET_ID}/",
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
        ressource_generale = selectionner_ressource(
            metadata, motif_nom=r"^Résultats généraux$", format="parquet",
        )
        ressource_candidats = selectionner_ressource(
            metadata, motif_nom=r"^Résultats par candidat$", format="parquet",
        )
        dossier_cache = os.path.join(dossier_sortie, ".cache_elections")
        chemin_general = telecharger(ressource_generale["url"], dossier=dossier_cache, session_http=session_http)
        chemin_candidats = telecharger(ressource_candidats["url"], dossier=dossier_cache, session_http=session_http)
        lignes_generales, _ = lire_parquet_filtre(
            chemin_general, _COLONNE_COMMUNE, code_insee, colonnes=list(_COLONNES_GENERALES),
        )
        lignes_candidats_brutes, _ = lire_parquet_filtre(
            chemin_candidats, _COLONNE_COMMUNE, code_insee, colonnes=list(_COLONNES_CANDIDATS),
        )
    except Exception as e:  # noqa: BLE001
        return ResultatConnecteur(StatutConnecteur.ECHEC, message=str(e))

    if not lignes_generales or not lignes_candidats_brutes:
        return ResultatConnecteur(StatutConnecteur.VIDE)

    try:
        licence_dynamique = construire_licence(
            metadata.get("license"), metadata.get("page"), LICENCES_DATAGOUV_CONNUES,
        )
        licence = licences.licence_pour_jdd(CLE, licence_dynamique=licence_dynamique)
    except licences.LicenceInconnueError as e:
        return ResultatConnecteur(StatutConnecteur.ECHEC, message=str(e))

    try:
        lignes_candidats = _enrichir_canton_circonscription(lignes_candidats_brutes, lignes_generales)
        totaux_agreges = agreger_long_vers_commune(lignes_generales, code_insee, champs_totaux=_CHAMPS_TOTAUX)
        candidats_agreges = agreger_long_vers_commune(
            lignes_candidats, code_insee, champs_identite_candidat=_CHAMPS_IDENTITE_CANDIDAT,
        )
    except Exception as e:  # noqa: BLE001
        return ResultatConnecteur(StatutConnecteur.ECHEC, message=str(e))

    # Incrément B : enrichissement optionnel (élu/sièges, municipales 2026 T1
    # seulement) — ne fait jamais échouer le run, la fusion (incrément A) a déjà toute
    # sa valeur sans cette jointure.
    try:
        metadata_municipales = get_dataset_metadata(_DATASET_ID_MUNICIPALES_2026, session_http=session_http)
        ressource_municipales = selectionner_ressource(
            metadata_municipales, motif_nom=_MOTIF_RESSOURCE_MUNICIPALES_2026,
        )
        chemin_municipales = telecharger(
            ressource_municipales["url"], dossier=dossier_cache, session_http=session_http,
        )
        lignes_municipales, entetes_municipales = lire_csv_filtre(
            chemin_municipales, _COLONNE_COMMUNE_MUNICIPALES_2026, code_insee,
        )
        index_elu_sieges = _index_elu_sieges(entetes_municipales, lignes_municipales)
    except Exception as e:  # noqa: BLE001
        print(f"[elections] AVERTISSEMENT : jointure élu/sièges indisponible ({commune['nom']}) : {e}")
        index_elu_sieges = {}

    candidats_agreges = joindre_elu_sieges(candidats_agreges, index_elu_sieges)

    try:
        lignes_csv = _lignes_csv(candidats_agreges, totaux_agreges, commune)
    except Exception as e:  # noqa: BLE001
        return ResultatConnecteur(StatutConnecteur.ECHEC, message=str(e))

    types_trouves = sorted({l["type_election"] for l in lignes_csv})

    # Incrément C : glossaire nuance, enrichissement optionnel (jamais bloquant).
    try:
        nuances_rencontrees = {l["nuance"] for l in lignes_csv if l.get("nuance")}
        glossaire_nuances = _glossaire_nuances_rencontrees(session_http, metadata, nuances_rencontrees)
    except Exception as e:  # noqa: BLE001
        print(f"[elections] AVERTISSEMENT : glossaire nuances indisponible ({commune['nom']}) : {e}")
        glossaire_nuances = {}

    local_id = local_id_jdd(CLE, code_insee)
    nom_fichier = f"elections_{code_insee}.csv"
    chemin = os.path.join(dossier_sortie, nom_fichier)
    os.makedirs(dossier_sortie, exist_ok=True)
    with open(chemin, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=_COLONNES_CSV, delimiter=";")
        writer.writeheader()
        writer.writerows(lignes_csv)

    producer = organisations.resoudre_producer(
        CLE, mode_producer, commune, description_commune=description_commune,
    )
    contacts = contacts_pour_producer(
        CLE, producer, commune, email_commune=contact_email_commune,
        contacts_dynamiques=extraire_contacts_datagouv(metadata),
    )

    media = media_filtre(
        local_id, nom_fichier, commune["nom"],
        caption=f"Résultats électoraux (historique multi-scrutins) - {commune['nom']} (CSV)",
    )

    date_source = max(
        (r.get("last_modified") for r in (ressource_generale, ressource_candidats) if r.get("last_modified")),
        default=None,
    )

    rudi_metadata = construire_rudi_metadata(
        local_id=local_id,
        titre=f"{TITRE} - {commune['nom']} ({code_insee})",
        synopsis=SYNOPSIS_PATRON.format(commune=commune["nom"], code_insee=code_insee)[:150],
        description=_description_enrichie(commune, code_insee, types_trouves, glossaire_nuances),
        theme=THEME,
        keywords=[
            "élections", "résultats électoraux", "historique électoral",
            "présidentielle", "législatives", "municipales", "européennes",
            "régionales", "départementales", "cantonales",
            commune["nom"], "data.gouv.fr",
        ],
        producer=producer,
        url_source=f"https://www.data.gouv.fr/fr/datasets/{_DATASET_ID}/",
        url_fiche=f"https://www.data.gouv.fr/fr/datasets/{_DATASET_ID}/",
        medias=[media],
        contacts_source=contacts,
        geography=geography_pour_commune(commune),
        licence=licence,
        date_source=date_source,
    )

    return ResultatConnecteur(
        StatutConnecteur.PUBLIABLE, rudi_metadata=rudi_metadata, fichiers_filtres=[chemin],
    )


__all__ = ["CLE", "DESCRIPTION_PATRON", "FREQUENCE_MAJ", "SYNOPSIS_PATRON", "THEME", "TITRE", "moissonner"]
