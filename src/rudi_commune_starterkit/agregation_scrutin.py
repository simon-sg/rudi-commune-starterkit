"""Agrégation bureau de vote → commune pour un scrutin électoral (format large).

Le format usuel des fichiers de résultats électoraux français est « large » : une ligne
par bureau de vote, des colonnes de totaux (inscrits/votants/abstentions/blancs/nuls/
exprimés), puis pour chaque candidat ou liste un groupe de colonnes répété (nom, voix,
pourcentage...). Le padding du code commune est incohérent selon les millésimes (avec ou
sans le département en tête) — voir le plan, § Corrections factuelles.

Ce module ne connaît aucun format de source précis (le scrutin exact du v1 n'est pas
encore choisi au moment de son écriture) : il prend en entrée des lignes déjà lues
(``list[dict]``, une ligne = un bureau) et des paramètres explicites décrivant quelles
colonnes contiennent quoi — c'est au module ``datasets/elections.py`` de les fournir une
fois le scrutin choisi.
"""

from __future__ import annotations

import re

_LARGEUR_CODE_INSEE = 5

# Table des types d'élection rencontrés dans id_election ({annee}_{type}_t{tour}),
# vérifiée par comptage exhaustif du jeu agrégé « donnees-des-elections-agregees »
# (plan v4, § 5.4/5.5) — 56 scrutins, 1999-2026, tous couverts par ces 7 types.
TYPES_ELECTION = {
    "muni": "Municipales",
    "legi": "Législatives",
    "pres": "Présidentielles",
    "euro": "Européennes",
    "regi": "Régionales",
    "dpmt": "Départementales",
    "cant": "Cantonales",
}

_RE_ID_ELECTION = re.compile(r"^(\d{4})_([a-z]+)_t(\d+)$")


class CodeCommuneInvalide(ValueError):
    """Code commune électoral non normalisable, ou aucun bureau trouvé pour ce code."""


class TypeElectionInconnu(ValueError):
    """``id_election`` mal formé, ou dont le type ne figure pas dans :data:`TYPES_ELECTION`
    — jamais laissé passer en silence (détecte un 8e type si la source évolue)."""


def decomposer_id_election(id_election: object) -> dict:
    """Décompose ``id_election`` (``{annee}_{type}_t{tour}``, ex. ``2026_muni_t2``) en
    ``{"annee": str, "type_election": str (libellé humain), "tour": int}``.

    Lève :class:`TypeElectionInconnu` si le format ne correspond pas, ou si le type
    brut n'est pas dans :data:`TYPES_ELECTION`."""
    m = _RE_ID_ELECTION.match(str(id_election or ""))
    if not m:
        raise TypeElectionInconnu(f"id_election mal formé : {id_election!r}")
    annee, type_brut, tour = m.groups()
    if type_brut not in TYPES_ELECTION:
        raise TypeElectionInconnu(
            f"type d'élection inconnu : {type_brut!r} (id_election={id_election!r})"
        )
    return {"annee": annee, "type_election": TYPES_ELECTION[type_brut], "tour": int(tour)}


def normaliser_code_commune(code: object) -> str:
    """Zero-pad un code commune électoral à 5 caractères — sauf Corse (``2A``/``2B``,
    déjà sur 5 caractères, jamais traités comme un entier)."""
    if code is None:
        raise CodeCommuneInvalide("code commune manquant")
    code = str(code).strip().upper()
    if not code:
        raise CodeCommuneInvalide("code commune vide")
    if code[:2] in ("2A", "2B"):
        if len(code) != _LARGEUR_CODE_INSEE:
            raise CodeCommuneInvalide(f"code commune corse mal formé : {code!r}")
        return code
    if not code.isdigit():
        raise CodeCommuneInvalide(f"code commune non numérique : {code!r}")
    return code.zfill(_LARGEUR_CODE_INSEE)


def _vers_int(valeur: object) -> int:
    if valeur is None:
        return 0
    s = str(valeur).strip().replace(" ", "").replace("\xa0", "")
    if not s:
        return 0
    try:
        return int(float(s.replace(",", ".")))
    except ValueError:
        raise ValueError(f"valeur numérique de scrutin attendue, reçu {valeur!r}") from None


def unpivot_candidats(ligne: dict, colonnes_candidats: dict[str, str]) -> list[dict]:
    """Convertit une ligne bureau (format large) en lignes ``{candidat, voix}`` (format long).

    ``colonnes_candidats`` : ``{nom_candidat_ou_liste: nom_colonne_voix}``.
    """
    return [
        {"candidat": nom, "voix": _vers_int(ligne.get(colonne))}
        for nom, colonne in colonnes_candidats.items()
    ]


