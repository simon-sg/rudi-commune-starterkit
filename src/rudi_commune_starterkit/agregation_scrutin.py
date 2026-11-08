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

_LARGEUR_CODE_INSEE = 5


class CodeCommuneInvalide(ValueError):
    """Code commune électoral non normalisable, ou aucun bureau trouvé pour ce code."""


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


__all__ = [
    "CodeCommuneInvalide",
    "agreger_bureau_vers_commune",
    "normaliser_code_commune",
    "unpivot_candidats",
]
