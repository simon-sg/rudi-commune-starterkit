"""Tests de resolution_noeud.py — rapprochement d'organisations déjà sur le nœud."""
import unittest
from unittest import mock

import requests

from rudi_commune_starterkit import resolution_noeud


class TestTesterConnexionNoeud(unittest.TestCase):
    def test_delegue_a_noeud_pret(self):
        with mock.patch("rudi_commune_starterkit.resolution_noeud.rudi_client.noeud_pret",
                         return_value=True) as m:
            self.assertTrue(resolution_noeud.tester_connexion_noeud({"url": "https://x"}))
        m.assert_called_once_with({"url": "https://x"}, erreur_sortie=None)

    def test_transmet_erreur_sortie(self):
        erreur: dict = {}
        with mock.patch("rudi_commune_starterkit.resolution_noeud.rudi_client.noeud_pret",
                         return_value=False) as m:
            resolution_noeud.tester_connexion_noeud({"url": "https://x"}, erreur_sortie=erreur)
        m.assert_called_once_with({"url": "https://x"}, erreur_sortie=erreur)


class TestErreurEstCertificatTls(unittest.TestCase):
    def test_true_pour_sslerror(self):
        erreur = {"exception": requests.exceptions.SSLError("auto-signé")}
        self.assertTrue(resolution_noeud.erreur_est_certificat_tls(erreur))

    def test_false_pour_autre_exception(self):
        erreur = {"exception": requests.exceptions.ConnectionError("DNS cassé")}
        self.assertFalse(resolution_noeud.erreur_est_certificat_tls(erreur))

    def test_false_si_aucune_exception(self):
        # Cas d'un code HTTP != 200 sans exception (nœud joignable mais mauvaise
        # réponse) : jamais un problème de certificat.
        self.assertFalse(resolution_noeud.erreur_est_certificat_tls({}))


class TestDesactiverVerificationTlsNoeud(unittest.TestCase):
    def test_delegue_a_rudi_client(self):
        with mock.patch(
            "rudi_commune_starterkit.resolution_noeud.rudi_client.desactiver_verification_tls",
        ) as m:
            resolution_noeud.desactiver_verification_tls_noeud()
        m.assert_called_once_with()


class TestOrganisationExistante(unittest.TestCase):
    def test_delegue_a_organisation_par_nom(self):
        org = {"organization_id": "abc", "organization_name": "Commune de Gévezé"}
        with mock.patch(
            "rudi_commune_starterkit.resolution_noeud.rudi_client.organisation_par_nom",
            return_value=org,
        ) as m:
            resultat = resolution_noeud.organisation_existante({"url": "https://x"}, "Commune de Gévezé")
        self.assertEqual(resultat, org)
        m.assert_called_once_with({"url": "https://x"}, "Commune de Gévezé")


class TestNormaliserNomOrganisation(unittest.TestCase):
    def test_casse_et_accents_ignores(self):
        a = resolution_noeud.normaliser_nom_organisation("Commune de Gévezé")
        b = resolution_noeud.normaliser_nom_organisation("commune   de geveze")
        self.assertEqual(a, b)


class TestRapprocherOrganisation(unittest.TestCase):
    def test_trouve_malgre_casse_differente(self):
        orgs = [{"organization_id": "abc", "organization_name": "dgfip"}]
        trouve = resolution_noeud.rapprocher_organisation("DGFiP", orgs)
        self.assertEqual(trouve["organization_id"], "abc")

    def test_aucune_correspondance(self):
        orgs = [{"organization_id": "abc", "organization_name": "INSEE"}]
        self.assertIsNone(resolution_noeud.rapprocher_organisation("DGFiP", orgs))


class TestResoudreOrganisationsProducteurs(unittest.TestCase):
    def test_nominal_un_rapproche_un_non(self):
        producteurs = [
            {"organization_name": "DGFiP", "organization_summary": "x"},
            {"organization_name": "Agence ORE", "organization_summary": "y"},
        ]
        orgs_noeud = [{"organization_id": "id-dgfip", "organization_name": "dgfip"}]
        with mock.patch(
            "rudi_commune_starterkit.resolution_noeud.rudi_client.lister_organisations",
            return_value=orgs_noeud,
        ):
            mapping, avertissement = resolution_noeud.resoudre_organisations_producteurs(
                {"url": "https://x"}, producteurs,
            )
        self.assertIsNone(avertissement)
        self.assertEqual(mapping["DGFiP"]["organization_id"], "id-dgfip")
        self.assertNotIn("organization_id", mapping["Agence ORE"])

    def test_echec_listing_renvoie_avertissement_sans_exception(self):
        producteurs = [{"organization_name": "DGFiP", "organization_summary": "x"}]
        with mock.patch(
            "rudi_commune_starterkit.resolution_noeud.rudi_client.lister_organisations",
            side_effect=RuntimeError("403"),
        ):
            mapping, avertissement = resolution_noeud.resoudre_organisations_producteurs(
                {"url": "https://x"}, producteurs,
            )
        self.assertIsNotNone(avertissement)
        self.assertEqual(mapping["DGFiP"]["organization_name"], "DGFiP")
        self.assertNotIn("organization_id", mapping["DGFiP"])


if __name__ == "__main__":
    unittest.main()
