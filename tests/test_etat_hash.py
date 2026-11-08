"""Tests de etat_hash.py — hash de contenu déterministe, décision de republication."""
import unittest

from rudi_commune_starterkit import etat_hash


class TestHashContenuJdd(unittest.TestCase):
    def test_determinisme_ordre_des_cles(self):
        a = {"producer": {"organization_name": "X"}, "resource_title": "Y"}
        b = {"resource_title": "Y", "producer": {"organization_name": "X"}}
        self.assertEqual(etat_hash.hash_contenu_jdd(a), etat_hash.hash_contenu_jdd(b))

    def test_changement_de_producer_change_le_hash(self):
        a = {"producer": {"organization_name": "DGFiP"}}
        b = {"producer": {"organization_name": "Commune de Gévezé"}}
        self.assertNotEqual(etat_hash.hash_contenu_jdd(a), etat_hash.hash_contenu_jdd(b))


class TestDoitRepublier(unittest.TestCase):
    def test_force_maj_toujours_vrai(self):
        etat = {"id1": {"hash": "abc"}}
        self.assertTrue(etat_hash.doit_republier(etat, "id1", "abc", forcer_maj=True))

    def test_local_id_absent_vrai(self):
        self.assertTrue(etat_hash.doit_republier({}, "id1", "abc", forcer_maj=False))

    def test_hash_identique_faux(self):
        etat = {"id1": {"hash": "abc"}}
        self.assertFalse(etat_hash.doit_republier(etat, "id1", "abc", forcer_maj=False))

    def test_hash_different_vrai(self):
        etat = {"id1": {"hash": "abc"}}
        self.assertTrue(etat_hash.doit_republier(etat, "id1", "xyz", forcer_maj=False))


class TestEnregistrerPublication(unittest.TestCase):
    def test_nouvelle_entree_presente(self):
        resultat = etat_hash.enregistrer_publication({}, "id1", "abc")
        self.assertEqual(resultat["id1"]["hash"], "abc")

    def test_etat_original_non_mute(self):
        etat_original = {"id0": {"hash": "zzz"}}
        copie_avant = dict(etat_original)
        etat_hash.enregistrer_publication(etat_original, "id1", "abc")
        self.assertEqual(etat_original, copie_avant)


if __name__ == "__main__":
    unittest.main()
