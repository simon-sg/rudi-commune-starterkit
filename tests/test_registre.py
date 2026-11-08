"""Tests de registre.py — énumération des modules JDD, sans duplication de métadonnées."""
import unittest

from rudi_commune_starterkit import registre


class TestRegistre(unittest.TestCase):
    def test_treize_modules(self):
        self.assertEqual(len(registre.lister_modules()), 13)

    def test_chaque_module_porte_les_attributs_requis(self):
        for module in registre.lister_modules():
            for attribut in ("CLE", "THEME", "TITRE", "SYNOPSIS_PATRON",
                              "DESCRIPTION_PATRON", "FREQUENCE_MAJ", "moissonner"):
                self.assertTrue(hasattr(module, attribut), f"{module.__name__}.{attribut} manquant")

    def test_cles_toutes_distinctes(self):
        cles = [m.CLE for m in registre.lister_modules()]
        self.assertEqual(len(cles), len(set(cles)))

    def test_energie_absent_du_registre(self):
        self.assertNotIn("energie", [m.CLE for m in registre.lister_modules()])

    def test_module_par_cle(self):
        module = registre.module_par_cle("adresses")
        self.assertEqual(module.CLE, "adresses")

    def test_module_par_cle_inconnu(self):
        with self.assertRaises(KeyError):
            registre.module_par_cle("inexistant")


if __name__ == "__main__":
    unittest.main()
