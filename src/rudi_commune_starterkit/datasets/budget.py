"""JDD « Budget communal » — DGFiP, « Comptes individuels des communes » (data.economie.gouv.fr).

**v4, Axe 4 (historique complet, 2026-11-11)** : remplace l'ancienne version
(dernier exercice disponible seulement, 2023-2024, en FILE hybride passthrough) par
l'historique complet disponible : 12 datasets Opendatasoft distincts, chacun couvrant
un ou plusieurs exercices, **vérifiés en direct** et couvrant sans trou ni
recoupement 2000 à 2025 (voir ``_DATASET_IDS`` ci-dessous et ``BACKLOG.md`` pour le
détail de la vérification — corrige une première conclusion erronée de cette même
recherche, qui avait cru la couverture limitée à 2008-2025 en ne vérifiant que
l'existence des datasets sans lire leur contenu réel : le dataset nommé ``2008``
contient en réalité les exercices 2000 à 2008).

Chaque dataset a son propre schéma (de 173 à 254 colonnes selon l'exercice,
nomenclature DGFiP historique volontairement cryptique : ``prod``, ``impo1``,
``dgf``...). Ce module **n'est plus un FILE hybride passthrough** : il interroge les
12 datasets, harmonise les schémas par nom de colonne (union, une ligne par exercice
réellement trouvé pour la commune) et écrit un fichier CSV local unique — changement
de modèle de média nécessaire par cette union (un passthrough ne peut pointer qu'un
seul dataset). Glossaire des codes les plus structurants (pas la nomenclature
complète) sourcé depuis la fiche de métadonnées DGFiP (``Maquette_commune.ods``,
publiée par chaque dataset) — jamais recopié de mémoire.

Filtré par ``dep``/``icom`` (codes DGFiP zero-paddés, dérivés du code INSEE : ``dep``
= 2 premiers caractères paddés à 3, ``icom`` = 3 derniers caractères — confirmé
Corse-safe : Ajaccio donne ``dep="02A"``). Mainland + Corse seulement, outre-mer non
supporté (encodage ``dep``/``icom`` non vérifié pour ces départements).
"""

from __future__ import annotations

import csv
import os

from rudi_harvest_toolkit.description import construire_description_structuree
from rudi_harvest_toolkit.http import session
from rudi_harvest_toolkit.http_dates import date_dataset_ods
from rudi_harvest_toolkit.pivot import construire_rudi_metadata, media_filtre

from .. import licences, organisations
from ..resultat import ResultatConnecteur, StatutConnecteur
from ._commun import contacts_pour_producer, geography_pour_commune, local_id_jdd

CLE = organisations.BUDGET
THEME = "economy"
TITRE = "Budget communal"
SYNOPSIS_PATRON = "Comptes individuels de la commune de {commune} ({code_insee})"
DESCRIPTION_PATRON = (
    "Comptes individuels de la commune de {commune} ({code_insee}) - recettes, dépenses "
    "et dotations, sourcés auprès de la DGFiP (Direction générale des Finances publiques) "
    "via data.economie.gouv.fr. Historique complet (2000-2025, selon disponibilité pour "
    "la commune)."
)
FREQUENCE_MAJ = "annuelle"

# Vérifiés en direct le 2026-11-11 : couvrent sans trou ni recoupement les exercices
# 2000 à 2025 (le champ "an" de chaque enregistrement porte l'exercice réel, y compris
# à l'intérieur d'un dataset nommé par une seule année ou une plage — ne jamais
# déduire l'exercice du nom du dataset, toujours du champ "an" de la ligne).
_DATASET_IDS = (
    "comptes-individuels-des-communes-fichier-global-2008",  # contient an=2000..2008
    "comptes-individuels-des-communes-fichier-global-20090",  # typo source : "20090"
    "comptes-individuels-des-communes-fichier-global-2010",
    "comptes-individuels-des-communes-fichier-global-2011-2015",
    "comptes-individuels-des-communes-fichier-global-2016",
    "comptes-individuels-des-communes-fichier-global-2017",
    "comptes-individuels-des-communes-fichier-global-2018",
    "comptes-individuels-des-communes-fichier-global-2019-2020",
    "comptes-individuels-des-communes-fichier-global-2021",
    "comptes-individuels-des-communes-fichier-global-2022",
    "comptes-individuels-des-communes-fichier-global-2023-2024",
    "comptes-individuels-des-communes-fichier-global-2025",
)
_EXPLORE_BASE_PATRON = "https://data.economie.gouv.fr/api/explore/v2.1/catalog/datasets/{id}"
_URL_FAMILLE = "https://www.data.gouv.fr/datasets/comptes-individuels-des-communes/"

