"""Générateur du guide utilisateur HTML (MkDocs) de ``rudi-commune-starterkit``.

Principe (voir ``guide/README.md`` et BACKLOG.md, chantier C) : ``docs/`` n'est
**jamais** versionné ni édité à la main — ce script le (re)construit entièrement à
chaque exécution, à partir de deux sources, jamais dupliquées ailleurs :

- ``registre.lister_modules()`` (13 JDD du socle) pour les fiches de données —
  ``TITRE``/``SYNOPSIS_PATRON``/``DESCRIPTION_PATRON``/``THEME``/``FREQUENCE_MAJ``,
  déjà écrits à la main dans chaque module ``datasets/*.py``.
- ``guide.contenu_statique`` pour tout le reste (accueil, tutoriel, FAQ, glossaire,
  licences) — du texte rédigé une fois avec soin, pas généré par gabarit.

Aucun appel réseau : les 13 fiches sont rendues avec une commune d'exemple fixe
(``contenu_statique.COMMUNE_EXEMPLE``), pas une vraie moisson en direct — fiabilité du
build, indépendance de la disponibilité d'INSEE/data.gouv au moment de déployer le
guide.

Usage : ``python -m guide.generer`` (ou ``python guide/generer.py``) depuis la racine
du dépôt, puis ``mkdocs build``.
"""

from __future__ import annotations

import os

from rudi_commune_starterkit import registre

from . import contenu_statique as c

RACINE_DEPOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DOSSIER_DOCS = os.path.join(RACINE_DEPOT, "docs")


def _ecrire(chemin_relatif: str, contenu: str) -> None:
    chemin = os.path.join(DOSSIER_DOCS, chemin_relatif)
    os.makedirs(os.path.dirname(chemin), exist_ok=True)
    with open(chemin, "w", encoding="utf-8") as f:
        f.write(contenu.rstrip() + "\n")


def generer_accueil() -> None:
    _ecrire("index.md", c.PAGE_ACCUEIL)


def generer_guide_utilisation() -> None:
    for nom_fichier, contenu in c.PAGES_GUIDE.items():
        _ecrire(f"guide/{nom_fichier}", contenu)


def generer_faq() -> None:
    _ecrire("faq.md", c.PAGE_FAQ)


def generer_glossaire() -> None:
    _ecrire("glossaire.md", c.PAGE_GLOSSAIRE)


def generer_licences() -> None:
    _ecrire("licences.md", c.PAGE_LICENCES)


def rendre_fiche_jdd(module) -> str:
    """Rend la fiche d'un module JDD pour la commune d'exemple — fiche volontairement
    simple (titre/synopsis/description/thème/fréquence, les 5 constantes module-level
    déjà écrites à la main, sans exécution) : le glossaire/les limites détaillés,
    dépendants d'une commune réelle, restent sur la vraie fiche RUDI (voir le renvoi en
    bas de page), pas dupliqués ici (décision BACKLOG.md, chantier C)."""
    commune, code_insee = c.COMMUNE_EXEMPLE["nom"], c.COMMUNE_EXEMPLE["code_insee"]
    synopsis = module.SYNOPSIS_PATRON.format(commune=commune, code_insee=code_insee)
    description = module.DESCRIPTION_PATRON.format(commune=commune, code_insee=code_insee)
    groupe = c.THEME_LIBELLES.get(module.THEME, module.THEME)
    frequence = c.FREQUENCE_LIBELLES.get(module.FREQUENCE_MAJ, module.FREQUENCE_MAJ)
    return f"""# {module.TITRE}

{synopsis}.

{description}

**Catégorie :** {groupe}. **Mise à jour :** {frequence}.

!!! note "Exemple, pas une vraie publication"
    Cette fiche illustre la donnée publiée pour {commune} ({code_insee}), à titre
    d'exemple — le contenu réel dépend de votre commune. Pour le détail technique
    complet (variables publiées, limites de couverture éventuelles, contact) et les
    vrais chiffres de votre commune, consultez la fiche publiée sur le portail RUDI
    qui vous a été indiqué.
"""


def generer_fiches_jdd() -> None:
    modules = registre.lister_modules()
    commune, code_insee = c.COMMUNE_EXEMPLE["nom"], c.COMMUNE_EXEMPLE["code_insee"]

    par_groupe: dict[str, list] = {}
    for module in modules:
        _ecrire(f"donnees/{module.CLE}.md", rendre_fiche_jdd(module))
        groupe = c.THEME_LIBELLES.get(module.THEME, module.THEME)
        par_groupe.setdefault(groupe, []).append(module)

    lignes = [c.PAGE_DONNEES_INTRO, ""]
    groupes_ordonnes = [g for g in c.ORDRE_GROUPES if g in par_groupe]
    groupes_ordonnes += [g for g in par_groupe if g not in groupes_ordonnes]  # repli defensif
    for groupe in groupes_ordonnes:
        lignes.append(f"## {groupe}\n")
        for module in par_groupe[groupe]:
            synopsis = module.SYNOPSIS_PATRON.format(commune=commune, code_insee=code_insee)
            lignes.append(f"- [**{module.TITRE}**](./{module.CLE}.md) — {synopsis}.")
        lignes.append("")
    _ecrire("donnees/index.md", "\n".join(lignes))


def generer_tout() -> None:
    generer_accueil()
    generer_guide_utilisation()
    generer_fiches_jdd()
    generer_faq()
    generer_glossaire()
    generer_licences()


if __name__ == "__main__":
    generer_tout()
    print(f"Guide généré dans {DOSSIER_DOCS}")
