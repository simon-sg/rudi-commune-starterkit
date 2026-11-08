"""Registre des modules JDD du socle — liste, ne duplique aucune métadonnée.

Chaque module de ``datasets/`` porte lui-même ses attributs (``CLE``, ``THEME``, ``TITRE``,
``SYNOPSIS_PATRON``, ``DESCRIPTION_PATRON``, ``FREQUENCE_MAJ``, ``moissonner()``) — ce
registre ne fait qu'énumérer les modules dans l'ordre de référence du plan, pour que
``cli.py`` n'ait qu'un seul endroit à boucler.

**13 JDD sur les 14 prévus** : ``energie`` (consommations gaz/électricité, Agence ORE/
``portail.agenceore.fr``) est absent — la source renvoie un ``403`` à toute requête
automatisée (protection anti-bot), contournement refusé par la politique de l'outil.
Reporté en v2 (décision utilisateur du 2026-11-07), pas un oubli.
"""

from __future__ import annotations

from .datasets import (
    adresses,
    associations,
    budget,
    deliberations,
    eau_potable,
    elections,
    elus,
    entreprises,
    etablissements_scolaires,
    immobilier_dvf,
    irve,
    marches_publics,
    population,
)

MODULES = (
    entreprises,
    associations,
    budget,
    marches_publics,
    deliberations,
    population,
    eau_potable,
    etablissements_scolaires,
    adresses,
    elus,
    elections,
    immobilier_dvf,
    irve,
)


def lister_modules() -> list:
    """Modules JDD disponibles, dans l'ordre de référence du plan."""
    return list(MODULES)


def module_par_cle(cle: str):
    """Module dont ``CLE == cle``. Lève :class:`KeyError` si inconnu."""
    for module in MODULES:
        if module.CLE == cle:
            return module
    raise KeyError(f"JDD inconnu : {cle!r} (disponibles : {[m.CLE for m in MODULES]})")


__all__ = ["MODULES", "lister_modules", "module_par_cle"]