def agreger_bureau_vers_commune(
    lignes_bureau: list[dict],
    code_insee: str,
    *,
    champ_code_commune: str,
    colonnes_candidats: dict[str, str],
    champs_totaux: dict[str, str] | None = None,
) -> dict:
    """Agrège les lignes bureau vers la commune ``code_insee``.

    - ``champ_code_commune`` : nom de la colonne portant le code commune dans
      ``lignes_bureau`` (normalisé via :func:`normaliser_code_commune` avant comparaison,
      pour absorber les incohérences de padding entre millésimes).
    - ``colonnes_candidats`` : ``{nom_candidat_ou_liste: nom_colonne_voix}``.
    - ``champs_totaux`` : ``{cle_sortie: nom_colonne}`` optionnel (ex.
      ``{"inscrits": "Inscrits", "votants": "Votants", "exprimes": "Exprimés"}``).

    Retourne ``{"code_insee", "nb_bureaux", "candidats": {nom: voix}, **totaux}``.

    Lève :class:`CodeCommuneInvalide` si **aucun** bureau ne correspond au code — distinct
    d'une commune dont les bureaux existent mais dont les totaux sont nuls, qui retourne un
    résultat normal avec des valeurs à 0.
    """
    cible = normaliser_code_commune(code_insee)
    lignes = [
        ligne for ligne in lignes_bureau
        if normaliser_code_commune(ligne.get(champ_code_commune)) == cible
    ]
    if not lignes:
        raise CodeCommuneInvalide(
            f"aucun bureau trouvé pour le code commune {code_insee!r} (normalisé {cible!r})"
        )

    candidats = {nom: 0 for nom in colonnes_candidats}
    for ligne in lignes:
        for nom, colonne in colonnes_candidats.items():
            candidats[nom] += _vers_int(ligne.get(colonne))

    totaux = {
        cle: sum(_vers_int(ligne.get(colonne)) for ligne in lignes)
        for cle, colonne in (champs_totaux or {}).items()
    }

    return {
        "code_insee": cible,
        "nb_bureaux": len(lignes),
        "candidats": candidats,
        **totaux,
    }


def recalculer_ratios(totaux: dict) -> dict:
    """Recalcule les ratios dérivés des totaux d'une élection (jamais moyennés depuis
    les ratios bureau du fichier source — recalculés après sommation, seule méthode
    exacte).

    ``totaux`` : ``{"inscrits", "abstentions", "votants", "blancs", "nuls",
    "exprimes"}``. ``None`` sur toute division par zéro (``inscrits``/``votants`` à 0) —
    jamais ``ZeroDivisionError`` en plein ``moissonner()``."""
    inscrits = totaux.get("inscrits") or 0
    votants = totaux.get("votants") or 0

    def _ratio(numerateur, denominateur):
        return round(numerateur / denominateur, 4) if denominateur else None

    return {
        "ratio_abstentions_inscrits": _ratio(totaux.get("abstentions") or 0, inscrits),
        "ratio_votants_inscrits": _ratio(votants, inscrits),
        "ratio_blancs_inscrits": _ratio(totaux.get("blancs") or 0, inscrits),
        "ratio_blancs_votants": _ratio(totaux.get("blancs") or 0, votants),
        "ratio_nuls_inscrits": _ratio(totaux.get("nuls") or 0, inscrits),
        "ratio_nuls_votants": _ratio(totaux.get("nuls") or 0, votants),
        "ratio_exprimes_inscrits": _ratio(totaux.get("exprimes") or 0, inscrits),
        "ratio_exprimes_votants": _ratio(totaux.get("exprimes") or 0, votants),
    }


