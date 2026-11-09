"""Tests de licences.py — point d'entrée unique, table curée, jamais de repli
silencieux Etalab 2.0."""
import unittest

from rudi_commune_starterkit import licences, registre
from rudi_commune_starterkit.licences import LicenceInconnueError, licence_pour_jdd


class TestCompleteudeLicencesCurees(unittest.TestCase):
    def test_toutes_les_cles_de_modules_ont_une_licence_curee(self):
        # Test le plus rentable de cette v3 (relecture technique) : attrape tout module
        # câblé sur licence_pour_jdd() sans entrée curée correspondante.
        cles_modules = {m.CLE for m in registre.lister_modules()}
        self.assertEqual(set(licences.LICENCES_CUREES), cles_modules)


class TestLicencePourJdd(unittest.TestCase):
    def test_licence_dynamique_prioritaire(self):
        dyn = {"licence_type": "STANDARD", "licence_label": "odbl-1.0"}
        resultat = licence_pour_jdd("elus", licence_dynamique=dyn)
        self.assertEqual(resultat, dyn)

    def test_repli_curee_si_pas_de_dynamique(self):
        resultat = licence_pour_jdd("elus")
        self.assertEqual(resultat["licence_label"], "etalab-2.0")

    def test_cle_inconnue_sans_dynamique_leve(self):
        with self.assertRaises(LicenceInconnueError):
            licence_pour_jdd("jdd-inexistant")

    def test_table_retournee_est_une_copie(self):
        a = licence_pour_jdd("elus")
        a["licence_label"] = "modifié"
        b = licence_pour_jdd("elus")
        self.assertEqual(b["licence_label"], "etalab-2.0")


class TestLicencesCureesContenu(unittest.TestCase):
    def test_entreprises_et_associations_sont_custom_avec_deux_uri(self):
        for cle in ("entreprises", "associations"):
            bloc = licences.LICENCES_CUREES[cle]
            self.assertEqual(bloc["licence_type"], "CUSTOM")
            texte = bloc["custom_licence_label"][0]["text"]
            self.assertIn("etalab.gouv.fr", texte)
            self.assertIn("inpi.fr", texte)

    def test_deliberations_licence_uri_pointe_vers_etalab_pas_le_pdf_megalis(self):
        bloc = licences.LICENCES_CUREES["deliberations"]
        self.assertEqual(bloc["licence_uri"], "https://www.etalab.gouv.fr/licence-ouverte-open-licence")

    def test_marches_publics_et_immobilier_dvf_presents(self):
        self.assertIn("marches_publics", licences.LICENCES_CUREES)
        self.assertIn("immobilier_dvf", licences.LICENCES_CUREES)


if __name__ == "__main__":
    unittest.main()
