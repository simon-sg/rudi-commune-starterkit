"""Tests de resolution_noeud.py — rapprochement d'organisations déjà sur le nœud."""
import unittest
from unittest import mock

import requests

from rudi_commune_starterkit import resolution_noeud


class TestChargerConfRudi(unittest.TestCase):
    """Bug réel corrigé le 2026-11-14 : cli.py importait charger_conf_rudi() et
    demander_creation_organisation() directement depuis le toolkit, contournant cet
    adaptateur."""
    def test_delegue_a_rudi_client(self):
        with mock.patch("rudi_commune_starterkit.resolution_noeud.rudi_client.charger_conf_rudi",
                         return_value={"url": "https://x"}) as m:
            self.assertEqual(resolution_noeud.charger_conf_rudi("conf/rudi_node.json"),
                              {"url": "https://x"})
        m.assert_called_once_with("conf/rudi_node.json")


class TestDemanderCreationOrganisation(unittest.TestCase):
    def test_delegue_a_rudi_client(self):
        with mock.patch(
            "rudi_commune_starterkit.resolution_noeud.rudi_client.demander_creation_organisation",
            return_value="org-1",
        ) as m:
            self.assertEqual(
                resolution_noeud.demander_creation_organisation({"url": "https://x"}, {"a": 1}),
                "org-1",
            )
        m.assert_called_once_with({"url": "https://x"}, {"a": 1})


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


class TestResoudreUrlsAutomatiquement(unittest.TestCase):
    """GET {url_noeud}/manager/conf — route publique du Manager, sans authentification
    (vérifié en conditions réelles le 2026-11-15 sur une instance preprod et une
    instance locale)."""

    def test_nominal_catalogue_et_portail_trouves(self):
        reponse = mock.Mock()
        reponse.json.return_value = {
            "catalogPubUrl": "https://x/catalog", "portalUrl": "https://portail.fr",
        }
        with mock.patch("rudi_commune_starterkit.resolution_noeud.requests.get",
                         return_value=reponse) as m:
            url_catalog, url_portail = resolution_noeud.resoudre_urls_automatiquement("https://x/")
        self.assertEqual(url_catalog, "https://x/catalog")
        self.assertEqual(url_portail, "https://portail.fr")
        m.assert_called_once_with("https://x/manager/conf", timeout=mock.ANY, verify=True)

    def test_url_noeud_trailing_slash_retiree(self):
        reponse = mock.Mock()
        reponse.json.return_value = {"catalogPubUrl": "https://x/catalog"}
        with mock.patch("rudi_commune_starterkit.resolution_noeud.requests.get",
                         return_value=reponse) as m:
            resolution_noeud.resoudre_urls_automatiquement("https://x///")
        m.assert_called_once_with("https://x/manager/conf", timeout=mock.ANY, verify=True)

    def test_champs_absents_de_la_reponse(self):
        reponse = mock.Mock()
        reponse.json.return_value = {"appTag": "dev0"}
        with mock.patch("rudi_commune_starterkit.resolution_noeud.requests.get",
                         return_value=reponse):
            url_catalog, url_portail = resolution_noeud.resoudre_urls_automatiquement("https://x")
        self.assertIsNone(url_catalog)
        self.assertIsNone(url_portail)

    def test_noeud_injoignable_renvoie_none_none_sans_lever(self):
        with mock.patch(
            "rudi_commune_starterkit.resolution_noeud.requests.get",
            side_effect=requests.exceptions.ConnectionError("DNS cassé"),
        ):
            url_catalog, url_portail = resolution_noeud.resoudre_urls_automatiquement("https://x")
        self.assertIsNone(url_catalog)
        self.assertIsNone(url_portail)

    def test_code_http_erreur_renvoie_none_none_sans_lever(self):
        reponse = mock.Mock()
        reponse.raise_for_status.side_effect = requests.exceptions.HTTPError("404")
        with mock.patch("rudi_commune_starterkit.resolution_noeud.requests.get",
                         return_value=reponse):
            url_catalog, url_portail = resolution_noeud.resoudre_urls_automatiquement("https://x")
        self.assertIsNone(url_catalog)
        self.assertIsNone(url_portail)

    def test_reponse_json_invalide_renvoie_none_none_sans_lever(self):
        reponse = mock.Mock()
        reponse.json.side_effect = ValueError("not json")
        with mock.patch("rudi_commune_starterkit.resolution_noeud.requests.get",
                         return_value=reponse):
            url_catalog, url_portail = resolution_noeud.resoudre_urls_automatiquement("https://x")
        self.assertIsNone(url_catalog)
        self.assertIsNone(url_portail)

    def test_certificat_tls_non_reconnu_renvoie_none_none_et_remplit_erreur_sortie(self):
        # Bug réel corrigé le 2026-11-16 : avant, cette exception était avalée sans
        # distinction (comme un nœud injoignable) — aucun moyen pour l'appelant de
        # proposer d'ignorer le certificat comme pour le test de connexion
        # (cli._tester_connexion_avec_repli_tls). Reproduit en conditions réelles
        # contre un serveur mock HTTPS à certificat auto-signé avant correction.
        erreur: dict = {}
        exception = requests.exceptions.SSLError("certificat non reconnu")
        with mock.patch(
            "rudi_commune_starterkit.resolution_noeud.requests.get", side_effect=exception,
        ):
            url_catalog, url_portail = resolution_noeud.resoudre_urls_automatiquement(
                "https://x", erreur_sortie=erreur,
            )
        self.assertIsNone(url_catalog)
        self.assertIsNone(url_portail)
        self.assertIs(erreur.get("exception"), exception)

    def test_verify_false_transmis_a_requests_get(self):
        reponse = mock.Mock()
        reponse.json.return_value = {
            "catalogPubUrl": "https://x/catalog", "portalUrl": "https://portail.fr",
        }
        with mock.patch("rudi_commune_starterkit.resolution_noeud.requests.get",
                         return_value=reponse) as m:
            url_catalog, url_portail = resolution_noeud.resoudre_urls_automatiquement(
                "https://x", verify=False,
            )
        self.assertEqual(url_catalog, "https://x/catalog")
        self.assertEqual(url_portail, "https://portail.fr")
        m.assert_called_once_with("https://x/manager/conf", timeout=mock.ANY, verify=False)

    def test_erreur_sortie_non_rempli_si_succes(self):
        reponse = mock.Mock()
        reponse.json.return_value = {"catalogPubUrl": "https://x/catalog"}
        erreur: dict = {}
        with mock.patch("rudi_commune_starterkit.resolution_noeud.requests.get",
                         return_value=reponse):
            resolution_noeud.resoudre_urls_automatiquement("https://x", erreur_sortie=erreur)
        self.assertEqual(erreur, {})


if __name__ == "__main__":
    unittest.main()