def agreger_long_vers_commune(
    lignes: list[dict],
    code_insee: str,
    *,
    champ_code_commune: str = "code_commune",
    champ_election: str = "id_election",
    champs_totaux: tuple[str, ...] = (),
    champs_identite_candidat: tuple[str, ...] = (),
) -> list[dict]:
    """Agrège ``general_results``/``candidats_results`` (jeu agrégé « donnees-des-
    elections-agregees », format long, plusieurs élections) vers la commune
    ``code_insee`` — une entrée par ``(id_election, ...)``, triée.

    Appelée **séparément** pour chaque fichier source (``champs_totaux`` sur les
    lignes ``general_results``, ``champs_identite_candidat`` sur les lignes
    ``candidats_results`` — mutuellement exclusifs, les deux fichiers n'ont pas la même
    granularité ni les mêmes colonnes) :

    - ``champs_totaux`` non vide : ``group by (id_election, code_commune)`` + somme —
      une entrée par élection, ``{"id_election", "code_insee", **champs_totaux}``.
    - ``champs_identite_candidat`` non vide : ``group by (id_election, code_commune,
      *champs_identite_candidat)`` + ``sum(voix)`` — une entrée par candidat distinct,
      ``{"id_election", "code_insee", **champs_identite_candidat, "voix"}``. Un même
      candidat dans 2 bureaux fusionne (voix sommées) ; deux candidats homonymes avec
      des identités différentes (ex. ``no_panneau``) ne fusionnent jamais.

    Lève :class:`CodeCommuneInvalide` si aucune ligne pour la commune,
    :class:`TypeElectionInconnu` si un ``id_election`` rencontré ne parse sur aucun
    type de :data:`TYPES_ELECTION`.
    """
    if champs_totaux and champs_identite_candidat:
        raise ValueError(
            "champs_totaux et champs_identite_candidat sont mutuellement exclusifs "
            "(fichiers sources de granularités différentes)."
        )

    cible = normaliser_code_commune(code_insee)
    lignes_commune = [
        ligne for ligne in lignes
        if normaliser_code_commune(ligne.get(champ_code_commune)) == cible
    ]
    if not lignes_commune:
        raise CodeCommuneInvalide(
            f"aucune ligne trouvée pour le code commune {code_insee!r} (normalisé {cible!r})"
        )

    for ligne in lignes_commune:
        decomposer_id_election(ligne.get(champ_election))

    groupes: dict[tuple, dict] = {}
    if champs_identite_candidat:
        for ligne in lignes_commune:
            cle = (ligne.get(champ_election), *(ligne.get(c) for c in champs_identite_candidat))
            if cle not in groupes:
                groupes[cle] = {
                    "id_election": ligne.get(champ_election),
                    "code_insee": cible,
                    **{c: ligne.get(c) for c in champs_identite_candidat},
                    "voix": 0,
                }
            groupes[cle]["voix"] += _vers_int(ligne.get("voix"))
    else:
        for ligne in lignes_commune:
            cle = (ligne.get(champ_election),)
            if cle not in groupes:
                groupes[cle] = {
                    "id_election": ligne.get(champ_election),
                    "code_insee": cible,
                    **{c: 0 for c in champs_totaux},
                }
            for c in champs_totaux:
                groupes[cle][c] += _vers_int(ligne.get(c))

    resultat = list(groupes.values())
    resultat.sort(key=lambda r: (r["id_election"], r["code_insee"]))
    return resultat


_CHAMPS_JOINTURE_ELU_SIEGES = (
    "libelle_liste", "libelle_abrege", "sieges_conseil_municipal",
    "sieges_conseil_communautaire", "elu",
)


def joindre_elu_sieges(lignes_agregees: list[dict], index_municipales: dict) -> list[dict]:
    """Enrichit les lignes agrégées ``2026_muni_t1`` avec ``elu``/
    ``sieges_conseil_municipal``/``sieges_conseil_communautaire``/``libelle_liste``/
    ``libelle_abrege``, par jointure ``(code_insee, no_panneau)`` avec la source
    municipales 2026 actuelle — seule source à porter ces colonnes, absentes du jeu
    agrégé (plan v4, § 5.6 : clé validée à 100 % sur l'intégralité du fichier source,
    49 893/49 893 paires).

    ``index_municipales`` : ``{(code_insee, no_panneau): {...}}`` — construit par
    l'appelant (``datasets/elections.py``, qui connaît le format précis de la source
    municipales, 13 blocs de colonnes répétées) depuis le fichier municipales 2026
    actuel ; ce module reste volontairement agnostique de ce format, comme pour le
    reste du fichier.

    N'enrichit **que** les lignes ``id_election == "2026_muni_t1"`` — jamais
    ``2026_muni_t2`` (pas de sièges exploitables au second tour dans la source
    actuelle, conseil pas encore constitué) ni aucun autre scrutin (aucune source de
    sièges équivalente n'existe pour les autres types). Une ligne sans correspondance
    dans l'index (clé absente — ex. commune passée au second tour) est retournée
    **inchangée**, jamais une exception : c'est un cas normal, pas une erreur de
    jointure. Ne mute jamais ``lignes_agregees`` (retourne des copies pour les lignes
    enrichies)."""
    resultat = []
    for ligne in lignes_agregees:
        if ligne.get("id_election") != "2026_muni_t1":
            resultat.append(ligne)
            continue
        cle = (str(ligne.get("code_insee") or "").strip(), str(ligne.get("no_panneau") or "").strip())
        correspondance = index_municipales.get(cle)
        if correspondance is None:
            resultat.append(ligne)
            continue
        resultat.append({**ligne, **{c: correspondance.get(c) for c in _CHAMPS_JOINTURE_ELU_SIEGES}})
    return resultat


__all__ = [
    "CodeCommuneInvalide",
    "TYPES_ELECTION",
    "TypeElectionInconnu",
    "agreger_bureau_vers_commune",
    "agreger_long_vers_commune",
    "decomposer_id_election",
    "joindre_elu_sieges",
    "normaliser_code_commune",
    "recalculer_ratios",
    "unpivot_candidats",
]