# Colonnes en tête, ordre fixe pour la lisibilité (identité) ; le reste suit par ordre
# alphabétique, dépendant des exercices réellement trouvés pour la commune.
_COLONNES_PRIORITAIRES = ("an", "dep", "icom", "inom", "reg", "pop1", "nomsst1", "nomsst2")

# Glossaire des codes les plus structurants, sourcé depuis la fiche de métadonnées
# DGFiP ("Maquette_commune.ods", publiée par chaque dataset, url_fiche) — pas la
# nomenclature complète (plusieurs centaines d'entrées avec les variantes par
# préfixe, voir la note ci-dessous). Restreint à l'affichage aux codes effectivement
# présents dans le CSV publié pour la commune (comme le glossaire nuance d'elections.py).
_GLOSSAIRE_CODES = {
    "an": "Exercice (année)",
    "dep": "Code département (nomenclature DGFiP)",
    "icom": "Code commune (nomenclature DGFiP, dérivé du code INSEE)",
    "inom": "Libellé de la commune",
    "reg": "Code région",
    "pop1": "Population légale au 1er janvier de l'exercice",
    "nomsst1": "Strate de population de la commune",
    "nomsst2": "Type de groupement d'appartenance (EPCI)",
    "prod": "Total des produits de fonctionnement (A)",
    "impo1": "Impôts locaux",
    "impo2": "Autres impôts et taxes",
    "dgf": "Dotation globale de fonctionnement",
    "charge": "Total des charges de fonctionnement (B)",
    "perso": "Charges de personnel",
    "achat": "Achats et charges externes",
    "fin": "Charges financières",
    "cont": "Contingents",
    "subv": "Subventions versées",
    "res1": "Résultat comptable (= A - B)",
    "potfis": "Potentiel fiscal",
    "pth": "Produits de la taxe d'habitation",
    "pfb": "Produits du foncier bâti",
    "pfnb": "Produits du foncier non bâti",
    "ptp": "Produits de la taxe professionnelle",
    "recinv": "Total des ressources d'investissement (C)",
    "emp": "Emprunts bancaires et dettes assimilées",
    "subr": "Subventions reçues",
    "fctva": "Fonds de compensation de la taxe sur la valeur ajoutée (FCTVA)",
    "raff": "Retour de biens affectés, concédés",
    "depinv": "Total des emplois d'investissement (D)",
    "equip": "Dépenses d'équipement",
    "remb": "Remboursement d'emprunts et dettes assimilées",
    "repart": "Charges à répartir",
    "daff": "Immobilisations affectées, concédées",
    "bf1": "Besoin ou capacité de financement résiduel d'investissement (= D - C)",
    "solde": "Solde des opérations pour le compte de tiers",
    "bf2": "Besoin ou capacité de financement de la section d'investissement",
    "res2": "Résultat d'ensemble",
    "ebf": "Excédent brut de fonctionnement",
    "caf": "Capacité d'autofinancement (CAF)",
    "cafn": "CAF nette du remboursement en capital des emprunts",
    "dette": "Encours total de la dette au 31 décembre",
    "annu": "Annuité de la dette",
    "avance": "Avances du Trésor au 31 décembre",
    "fdr": "Fonds de roulement",
    "préfixes f/m/r/rm": (
        "Variantes de chaque code ci-dessus : f = euros par habitant, m = moyenne de "
        "la strate, r = ratio ou taux, rm = ratio ou taux moyen de la strate "
        "(ex. fprod, mprod, rimpo1 : même grandeur que le code de base)"
    ),
}


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


