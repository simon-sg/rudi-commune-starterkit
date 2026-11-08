"""Tests de resultat.py — taxonomie ResultatConnecteur."""
import unittest

from rudi_commune_starterkit.resultat import ResultatConnecteur, StatutConnecteur


class TestResultatConnecteur(unittest.TestCase):
    def test_publiable_avec_rudi_metadata(self):
        r = ResultatConnecteur(StatutConnecteur.PUBLIABLE, rudi_metadata={"local_id": "x"})
        self.assertEqual(r.statut, StatutConnecteur.PUBLIABLE)

    def test_publiable_sans_rudi_metadata_leve(self):
        with self.assertRaises(ValueError):
            ResultatConnecteur(StatutConnecteur.PUBLIABLE)

    def test_hors_couverture_sans_rudi_metadata_ok(self):
        r = ResultatConnecteur(StatutConnecteur.HORS_COUVERTURE)
        self.assertIsNone(r.rudi_metadata)

    def test_vide_sans_rudi_metadata_ok(self):
        r = ResultatConnecteur(StatutConnecteur.VIDE)
        self.assertEqual(r.fichiers_filtres, [])

    def test_echec_avec_message(self):
        r = ResultatConnecteur(StatutConnecteur.ECHEC, message="panne réseau")
        self.assertEqual(r.message, "panne réseau")

    def test_statut_inconnu_leve(self):
        with self.assertRaises(ValueError):
            ResultatConnecteur("autre")


if __name__ == "__main__":
    unittest.main()
