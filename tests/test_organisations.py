"""Tests de organisations.py — table curée + résolution des 3 modes de producer."""
import unittest

from rudi_commune_starterkit.organisations import (
    ADRESSES,
    DELIBERATIONS,
    ENTREPRISES,
    ORGANISATIONS,
    organisation_commune,
    producteur_reel,
    resoudre_producer,
)

_GEVEZE = {"nom": "Gévezé", "code_insee": "35120"}


class TestTableCuree(unittest.TestCase):
    def test_14_jdd_moins_deliberations(self):
        # DELIBERATIONS est volontairement absente (cas particulier, voir docstring).
        self.assertNotIn(DELIBERATIONS, ORGANISATIONS)
        self.assertEqual(len(ORGANISATIONS), 13)

    def test_chaque_entree_a_nom_caption_summary_url(self):
        for cle, org in ORGANISATIONS.items():
            self.assertTrue(org.get("organization_name"), cle)
            self.assertTrue(org.get("organization_caption"), cle)
            self.assertTrue(org.get("organization_summary"), cle)
            self.assertTrue(org.get("organization_url"), cle)

    def test_producteur_reel_retourne_une_copie(self):
        a = producteur_reel(ENTREPRISES)
        a["organization_name"] = "modifié"
        b = producteur_reel(ENTREPRISES)
        self.assertEqual(b["organization_name"], "INSEE")

    def test_producteur_reel_cle_inconnue_leve(self):
        with self.assertRaises(KeyError):
            producteur_reel("jdd-inexistant")

    def test_producteur_reel_deliberations_leve(self):
        with self.assertRaises(KeyError):
            producteur_reel(DELIBERATIONS)


class TestOrganisationCommune(unittest.TestCase):
    def test_nom_construit_explicitement(self):
        org = organisation_commune(_GEVEZE)
        self.assertEqual(org["organization_name"], "Commune de Gévezé")

    def test_summary_non_vide(self):
        org = organisation_commune(_GEVEZE)
        self.assertIn("Gévezé", org["organization_summary"])
        self.assertIn("35120", org["organization_summary"])

    def test_aucune_organization_caption_transmise_a_la_creation(self):
        # Rappel du README toolkit : demander_creation_organisation() ne transmet jamais
        # organization_caption à la création — sans conséquence ici, mais la présence de la
        # clé elle-même (pour l'affichage une fois l'org déjà connue) doit être vérifiée.
        org = organisation_commune(_GEVEZE)
        self.assertIn("organization_caption", org)


class TestResoudreProducer(unittest.TestCase):
    def test_mode_source_retourne_le_vrai_producteur(self):
        producer = resoudre_producer(ENTREPRISES, "source", _GEVEZE)
        self.assertEqual(producer["organization_name"], "INSEE")

    def test_mode_commune_retourne_la_commune(self):
        producer = resoudre_producer(ENTREPRISES, "commune", _GEVEZE)
        self.assertEqual(producer["organization_name"], "Commune de Gévezé")

    def test_deliberations_toujours_commune_meme_en_mode_source(self):
        producer = resoudre_producer(DELIBERATIONS, "source", _GEVEZE)
        self.assertEqual(producer["organization_name"], "Commune de Gévezé")

    def test_deliberations_toujours_commune_meme_en_mode_commune(self):
        producer = resoudre_producer(DELIBERATIONS, "commune", _GEVEZE)
        self.assertEqual(producer["organization_name"], "Commune de Gévezé")

    def test_mode_inconnu_leve(self):
        with self.assertRaises(ValueError):
            resoudre_producer(ENTREPRISES, "autre", _GEVEZE)

    def test_mode_source_jdd_inconnu_leve(self):
        with self.assertRaises(KeyError):
            resoudre_producer("jdd-inexistant", "source", _GEVEZE)

    def test_adresses_mode_source(self):
        producer = resoudre_producer(ADRESSES, "source", _GEVEZE)
        self.assertIn("Base Adresse Nationale", producer["organization_name"])


if __name__ == "__main__":
    unittest.main()