def _lignes_dataset(dataset_id: str, where: str, *, session_http) -> list[dict]:
    """Toutes les lignes (pagination complète, jamais tronquée silencieusement) d'un
    dataset Opendatasoft filtré par ``where``."""
    base = _EXPLORE_BASE_PATRON.format(id=dataset_id)
    lignes: list[dict] = []
    offset = 0
    limite = 100
    while True:
        reponse = session_http.get(
            f"{base}/records",
            params={"where": where, "limit": limite, "offset": offset},
            timeout=30,
        )
        reponse.raise_for_status()
        donnees = reponse.json()
        resultats = donnees.get("results", [])
        lignes.extend(resultats)
        if not resultats or len(lignes) >= donnees.get("total_count", len(lignes)):
            break
        offset += limite
    return lignes


def _entetes_harmonisees(lignes: list[dict]) -> list[str]:
    """Union des colonnes réellement présentes dans les exercices trouvés pour la
    commune, colonnes d'identité en tête puis le reste par ordre alphabétique —
    harmonisation par nom de colonne, jamais par position (les schémas DGFiP
    divergent d'un exercice à l'autre)."""
    vues: set[str] = set()
    for ligne in lignes:
        vues |= set(ligne.keys())
    reste = sorted(vues - set(_COLONNES_PRIORITAIRES))
    return [c for c in _COLONNES_PRIORITAIRES if c in vues] + reste


def _glossaire_colonnes(entetes: list[str]) -> dict[str, str]:
    """Glossaire restreint aux codes effectivement publiés pour cette commune (pas la
    table complète) — les variantes f/m/r/rm d'un code déjà documenté n'ajoutent pas
    une entrée séparée (couvertes par la note générique)."""
    glossaire = {code: libelle for code, libelle in _GLOSSAIRE_CODES.items() if code in entetes}
    codes_documentes = set(_GLOSSAIRE_CODES) - {"préfixes f/m/r/rm"}
    a_une_variante = any(
        (colonne[:2] == "rm" and colonne[2:] in codes_documentes)
        or (colonne[:1] in ("f", "m", "r") and colonne[1:] in codes_documentes)
        for colonne in entetes
    )
    if a_une_variante:
        glossaire["préfixes f/m/r/rm"] = _GLOSSAIRE_CODES["préfixes f/m/r/rm"]
    return glossaire


