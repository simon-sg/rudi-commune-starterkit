"""Tests de non-régression du guide utilisateur HTML (``guide/``, hors ``src/``).

``docs/`` est un artefact de build jetable (jamais versionné, voir ``.gitignore``) —
ces tests le régénèrent eux-mêmes plutôt que de supposer un état préexistant, et
vérifient surtout les deux risques réels de ce générateur : un module de JDD oublié
silencieusement, et une dérive entre le tutoriel (texte figé dans
``guide/contenu_statique.py``) et le wizard réel (``cli.py``).
"""
from __future__ import annotations

import inspect
import os
import re
import unittest

from rudi_commune_starterkit import cli, registre

from guide import contenu_statique as c
from guide import generer


class TestFichesJdd(unittest.TestCase):
    def test_une_fiche_par_module_du_registre(self):
        generer.generer_fiches_jdd()
        cles_registre = {m.CLE for m in registre.lister_modules()}
        fichiers = {
            nom[: -len(".md")]
            for nom in os.listdir(os.path.join(generer.DOSSIER_DOCS, "donnees"))
            if nom.endswith(".md") and nom != "index.md"
        }
        self.assertEqual(
            fichiers, cles_registre,
            "Une fiche doit exister pour chaque module de registre.lister_modules() "
            "(ni plus, ni moins) — un module ajouté/retiré doit se répercuter ici "
            "automatiquement, sans oubli silencieux.",
        )

    def test_aucun_placeholder_residuel(self):
        """Un module dont SYNOPSIS_PATRON/DESCRIPTION_PATRON référence un placeholder
        autre que {commune}/{code_insee} lèverait un KeyError à la génération — ce test
        couvre aussi le cas plus insidieux d'un format() qui réussirait mais laisserait
        une accolade littérale si un futur module utilisait .format_map avec un repli
        silencieux (pas le cas aujourd'hui, mais une régression future ne doit pas
        passer inaperçue)."""
        for module in registre.lister_modules():
            fiche = generer.rendre_fiche_jdd(module)
            self.assertNotIn("{", fiche, f"placeholder résiduel dans la fiche {module.CLE}")
            self.assertNotIn("}", fiche, f"placeholder résiduel dans la fiche {module.CLE}")

    def test_toutes_les_fiches_generent_sans_exception(self):
        """Contrat de complétude direct : SYNOPSIS_PATRON/DESCRIPTION_PATRON des 13
        modules formatent avec exactement (commune, code_insee) — pas un placeholder
        de plus (voir le correctif immobilier_dvf.py, qui référençait un {annees}
        jamais fourni, dead code découvert en écrivant ce générateur)."""
        for module in registre.lister_modules():
            try:
                generer.rendre_fiche_jdd(module)
            except KeyError as e:  # noqa: PERF203 - clarté du message prime ici
                self.fail(
                    f"{module.CLE} : SYNOPSIS_PATRON/DESCRIPTION_PATRON référence un "
                    f"placeholder non fourni ({e}) — corriger le patron du module, pas "
                    "ce générateur."
                )


class TestIdempotence(unittest.TestCase):
    def test_regeneration_identique(self):
        generer.generer_tout()
        avant = _lire_tous_les_fichiers(generer.DOSSIER_DOCS)
        generer.generer_tout()
        apres = _lire_tous_les_fichiers(generer.DOSSIER_DOCS)
        self.assertEqual(avant, apres, "la génération doit être déterministe (pas d'horodatage, pas d'ordre aléatoire)")


def _lire_tous_les_fichiers(racine: str) -> dict[str, str]:
    contenu: dict[str, str] = {}
    for dossier, _sous_dossiers, fichiers in os.walk(racine):
        for nom in fichiers:
            chemin = os.path.join(dossier, nom)
            with open(chemin, encoding="utf-8") as f:
                contenu[os.path.relpath(chemin, racine)] = f.read()
    return contenu


class TestNavCoherente(unittest.TestCase):
    def test_toutes_les_pages_du_guide_sont_dans_pages_guide(self):
        """mkdocs.yml liste les 7 pages du tutoriel en dur (volontairement, voir sa
        section nav) — ce test échoue si contenu_statique.PAGES_GUIDE change sans que
        mkdocs.yml soit mis à jour en conséquence, plutôt que de laisser une page
        générée mais invisible dans la navigation."""
        chemin_mkdocs = os.path.join(generer.RACINE_DEPOT, "mkdocs.yml")
        with open(chemin_mkdocs, encoding="utf-8") as f:
            contenu_mkdocs = f.read()
        for nom_fichier in c.PAGES_GUIDE:
            self.assertIn(
                f"guide/{nom_fichier}", contenu_mkdocs,
                f"guide/{nom_fichier} existe dans PAGES_GUIDE mais pas dans la nav de mkdocs.yml",
            )


class TestAntiDeriveWizard(unittest.TestCase):
    """Le tutoriel (pas-a-pas.md) cite mot pour mot des invites de cli.py. Si quelqu'un
    reformule une invite du wizard sans toucher au guide (ou l'inverse), ce test doit
    casser plutôt que de laisser le tutoriel mentir silencieusement à un agent
    municipal qui s'y fie écran par écran."""

    def test_citations_presentes_dans_cli(self):
        source_cli = inspect.getsource(cli)
        for citation in c.CITATIONS_WIZARD_A_VERIFIER:
            self.assertIn(
                citation, source_cli,
                f"citation absente de cli.py (reformulée sans mettre à jour le "
                f"tutoriel, ou inversement) : {citation!r}",
            )

    def test_citations_presentes_dans_le_tutoriel(self):
        # Les citations sont réparties sur plusieurs pages du tutoriel (pas-a-pas.md
        # pour le premier lancement, relancer.md pour la reprise d'un profil...) — pas
        # seulement pas-a-pas.md.
        texte_guide_complet = "\n".join(c.PAGES_GUIDE.values())
        for citation in c.CITATIONS_WIZARD_A_VERIFIER:
            self.assertIn(
                citation, texte_guide_complet,
                f"citation listée dans CITATIONS_WIZARD_A_VERIFIER mais absente du "
                f"texte réel du tutoriel : {citation!r}",
            )


class TestMarkdownBienForme(unittest.TestCase):
    def test_pas_de_titre_vide_ni_de_lien_casse_evident(self):
        generer.generer_tout()
        for dossier, _sous_dossiers, fichiers in os.walk(generer.DOSSIER_DOCS):
            for nom in fichiers:
                if not nom.endswith(".md"):
                    continue
                chemin = os.path.join(dossier, nom)
                with open(chemin, encoding="utf-8") as f:
                    texte = f.read()
                self.assertTrue(texte.startswith("# "), f"{chemin} ne commence pas par un titre H1")
                self.assertFalse(
                    re.search(r"\[[^\]]*\]\(\s*\)", texte), f"{chemin} contient un lien Markdown vide",
                )


if __name__ == "__main__":
    unittest.main()