def _description_enrichie(
    commune: dict, code_insee: str, annees_texte: str, glossaire: dict[str, str],
    exercices_indisponibles: list[str],
) -> str:
    limites = [
        "Historique limité aux exercices effectivement publiés par la DGFiP pour "
        "cette commune (fusions, créations de commune : certains exercices anciens "
        "peuvent être absents).",
        "Nomenclature DGFiP volontairement cryptique : seuls les codes les plus "
        "structurants sont glossés ci-dessus, pas l'intégralité des colonnes "
        "publiées (jusqu'à 254 colonnes selon l'exercice).",
    ]
    if exercices_indisponibles:
        limites.append(
            "Exercice(s) non interrogeable(s) pour cette commune lors de cette "
            "collecte (source indisponible) : " + ", ".join(exercices_indisponibles) + "."
        )
    return construire_description_structuree(
        quoi=(
            f"Comptes individuels de la commune de {commune['nom']} ({code_insee}) : "
            f"recettes, dépenses et dotations, exercices disponibles ({annees_texte})."
        ),
        comment_construit=(
            "Union de 12 fichiers Opendatasoft distincts de la DGFiP (data.economie."
            "gouv.fr, « comptes individuels des communes », un fichier par exercice "
            "ou groupe d'exercices), filtrés par code département (dep) et code "
            "commune (icom) au format DGFiP historique dérivé du code INSEE, et "
            "harmonisés par nom de colonne (une ligne par exercice réellement trouvé)."
        ),
        structure_variables=[
            "Identifiants (an = exercice, dep, icom, inom = nom de la commune)",
            "Recettes de fonctionnement et d'investissement (prod, recinv, ...)",
            "Dépenses de fonctionnement et d'investissement (charge, depinv, ...)",
            "Dotations globales de fonctionnement (dgf), endettement (dette, caf, ...)",
        ],
        frequence_maj=FREQUENCE_MAJ,
        source_label="DGFiP (comptes individuels des communes)",
        url_source=_URL_FAMILLE,
        glossaire=glossaire or None,
        limites=limites,
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
        dep, icom = _dep_icom(code_insee)
    except DepartementNonSupporte as e:
        return ResultatConnecteur(StatutConnecteur.ECHEC, message=str(e))
    where = f"dep='{dep}' AND icom='{icom}'"

    lignes_par_exercice: dict[str, dict] = {}
    exercices_indisponibles: list[str] = []
    datasets_contribues: list[str] = []
    for dataset_id in _DATASET_IDS:
        try:
            lignes = _lignes_dataset(dataset_id, where, session_http=session_http)
        except Exception as e:  # noqa: BLE001
            exercices_indisponibles.append(dataset_id)
            print(
                f"[budget] AVERTISSEMENT : dataset {dataset_id} indisponible "
                f"({commune['nom']}) : {e}"
            )
            continue
        if lignes:
            datasets_contribues.append(dataset_id)
        for ligne in lignes:
            an = ligne.get("an")
            if not an:
                continue
            if an in lignes_par_exercice:
                print(
                    f"[budget] AVERTISSEMENT : exercice {an} présent dans plusieurs "
                    f"datasets pour {commune['nom']} - dernier conservé."
                )
            lignes_par_exercice[an] = ligne

    if len(exercices_indisponibles) == len(_DATASET_IDS):
        return ResultatConnecteur(
            StatutConnecteur.ECHEC,
            message="Tous les datasets DGFiP de comptes communaux sont indisponibles.",
        )

    if not lignes_par_exercice:
        return ResultatConnecteur(StatutConnecteur.VIDE)

    exercices_trouves = sorted(lignes_par_exercice)
    lignes_triees = [lignes_par_exercice[an] for an in exercices_trouves]
    entetes = _entetes_harmonisees(lignes_triees)

    local_id = local_id_jdd(CLE, code_insee)
    nom_fichier = f"budget_{code_insee}.csv"
    chemin = os.path.join(dossier_sortie, nom_fichier)
    os.makedirs(dossier_sortie, exist_ok=True)
    with open(chemin, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=entetes, delimiter=";", restval="", extrasaction="ignore")
        writer.writeheader()
        writer.writerows(lignes_triees)

    producer = organisations.resoudre_producer(
        CLE, mode_producer, commune, description_commune=description_commune,
    )
    contacts = contacts_pour_producer(CLE, producer, commune, email_commune=contact_email_commune)

    annees_texte = ", ".join(exercices_trouves)
    media = media_filtre(
        local_id, nom_fichier, commune["nom"],
        caption=f"Comptes individuels de la commune, {annees_texte} - {commune['nom']} (CSV)",
    )

    try:
        licence = licences.licence_pour_jdd(CLE)
    except licences.LicenceInconnueError as e:
        return ResultatConnecteur(StatutConnecteur.ECHEC, message=str(e))

    date_source = None
    for dataset_id in datasets_contribues:
        base = _EXPLORE_BASE_PATRON.format(id=dataset_id)
        date_dataset = date_dataset_ods(base, session_http=session_http)
        if date_dataset and (date_source is None or date_dataset > date_source):
            date_source = date_dataset

    rudi_metadata = construire_rudi_metadata(
        local_id=local_id,
        titre=f"{TITRE} - {commune['nom']} ({code_insee})",
        synopsis=SYNOPSIS_PATRON.format(commune=commune["nom"], code_insee=code_insee)[:150],
        description=_description_enrichie(
            commune, code_insee, annees_texte, _glossaire_colonnes(entetes), exercices_indisponibles,
        ),
        theme=THEME,
        keywords=[
            "budget communal", "finances locales", "comptes communaux", "fiscalité",
            "historique", commune["nom"], "DGFiP",
        ],
        producer=producer,
        url_source=_URL_FAMILLE,
        url_fiche=_URL_FAMILLE,
        date_source=date_source,
        medias=[media],
        contacts_source=contacts,
        geography=geography_pour_commune(commune),
        licence=licence,
    )

    return ResultatConnecteur(
        StatutConnecteur.PUBLIABLE, rudi_metadata=rudi_metadata, fichiers_filtres=[chemin],
    )


__all__ = [
    "CLE", "DepartementNonSupporte", "DESCRIPTION_PATRON", "FREQUENCE_MAJ",
    "SYNOPSIS_PATRON", "THEME", "TITRE", "moissonner",
]
