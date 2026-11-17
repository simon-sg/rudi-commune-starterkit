"""Tests de cli.py — cœur partagé (executer_run), résolution de modes, mode scriptable.

`only={...}` restreint systématiquement executer_run() à un seul module réel
(`population`), patché, pour ne jamais risquer un appel réseau vers les 12 autres
connecteurs réels référencés par registre.MODULES.
"""
import argparse
import io
import tempfile
import unittest
from unittest import mock

import requests

from rudi_commune_starterkit import cli, organisations, securite
from rudi_commune_starterkit.datasets import population
from rudi_commune_starterkit.resultat import ResultatConnecteur, StatutConnecteur

_GEVEZE = {"nom": "Gévezé", "code_insee": "35120", "code_region": "53"}
_HORS_BRETAGNE = {"nom": "Lyon", "code_insee": "69123", "code_region": "84"}
_CONF = {"url": "https://noeud", "usr": "u", "pwd": "p"}


def _metadata(organization_name="INSEE"):
    return {
        "local_id": "id-population-35120",
        "producer": {"organization_name": organization_name},
        "resource_title": "Population — Gévezé",
    }


class TestResoudreModesParJdd(unittest.TestCase):
    def test_source_pour_tous(self):
        modes = cli.resoudre_modes_par_jdd("source", None)
        self.assertTrue(all(m == "source" for m in modes.values()))
        self.assertEqual(len(modes), 13)

    def test_commune_pour_tous(self):
        modes = cli.resoudre_modes_par_jdd("commune", None)
        self.assertTrue(all(m == "commune" for m in modes.values()))

    def test_par_jdd_repli_source_pour_absent(self):
        modes = cli.resoudre_modes_par_jdd("par-jdd", {organisations.POPULATION: "commune"})
        self.assertEqual(modes[organisations.POPULATION], "commune")
        self.assertEqual(modes[organisations.ENTREPRISES], "source")

    def test_par_jdd_cle_inconnue_rejetee(self):
        with self.assertRaises(ValueError):
            cli.resoudre_modes_par_jdd("par-jdd", {"inexistant": "commune"})

    def test_mode_inconnu(self):
        with self.assertRaises(ValueError):
            cli.resoudre_modes_par_jdd("autre", None)


class TestDiagnosticCouvertureStructurelle(unittest.TestCase):
    def test_bretagne_tout_disponible(self):
        diagnostic = cli.diagnostic_couverture_structurelle(_GEVEZE)
        self.assertEqual(diagnostic[organisations.DELIBERATIONS], "a priori disponible")

    def test_hors_bretagne_deliberations_signalees(self):
        diagnostic = cli.diagnostic_couverture_structurelle(_HORS_BRETAGNE)
        self.assertIn("hors couverture", diagnostic[organisations.DELIBERATIONS])


class TestExecuterRun(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.dossier_sortie = self._tmp.name
        self.chemin_etat = f"{self._tmp.name}/etat.json"
        self.modes = {organisations.POPULATION: "source"}
        patcher_rapprochement = mock.patch(
            "rudi_commune_starterkit.cli.resoudre_organisations_producteurs",
            return_value=({}, None),
        )
        patcher_rapprochement.start()
        self.addCleanup(patcher_rapprochement.stop)
        patcher_connexion = mock.patch(
            "rudi_commune_starterkit.cli.tester_connexion_noeud", return_value=True,
        )
        patcher_connexion.start()
        self.addCleanup(patcher_connexion.stop)
        patcher_pause = mock.patch("rudi_commune_starterkit.cli.time.sleep")
        patcher_pause.start()
        self.addCleanup(patcher_pause.stop)
        # Sans ce patch, executer_run() ferait un vrai appel réseau Wikipédia/Wikidata
        # (resumer_commune_wikipedia(), via construire_description_commune()) à chaque
        # test de cette classe et de TestExecuterRunGardeFouOrganisation.
        patcher_description = mock.patch(
            "rudi_commune_starterkit.cli.construire_description_commune",
            return_value={"organization_summary": "Résumé de test.",
                          "source": "wikipedia", "url": "https://fr.wikipedia.org/wiki/Test"},
        )
        patcher_description.start()
        self.addCleanup(patcher_description.stop)

    def _executer(self, **override):
        kwargs = dict(
            commune=_GEVEZE, conf=_CONF, modes_par_jdd=self.modes,
            contact_email_commune=None, forcer_maj=False,
            only={organisations.POPULATION}, skip=None, dry_run=False,
            dossier_sortie=self.dossier_sortie, chemin_etat=self.chemin_etat,
        )
        kwargs.update(override)
        return cli.executer_run(**kwargs)

    def test_only_cle_inconnue_echoue_au_lieu_de_ne_rien_faire(self):
        """Bug réel corrigé le 2026-11-14 : une clé inconnue (typo) dans --only ne
        sélectionnait silencieusement aucun module — le run "réussissait"
        (EXIT_SUCCES) sans avoir rien publié ni avertir de quoi que ce soit."""
        code = self._executer(only={"populaton"})
        self.assertEqual(code, cli.EXIT_ECHEC_TOTAL)

    def test_skip_cle_inconnue_echoue(self):
        code = self._executer(only=None, skip={"populaton"})
        self.assertEqual(code, cli.EXIT_ECHEC_TOTAL)

    def test_publication_nouvelle(self):
        with mock.patch.object(
            population, "moissonner",
            return_value=ResultatConnecteur(StatutConnecteur.PUBLIABLE, rudi_metadata=_metadata()),
        ), mock.patch("rudi_commune_starterkit.cli.publier_si_configue", return_value=True) as m_pub:
            code = self._executer()
        self.assertEqual(code, cli.EXIT_SUCCES)
        m_pub.assert_called_once()

    def test_sans_republication_si_hash_inchange(self):
        with mock.patch.object(
            population, "moissonner",
            return_value=ResultatConnecteur(StatutConnecteur.PUBLIABLE, rudi_metadata=_metadata()),
        ), mock.patch("rudi_commune_starterkit.cli.publier_si_configue", return_value=True) as m_pub:
            self._executer()
            m_pub.reset_mock()
            code = self._executer()
        self.assertEqual(code, cli.EXIT_SUCCES)
        m_pub.assert_not_called()

    def test_forcer_maj_republie_malgre_hash_inchange(self):
        with mock.patch.object(
            population, "moissonner",
            return_value=ResultatConnecteur(StatutConnecteur.PUBLIABLE, rudi_metadata=_metadata()),
        ), mock.patch("rudi_commune_starterkit.cli.publier_si_configue", return_value=True) as m_pub:
            self._executer()
            m_pub.reset_mock()
            code = self._executer(forcer_maj=True)
        self.assertEqual(code, cli.EXIT_SUCCES)
        m_pub.assert_called_once()

    def test_vide_ne_publie_pas(self):
        with mock.patch.object(
            population, "moissonner", return_value=ResultatConnecteur(StatutConnecteur.VIDE),
        ), mock.patch("rudi_commune_starterkit.cli.publier_si_configue") as m_pub:
            code = self._executer()
        self.assertEqual(code, cli.EXIT_SUCCES)
        m_pub.assert_not_called()

    def test_hors_couverture_ne_publie_pas(self):
        with mock.patch.object(
            population, "moissonner",
            return_value=ResultatConnecteur(StatutConnecteur.HORS_COUVERTURE),
        ), mock.patch("rudi_commune_starterkit.cli.publier_si_configue") as m_pub:
            code = self._executer()
        self.assertEqual(code, cli.EXIT_SUCCES)
        m_pub.assert_not_called()

    def test_echec_total_sans_aucun_succes(self):
        with mock.patch.object(
            population, "moissonner",
            return_value=ResultatConnecteur(StatutConnecteur.ECHEC, message="panne"),
        ):
            code = self._executer()
        self.assertEqual(code, cli.EXIT_ECHEC_TOTAL)

    def test_dry_run_ne_publie_pas_et_ne_sauvegarde_pas_etat(self):
        with mock.patch.object(
            population, "moissonner",
            return_value=ResultatConnecteur(StatutConnecteur.PUBLIABLE, rudi_metadata=_metadata()),
        ), mock.patch("rudi_commune_starterkit.cli.publier_si_configue") as m_pub, \
           mock.patch("rudi_commune_starterkit.cli.sauvegarder_etat") as m_save:
            code = self._executer(dry_run=True)
        self.assertEqual(code, cli.EXIT_SUCCES)
        m_pub.assert_not_called()
        m_save.assert_not_called()

    def test_organisation_id_injecte_si_rapproche(self):
        metadata = _metadata("INSEE")
        with mock.patch(
            "rudi_commune_starterkit.cli.resoudre_organisations_producteurs",
            return_value=({"INSEE": {"organization_name": "INSEE", "organization_id": "oid-1"}}, None),
        ), mock.patch.object(
            population, "moissonner",
            return_value=ResultatConnecteur(StatutConnecteur.PUBLIABLE, rudi_metadata=metadata),
        ), mock.patch("rudi_commune_starterkit.cli.publier_si_configue", return_value=True):
            self._executer()
        self.assertEqual(metadata["producer"]["organization_id"], "oid-1")

class TestExecuterRunGardeFouOrganisation(TestExecuterRun):
    """Réutilise setUp()/_executer() de TestExecuterRun, mode commune pour POPULATION
    (producteur résolu == organisation_commune(_GEVEZE)) pour déclencher le garde-fou."""

    def setUp(self):
        super().setUp()
        self.modes = {organisations.POPULATION: "commune"}
        # Repli par défaut "organisation déjà validée" pour les tests hérités de
        # TestExecuterRun, qui ne testent pas le garde-fou lui-même : sans ce patch,
        # ils déclenchaient un vrai appel réseau vers l'hôte factice "noeud" (échec
        # DNS), et ne passaient que par accident grâce à l'ancien comportement
        # fail-open corrigé le 2026-11-14 (voir
        # test_echec_de_verification_bloque_au_lieu_de_forcer_validee). Chaque test
        # qui teste vraiment le garde-fou écrase ce patch localement.
        patcher_organisation = mock.patch(
            "rudi_commune_starterkit.cli.organisation_existante",
            return_value={"organization_id": "o1", "organization_status": "VALIDATED",
                          "linked_producer_status": "VALIDATED"},
        )
        patcher_organisation.start()
        self.addCleanup(patcher_organisation.stop)

    def test_organisation_deja_tentee_ne_recree_pas(self):
        """Bug réel corrigé le 2026-11-17 (Grand-Fougeray, nœud preprod
        rudi-univ-rennes1) : l'organisation en attente de validation est invisible
        via GET /v1/organizations (endpoint public, ne liste que les organisations
        déjà validées) — vue comme « absente » à chaque nouvel appel. Sans ce
        paramètre, une 2e vérification recréait donc une organisation distincte sur
        un nœud qui n'honore pas l'id déterministe proposé."""
        with mock.patch(
            "rudi_commune_starterkit.cli.organisation_existante", return_value=None,
        ), mock.patch(
            "rudi_commune_starterkit.cli.demander_creation_organisation",
        ) as m_creer, mock.patch("builtins.input") as m_input, mock.patch.object(
            population, "moissonner",
        ) as m_moissonner:
            code = self._executer(contact_email_commune="mairie@geveze.fr",
                                   confirmer_creation_organisation=False,
                                   organisation_creation_deja_tentee=True)
        self.assertEqual(code, cli.EXIT_EN_ATTENTE_VALIDATION)
        m_creer.assert_not_called()
        m_input.assert_not_called()
        m_moissonner.assert_not_called()

    def test_organisation_absente_scriptable_cree_sans_prompt(self):
        with mock.patch(
            "rudi_commune_starterkit.cli.organisation_existante", return_value=None,
        ), mock.patch(
            "rudi_commune_starterkit.cli.demander_creation_organisation", return_value="org-1",
        ) as m_creer, mock.patch("builtins.input") as m_input, mock.patch.object(
            population, "moissonner",
        ) as m_moissonner:
            code = self._executer(contact_email_commune="mairie@geveze.fr",
                                   confirmer_creation_organisation=False)
        self.assertEqual(code, cli.EXIT_EN_ATTENTE_VALIDATION)
        m_creer.assert_called_once()
        m_input.assert_not_called()
        m_moissonner.assert_not_called()

    def test_organisation_creee_porte_la_description_resolue(self):
        desc = {"organization_summary": "Résumé Wikipédia de test.",
                "source": "wikipedia", "url": "https://fr.wikipedia.org/wiki/X"}
        with mock.patch(
            "rudi_commune_starterkit.cli.construire_description_commune", return_value=desc,
        ), mock.patch(
            "rudi_commune_starterkit.cli.organisation_existante", return_value=None,
        ), mock.patch(
            "rudi_commune_starterkit.cli.demander_creation_organisation", return_value="org-1",
        ) as m_creer, mock.patch("builtins.input") as m_input, mock.patch.object(
            population, "moissonner",
        ):
            self._executer(contact_email_commune="mairie@geveze.fr",
                            confirmer_creation_organisation=False)
        organisation_passee = m_creer.call_args.args[1]
        self.assertEqual(organisation_passee["organization_summary"], desc["organization_summary"])
        self.assertEqual(organisation_passee["organization_url"], desc["url"])

    def test_organisation_absente_interactif_confirme_puis_cree(self):
        with mock.patch(
            "rudi_commune_starterkit.cli.organisation_existante", return_value=None,
        ), mock.patch(
            "rudi_commune_starterkit.cli.demander_creation_organisation", return_value="org-1",
        ) as m_creer, mock.patch("builtins.input", return_value="o"), mock.patch.object(
            population, "moissonner",
        ) as m_moissonner:
            code = self._executer(contact_email_commune="mairie@geveze.fr")
        self.assertEqual(code, cli.EXIT_EN_ATTENTE_VALIDATION)
        m_creer.assert_called_once()
        m_moissonner.assert_not_called()

    def test_organisation_absente_interactif_refusee_ne_cree_pas(self):
        with mock.patch(
            "rudi_commune_starterkit.cli.organisation_existante", return_value=None,
        ), mock.patch(
            "rudi_commune_starterkit.cli.demander_creation_organisation",
        ) as m_creer, mock.patch("builtins.input", return_value="n"), mock.patch.object(
            population, "moissonner",
        ) as m_moissonner:
            code = self._executer(contact_email_commune="mairie@geveze.fr")
        self.assertEqual(code, cli.EXIT_EN_ATTENTE_VALIDATION)
        m_creer.assert_not_called()
        m_moissonner.assert_not_called()

    def test_echec_de_creation_est_un_echec_jamais_en_attente(self):
        with mock.patch(
            "rudi_commune_starterkit.cli.organisation_existante", return_value=None,
        ), mock.patch(
            "rudi_commune_starterkit.cli.demander_creation_organisation", return_value=None,
        ), mock.patch("builtins.input", return_value="o"), mock.patch.object(
            population, "moissonner",
        ) as m_moissonner:
            code = self._executer(contact_email_commune="mairie@geveze.fr")
        self.assertEqual(code, cli.EXIT_ECHEC_TOTAL)
        m_moissonner.assert_not_called()

    def test_organisation_en_attente_saute_le_module_sans_creer(self):
        org = {"organization_id": "o1", "organization_status": "DRAFT",
               "linked_producer_status": None}
        with mock.patch(
            "rudi_commune_starterkit.cli.organisation_existante", return_value=org,
        ), mock.patch(
            "rudi_commune_starterkit.cli.demander_creation_organisation",
        ) as m_creer, mock.patch.object(population, "moissonner") as m_moissonner:
            code = self._executer(contact_email_commune="mairie@geveze.fr")
        self.assertEqual(code, cli.EXIT_EN_ATTENTE_VALIDATION)
        m_creer.assert_not_called()
        m_moissonner.assert_not_called()

    def test_echec_de_verification_bloque_au_lieu_de_forcer_validee(self):
        """Bug réel corrigé le 2026-11-14 : une panne de vérification (réseau, auth...)
        forçait `etat_org = "validee"` — l'opposé du garde-fou fail-closed documenté
        par _etat_organisation_commune() — et publiait sous une organisation jamais
        vérifiée. Doit désormais bloquer comme "en_attente"."""
        with mock.patch(
            "rudi_commune_starterkit.cli.organisation_existante",
            side_effect=RuntimeError("panne réseau"),
        ), mock.patch(
            "rudi_commune_starterkit.cli.demander_creation_organisation",
        ) as m_creer, mock.patch.object(population, "moissonner") as m_moissonner:
            code = self._executer(contact_email_commune="mairie@geveze.fr")
        self.assertEqual(code, cli.EXIT_EN_ATTENTE_VALIDATION)
        m_creer.assert_not_called()
        m_moissonner.assert_not_called()

    def test_organisation_validee_ne_bloque_rien(self):
        org = {"organization_id": "o1", "organization_status": "VALIDATED",
               "linked_producer_status": "VALIDATED"}
        with mock.patch(
            "rudi_commune_starterkit.cli.organisation_existante", return_value=org,
        ), mock.patch.object(
            population, "moissonner",
            return_value=ResultatConnecteur(
                StatutConnecteur.PUBLIABLE,
                rudi_metadata=_metadata("Commune de Gévezé"),
            ),
        ), mock.patch("rudi_commune_starterkit.cli.publier_si_configue", return_value=True) as m_pub:
            code = self._executer(contact_email_commune="mairie@geveze.fr")
        self.assertEqual(code, cli.EXIT_SUCCES)
        m_pub.assert_called_once()

    def test_dry_run_organisation_absente_ne_cree_rien_code_zero(self):
        with mock.patch(
            "rudi_commune_starterkit.cli.organisation_existante", return_value=None,
        ), mock.patch(
            "rudi_commune_starterkit.cli.demander_creation_organisation",
        ) as m_creer, mock.patch("builtins.input") as m_input, mock.patch.object(
            population, "moissonner",
        ) as m_moissonner:
            code = self._executer(contact_email_commune="mairie@geveze.fr", dry_run=True)
        self.assertEqual(code, cli.EXIT_SUCCES)
        m_creer.assert_not_called()
        m_input.assert_not_called()
        m_moissonner.assert_not_called()

    def test_mode_source_ne_verifie_jamais_lorganisation(self):
        with mock.patch(
            "rudi_commune_starterkit.cli.organisation_existante",
        ) as m_verif, mock.patch.object(
            population, "moissonner",
            return_value=ResultatConnecteur(StatutConnecteur.PUBLIABLE, rudi_metadata=_metadata()),
        ), mock.patch("rudi_commune_starterkit.cli.publier_si_configue", return_value=True):
            self.modes = {organisations.POPULATION: "source"}
            self._executer()
        m_verif.assert_not_called()

    def test_description_commune_resolue_une_fois_et_transmise_au_module(self):
        # mode "commune" (déjà le défaut de cette classe) : seul cas où
        # resoudre_producer() utilise vraiment description_commune — voir
        # test_description_commune_non_calculee_si_aucun_module_ne_lutilise ci-dessous
        # pour le cas "source" (bug réel corrigé le 2026-11-14 : calculée même quand
        # inutile à aucun module sélectionné).
        desc = {"organization_summary": "Résumé spécifique au test.",
                "source": "wikipedia", "url": "https://fr.wikipedia.org/wiki/X"}
        with mock.patch(
            "rudi_commune_starterkit.cli.construire_description_commune", return_value=desc,
        ) as m_desc, mock.patch.object(
            population, "moissonner",
            return_value=ResultatConnecteur(StatutConnecteur.PUBLIABLE, rudi_metadata=_metadata()),
        ) as m_moissonner, mock.patch(
            "rudi_commune_starterkit.cli.publier_si_configue", return_value=True,
        ):
            self._executer()
        m_desc.assert_called_once()
        self.assertEqual(m_moissonner.call_args.kwargs["description_commune"], desc)

    def test_avertissement_affiche_si_repli_generique(self):
        desc = {"organization_summary": "Générique.", "source": "repli_generique", "url": None}
        with mock.patch(
            "rudi_commune_starterkit.cli.construire_description_commune", return_value=desc,
        ), mock.patch.object(
            population, "moissonner",
            return_value=ResultatConnecteur(StatutConnecteur.PUBLIABLE, rudi_metadata=_metadata()),
        ), mock.patch(
            "rudi_commune_starterkit.cli.publier_si_configue", return_value=True,
        ), mock.patch("builtins.print") as m_print:
            self._executer()
        self.assertTrue(
            any("repli" in str(appel) or "générique" in str(appel) for appel in m_print.call_args_list)
        )

    def test_description_commune_non_calculee_si_aucun_module_ne_lutilise(self):
        """Bug réel corrigé le 2026-11-14 : calculée inconditionnellement (appel
        Wikipédia + téléchargement RNE ~65 Mo) même en mode "source" (où
        resoudre_producer() ne l'utilise jamais) et même en --dry-run."""
        with mock.patch(
            "rudi_commune_starterkit.cli.construire_description_commune",
        ) as m_desc, mock.patch.object(
            population, "moissonner",
            return_value=ResultatConnecteur(StatutConnecteur.PUBLIABLE, rudi_metadata=_metadata()),
        ), mock.patch("rudi_commune_starterkit.cli.publier_si_configue", return_value=True):
            self.modes = {organisations.POPULATION: "source"}
            self._executer()
        m_desc.assert_not_called()


class TestTesterConnexionAvecRepliTls(unittest.TestCase):
    def test_succes_direct_ne_propose_rien(self):
        with mock.patch("rudi_commune_starterkit.cli.tester_connexion_noeud", return_value=True), \
             mock.patch("rudi_commune_starterkit.cli.confirmer") as m_confirmer:
            self.assertTrue(cli._tester_connexion_avec_repli_tls({"url": "https://x"}))
        m_confirmer.assert_not_called()

    def test_echec_non_tls_pas_de_proposition(self):
        with mock.patch("rudi_commune_starterkit.cli.tester_connexion_noeud", return_value=False), \
             mock.patch("rudi_commune_starterkit.cli.erreur_est_certificat_tls", return_value=False), \
             mock.patch("rudi_commune_starterkit.cli.confirmer") as m_confirmer:
            self.assertFalse(cli._tester_connexion_avec_repli_tls({"url": "https://x"}))
        m_confirmer.assert_not_called()

    def test_echec_tls_refuse_reste_en_echec(self):
        with mock.patch("rudi_commune_starterkit.cli.tester_connexion_noeud", return_value=False), \
             mock.patch("rudi_commune_starterkit.cli.erreur_est_certificat_tls", return_value=True), \
             mock.patch("rudi_commune_starterkit.cli.confirmer", return_value=False), \
             mock.patch("rudi_commune_starterkit.cli.desactiver_verification_tls_noeud") as m_desact:
            self.assertFalse(cli._tester_connexion_avec_repli_tls({"url": "https://x"}))
        m_desact.assert_not_called()

    def test_echec_tls_accepte_desactive_et_reessaie(self):
        with mock.patch("rudi_commune_starterkit.cli.tester_connexion_noeud",
                         side_effect=[False, True]) as m_test, \
             mock.patch("rudi_commune_starterkit.cli.erreur_est_certificat_tls", return_value=True), \
             mock.patch("rudi_commune_starterkit.cli.confirmer", return_value=True), \
             mock.patch("rudi_commune_starterkit.cli.desactiver_verification_tls_noeud") as m_desact:
            self.assertTrue(cli._tester_connexion_avec_repli_tls({"url": "https://x"}))
        m_desact.assert_called_once()
        self.assertEqual(m_test.call_count, 2)


class TestLireMotDePasseTrousseauAvecConfirmation(unittest.TestCase):
    def test_succes_direct_ne_propose_rien(self):
        with mock.patch("rudi_commune_starterkit.cli.lire_mot_de_passe_trousseau",
                         return_value="secret") as m_lire, \
             mock.patch("rudi_commune_starterkit.cli.confirmer") as m_confirmer:
            resultat = cli._lire_mot_de_passe_trousseau_avec_confirmation("https://x", "u")
        self.assertEqual(resultat, "secret")
        m_confirmer.assert_not_called()
        m_lire.assert_called_once_with("https://x", "u")

    def test_backend_en_clair_connu_ne_propose_rien_et_remonte(self):
        with mock.patch("rudi_commune_starterkit.cli.lire_mot_de_passe_trousseau",
                         side_effect=securite.TrousseauEnClairError("en clair")) as m_lire, \
             mock.patch("rudi_commune_starterkit.cli.confirmer") as m_confirmer:
            with self.assertRaises(securite.TrousseauEnClairError):
                cli._lire_mot_de_passe_trousseau_avec_confirmation("https://x", "u")
        m_confirmer.assert_not_called()
        m_lire.assert_called_once_with("https://x", "u")

    def test_backend_non_reconnu_refuse_remonte_sans_contourner(self):
        with mock.patch("rudi_commune_starterkit.cli.lire_mot_de_passe_trousseau",
                         side_effect=securite.TrousseauBackendNonReconnuError("?")) as m_lire, \
             mock.patch("rudi_commune_starterkit.cli.confirmer", return_value=False):
            with self.assertRaises(securite.TrousseauBackendNonReconnuError):
                cli._lire_mot_de_passe_trousseau_avec_confirmation("https://x", "u")
        m_lire.assert_called_once_with("https://x", "u")

    def test_backend_non_reconnu_accepte_contourne_et_reessaie(self):
        with mock.patch("rudi_commune_starterkit.cli.lire_mot_de_passe_trousseau",
                         side_effect=[securite.TrousseauBackendNonReconnuError("?"), "secret"]) as m_lire, \
             mock.patch("rudi_commune_starterkit.cli.confirmer", return_value=True):
            resultat = cli._lire_mot_de_passe_trousseau_avec_confirmation("https://x", "u")
        self.assertEqual(resultat, "secret")
        self.assertEqual(m_lire.call_count, 2)
        m_lire.assert_called_with("https://x", "u", autoriser_backend_non_reconnu=True)


class TestEnregistrerMotDePasseTrousseauAvecConfirmation(unittest.TestCase):
    def test_succes_direct_ne_propose_rien(self):
        with mock.patch("rudi_commune_starterkit.cli.enregistrer_mot_de_passe_trousseau") as m_enr, \
             mock.patch("rudi_commune_starterkit.cli.confirmer") as m_confirmer:
            cli._enregistrer_mot_de_passe_trousseau_avec_confirmation("https://x", "u", "secret")
        m_confirmer.assert_not_called()
        m_enr.assert_called_once_with("https://x", "u", "secret")

    def test_backend_en_clair_connu_ne_propose_rien_et_remonte(self):
        with mock.patch("rudi_commune_starterkit.cli.enregistrer_mot_de_passe_trousseau",
                         side_effect=securite.TrousseauEnClairError("en clair")) as m_enr, \
             mock.patch("rudi_commune_starterkit.cli.confirmer") as m_confirmer:
            with self.assertRaises(securite.TrousseauEnClairError):
                cli._enregistrer_mot_de_passe_trousseau_avec_confirmation("https://x", "u", "secret")
        m_confirmer.assert_not_called()
        m_enr.assert_called_once_with("https://x", "u", "secret")

    def test_backend_non_reconnu_refuse_remonte_sans_contourner(self):
        with mock.patch("rudi_commune_starterkit.cli.enregistrer_mot_de_passe_trousseau",
                         side_effect=securite.TrousseauBackendNonReconnuError("?")) as m_enr, \
             mock.patch("rudi_commune_starterkit.cli.confirmer", return_value=False):
            with self.assertRaises(securite.TrousseauBackendNonReconnuError):
                cli._enregistrer_mot_de_passe_trousseau_avec_confirmation("https://x", "u", "secret")
        m_enr.assert_called_once_with("https://x", "u", "secret")

    def test_backend_non_reconnu_accepte_contourne_et_reessaie(self):
        with mock.patch("rudi_commune_starterkit.cli.enregistrer_mot_de_passe_trousseau",
                         side_effect=[securite.TrousseauBackendNonReconnuError("?"), None]) as m_enr, \
             mock.patch("rudi_commune_starterkit.cli.confirmer", return_value=True):
            cli._enregistrer_mot_de_passe_trousseau_avec_confirmation("https://x", "u", "secret")
        self.assertEqual(m_enr.call_count, 2)
        m_enr.assert_called_with("https://x", "u", "secret", autoriser_backend_non_reconnu=True)


class TestResoudreConfScriptable(unittest.TestCase):
    def test_rudi_conf_fichier(self):
        args = argparse.Namespace(rudi_conf="conf.json", url_noeud=None, usr=None,
                                   utiliser_trousseau=False, autoriser_http_local=False)
        with mock.patch("rudi_commune_starterkit.cli.verifier_permissions_conf"), \
             mock.patch("rudi_commune_starterkit.cli.charger_conf_rudi",
                         return_value={"url": "https://x", "usr": "u", "pwd": "p"}):
            conf = cli._resoudre_conf_scriptable(args)
        self.assertEqual(conf["usr"], "u")

    def test_rudi_conf_url_http_non_locale_refusee(self):
        """Bug réel corrigé le 2026-11-14 : --rudi-conf contournait entièrement la
        protection http:// appliquée à --url-noeud (identifiants en clair sur le
        réseau)."""
        args = argparse.Namespace(rudi_conf="conf.json", url_noeud=None, usr=None,
                                   utiliser_trousseau=False, autoriser_http_local=False)
        with mock.patch("rudi_commune_starterkit.cli.verifier_permissions_conf"), \
             mock.patch("rudi_commune_starterkit.cli.charger_conf_rudi",
                         return_value={"url": "http://noeud-externe.example", "usr": "u", "pwd": "p"}):
            with self.assertRaises(cli.UrlNoeudNonSecurisee):
                cli._resoudre_conf_scriptable(args)

    def test_rudi_conf_url_portail_http_non_locale_refusee(self):
        args = argparse.Namespace(rudi_conf="conf.json", url_noeud=None, usr=None,
                                   utiliser_trousseau=False, autoriser_http_local=False)
        with mock.patch("rudi_commune_starterkit.cli.verifier_permissions_conf"), \
             mock.patch("rudi_commune_starterkit.cli.charger_conf_rudi",
                         return_value={"url": "https://noeud", "usr": "u", "pwd": "p",
                                       "url_portail": "http://portail-externe.example"}):
            with self.assertRaises(cli.UrlNoeudNonSecurisee):
                cli._resoudre_conf_scriptable(args)

    def test_rudi_conf_url_http_locale_acceptee_avec_flag(self):
        """Bug réel trouvé le 2026-11-15 : --rudi-conf (donc tout usage scriptable,
        y compris starterkit-tester) refusait http://localhost même avec le nœud/
        portail de dev visés, faute d'un flag équivalent à autoriser_http_local du
        mode interactif — --autoriser-http-local corrige ça."""
        args = argparse.Namespace(rudi_conf="conf.json", url_noeud=None, usr=None,
                                   utiliser_trousseau=False, autoriser_http_local=True)
        with mock.patch("rudi_commune_starterkit.cli.verifier_permissions_conf"), \
             mock.patch("rudi_commune_starterkit.cli.charger_conf_rudi",
                         return_value={"url": "http://localhost:4032", "usr": "u", "pwd": "p",
                                       "url_portail": "http://rudi.localhost"}):
            conf = cli._resoudre_conf_scriptable(args)
        self.assertEqual(conf["url"], "http://localhost:4032")
        self.assertEqual(conf["url_portail"], "http://rudi.localhost")

    def test_sans_rudi_conf_ni_url_leve(self):
        args = argparse.Namespace(rudi_conf=None, url_noeud=None, usr=None,
                                   utiliser_trousseau=False, autoriser_http_local=False)
        with self.assertRaises(ValueError):
            cli._resoudre_conf_scriptable(args)

    def test_sans_trousseau_ni_conf_leve(self):
        args = argparse.Namespace(rudi_conf=None, url_noeud="https://x", usr="u",
                                   utiliser_trousseau=False, autoriser_http_local=False)
        with self.assertRaises(ValueError):
            cli._resoudre_conf_scriptable(args)

    def test_trousseau_sans_mot_de_passe_enregistre_leve(self):
        args = argparse.Namespace(rudi_conf=None, url_noeud="https://x", usr="u",
                                   utiliser_trousseau=True,
                                   autoriser_backend_trousseau_non_reconnu=False, autoriser_http_local=False)
        with mock.patch("rudi_commune_starterkit.cli.lire_mot_de_passe_trousseau", return_value=None):
            with self.assertRaises(ValueError):
                cli._resoudre_conf_scriptable(args)

    def test_trousseau_ok(self):
        args = argparse.Namespace(rudi_conf=None, url_noeud="https://x", usr="u",
                                   utiliser_trousseau=True,
                                   autoriser_backend_trousseau_non_reconnu=False, autoriser_http_local=False)
        with mock.patch("rudi_commune_starterkit.cli.lire_mot_de_passe_trousseau", return_value="secret") as m:
            conf = cli._resoudre_conf_scriptable(args)
        self.assertEqual(conf["pwd"], "secret")
        m.assert_called_once_with("https://x", "u", autoriser_backend_non_reconnu=False)

    def test_trousseau_autorise_backend_non_reconnu_transmis(self):
        args = argparse.Namespace(rudi_conf=None, url_noeud="https://x", usr="u",
                                   utiliser_trousseau=True,
                                   autoriser_backend_trousseau_non_reconnu=True, autoriser_http_local=False)
        with mock.patch("rudi_commune_starterkit.cli.lire_mot_de_passe_trousseau", return_value="secret") as m:
            cli._resoudre_conf_scriptable(args)
        m.assert_called_once_with("https://x", "u", autoriser_backend_non_reconnu=True)


class TestExecuterScriptable(unittest.TestCase):
    def test_sans_code_insee_echec(self):
        args = cli._construire_parser().parse_args([])
        self.assertEqual(cli.executer_scriptable(args), cli.EXIT_ECHEC_TOTAL)

    def test_commune_sans_contact_email_echec(self):
        args = cli._construire_parser().parse_args([
            "--code-insee", "35120", "--rudi-conf", "conf.json",
            "--organisation-producteur", "commune",
        ])
        with mock.patch("rudi_commune_starterkit.cli._resoudre_conf_scriptable", return_value=_CONF), \
             mock.patch("rudi_commune_starterkit.cli.resoudre_commune", return_value=_GEVEZE):
            code = cli.executer_scriptable(args)
        self.assertEqual(code, cli.EXIT_ECHEC_TOTAL)

    def test_noeud_injoignable_echec(self):
        args = cli._construire_parser().parse_args([
            "--code-insee", "35120", "--rudi-conf", "conf.json",
        ])
        with mock.patch("rudi_commune_starterkit.cli._resoudre_conf_scriptable", return_value=_CONF), \
             mock.patch("rudi_commune_starterkit.cli.resoudre_commune", return_value=_GEVEZE), \
             mock.patch("rudi_commune_starterkit.cli.tester_connexion_noeud", return_value=False):
            code = cli.executer_scriptable(args)
        self.assertEqual(code, cli.EXIT_ECHEC_TOTAL)

    def test_nominal_delegue_a_executer_run(self):
        args = cli._construire_parser().parse_args([
            "--code-insee", "35120", "--rudi-conf", "conf.json", "--only", "population",
        ])
        with mock.patch("rudi_commune_starterkit.cli._resoudre_conf_scriptable", return_value=_CONF), \
             mock.patch("rudi_commune_starterkit.cli.resoudre_commune", return_value=_GEVEZE), \
             mock.patch("rudi_commune_starterkit.cli.tester_connexion_noeud", return_value=True), \
             mock.patch("rudi_commune_starterkit.cli.executer_run", return_value=0) as m_run:
            code = cli.executer_scriptable(args)
        self.assertEqual(code, 0)
        m_run.assert_called_once()
        self.assertEqual(m_run.call_args.kwargs["only"], {"population"})

    def test_certificat_tls_non_reconnu_sans_flag_echec(self):
        # Certificat auto-signé détecté mais --ignorer-certificat-tls absent : échec
        # explicite, jamais de contournement silencieux.
        args = cli._construire_parser().parse_args([
            "--code-insee", "35120", "--rudi-conf", "conf.json",
        ])
        with mock.patch("rudi_commune_starterkit.cli._resoudre_conf_scriptable", return_value=_CONF), \
             mock.patch("rudi_commune_starterkit.cli.resoudre_commune", return_value=_GEVEZE), \
             mock.patch("rudi_commune_starterkit.cli.tester_connexion_noeud", return_value=False), \
             mock.patch("rudi_commune_starterkit.cli.erreur_est_certificat_tls", return_value=True), \
             mock.patch("rudi_commune_starterkit.cli.desactiver_verification_tls_noeud") as m_desact:
            code = cli.executer_scriptable(args)
        self.assertEqual(code, cli.EXIT_ECHEC_TOTAL)
        m_desact.assert_not_called()

    def test_certificat_tls_non_reconnu_avec_flag_reessaie(self):
        # Avec --ignorer-certificat-tls : désactive la vérification TLS puis
        # retente la connexion avant de poursuivre.
        args = cli._construire_parser().parse_args([
            "--code-insee", "35120", "--rudi-conf", "conf.json", "--ignorer-certificat-tls",
            "--only", "population",
        ])
        with mock.patch("rudi_commune_starterkit.cli._resoudre_conf_scriptable", return_value=_CONF), \
             mock.patch("rudi_commune_starterkit.cli.resoudre_commune", return_value=_GEVEZE), \
             mock.patch("rudi_commune_starterkit.cli.tester_connexion_noeud",
                        side_effect=[False, True]) as m_test, \
             mock.patch("rudi_commune_starterkit.cli.erreur_est_certificat_tls", return_value=True), \
             mock.patch("rudi_commune_starterkit.cli.desactiver_verification_tls_noeud") as m_desact, \
             mock.patch("rudi_commune_starterkit.cli.executer_run", return_value=0):
            code = cli.executer_scriptable(args)
        self.assertEqual(code, 0)
        m_desact.assert_called_once()
        self.assertEqual(m_test.call_count, 2)


class TestExecuterScriptableViderCommune(unittest.TestCase):
    def test_supprimer_organisation_sans_vider_commune_echec(self):
        args = cli._construire_parser().parse_args([
            "--code-insee", "35120", "--supprimer-organisation",
        ])
        self.assertEqual(cli.executer_scriptable(args), cli.EXIT_ECHEC_TOTAL)

    def test_url_portail_http_non_locale_refusee(self):
        """Bug réel corrigé le 2026-11-14 : url_portail (--url-portail ou profil du
        registre) n'était jamais validée, contrairement à url_noeud."""
        args = cli._construire_parser().parse_args([
            "--code-insee", "35120", "--rudi-conf", "conf.json", "--vider-commune",
            "--url-portail", "http://portail-externe.example", "--confirmer", "SUPPRIMER",
        ])
        with mock.patch("rudi_commune_starterkit.cli._resoudre_conf_scriptable", return_value=dict(_CONF)):
            code = cli.executer_scriptable(args)
        self.assertEqual(code, cli.EXIT_ECHEC_TOTAL)

    def test_delegue_a_vider_commune_et_fusionne_url_portail(self):
        args = cli._construire_parser().parse_args([
            "--code-insee", "35120", "--rudi-conf", "conf.json", "--vider-commune",
            "--url-portail", "https://portail", "--confirmer", "SUPPRIMER",
        ])
        rapport = {"jdd_supprimes": ["lid-1"], "jdd_echecs": [], "jdd_tiers_supprimes": [], "jdd_tiers_echecs": [], "organisation": None,
                   "message": "ok"}
        with mock.patch("rudi_commune_starterkit.cli._resoudre_conf_scriptable", return_value=dict(_CONF)), \
             mock.patch("rudi_commune_starterkit.cli.vider_commune", return_value=rapport) as m_vider:
            code = cli.executer_scriptable(args)
        self.assertEqual(code, cli.EXIT_SUCCES)
        m_vider.assert_called_once()
        self.assertEqual(m_vider.call_args.args[0]["url_portail"], "https://portail")
        self.assertFalse(m_vider.call_args.kwargs["supprimer_organisation"])

    def test_jdd_en_echec_rapporte_echecs_partiels(self):
        args = cli._construire_parser().parse_args([
            "--code-insee", "35120", "--rudi-conf", "conf.json", "--vider-commune",
            "--url-portail", "https://portail",
        ])
        rapport = {"jdd_supprimes": [], "jdd_echecs": ["lid-1"], "jdd_tiers_supprimes": [], "jdd_tiers_echecs": [], "organisation": None,
                   "message": "échec"}
        with mock.patch("rudi_commune_starterkit.cli._resoudre_conf_scriptable", return_value=dict(_CONF)), \
             mock.patch("rudi_commune_starterkit.cli.vider_commune", return_value=rapport):
            code = cli.executer_scriptable(args)
        self.assertEqual(code, cli.EXIT_ECHECS_PARTIELS)

    def test_organisation_en_attente_de_detachement_rapporte_attente_validation(self):
        """Bug réel corrigé le 2026-11-14 : le mode scriptable traitait ce statut
        d'attente (pas un échec, un rendez-vous à reprendre une fois l'animateur
        passé) comme un échec partiel — incohérent avec le mode interactif, qui ne le
        traite pas comme un échec (voir TestViderCommuneInteractifAttenteDetachement).
        Même code que l'attente de validation côté publication (EXIT_EN_ATTENTE_VALIDATION)."""
        args = cli._construire_parser().parse_args([
            "--code-insee", "35120", "--rudi-conf", "conf.json", "--vider-commune",
            "--supprimer-organisation", "--url-portail", "https://portail",
            "--confirmer", "SUPPRIMER",
        ])
        rapport = {"jdd_supprimes": ["lid-1"], "jdd_echecs": [], "jdd_tiers_supprimes": [], "jdd_tiers_echecs": [],
                   "organisation": "detachement_demande", "message": "en attente"}
        with mock.patch("rudi_commune_starterkit.cli._resoudre_conf_scriptable", return_value=dict(_CONF)), \
             mock.patch("rudi_commune_starterkit.cli.vider_commune", return_value=rapport):
            code = cli.executer_scriptable(args)
        self.assertEqual(code, cli.EXIT_EN_ATTENTE_VALIDATION)

    def test_organisation_deja_absente_est_un_succes_pas_un_echec(self):
        """Même bug : "deja_absente" (rien à faire, organisation déjà supprimée) était
        traité comme un échec partiel en mode scriptable faute de check explicite."""
        args = cli._construire_parser().parse_args([
            "--code-insee", "35120", "--rudi-conf", "conf.json", "--vider-commune",
            "--supprimer-organisation", "--url-portail", "https://portail",
            "--confirmer", "SUPPRIMER",
        ])
        rapport = {"jdd_supprimes": ["lid-1"], "jdd_echecs": [], "jdd_tiers_supprimes": [], "jdd_tiers_echecs": [],
                   "organisation": "deja_absente", "message": "déjà absente"}
        with mock.patch("rudi_commune_starterkit.cli._resoudre_conf_scriptable", return_value=dict(_CONF)), \
             mock.patch("rudi_commune_starterkit.cli.vider_commune", return_value=rapport):
            code = cli.executer_scriptable(args)
        self.assertEqual(code, cli.EXIT_SUCCES)

    def test_echec_suppression_noeud_rapporte_echecs_partiels(self):
        args = cli._construire_parser().parse_args([
            "--code-insee", "35120", "--rudi-conf", "conf.json", "--vider-commune",
            "--supprimer-organisation", "--url-portail", "https://portail",
            "--confirmer", "SUPPRIMER",
        ])
        rapport = {"jdd_supprimes": ["lid-1"], "jdd_echecs": [], "jdd_tiers_supprimes": [], "jdd_tiers_echecs": [],
                   "organisation": "echec_suppression_noeud", "message": "refusé"}
        with mock.patch("rudi_commune_starterkit.cli._resoudre_conf_scriptable", return_value=dict(_CONF)), \
             mock.patch("rudi_commune_starterkit.cli.vider_commune", return_value=rapport):
            code = cli.executer_scriptable(args)
        self.assertEqual(code, cli.EXIT_ECHECS_PARTIELS)

    def test_organisation_supprimee_avec_succes_complet(self):
        args = cli._construire_parser().parse_args([
            "--code-insee", "35120", "--rudi-conf", "conf.json", "--vider-commune",
            "--supprimer-organisation", "--url-portail", "https://portail",
            "--confirmer", "SUPPRIMER",
        ])
        rapport = {"jdd_supprimes": ["lid-1"], "jdd_echecs": [], "jdd_tiers_supprimes": [], "jdd_tiers_echecs": [],
                   "organisation": "supprimee", "message": "ok"}
        with mock.patch("rudi_commune_starterkit.cli._resoudre_conf_scriptable", return_value=dict(_CONF)), \
             mock.patch("rudi_commune_starterkit.cli.vider_commune", return_value=rapport):
            code = cli.executer_scriptable(args)
        self.assertEqual(code, cli.EXIT_SUCCES)

    def test_confirmation_scriptable_transmise_au_confirmer_fn(self):
        args = cli._construire_parser().parse_args([
            "--code-insee", "35120", "--rudi-conf", "conf.json", "--vider-commune",
            "--url-portail", "https://portail", "--confirmer", "SUPPRIMER",
        ])
        with mock.patch("rudi_commune_starterkit.cli._resoudre_conf_scriptable", return_value=dict(_CONF)), \
             mock.patch("rudi_commune_starterkit.cli.vider_commune") as m_vider:
            m_vider.return_value = {"jdd_supprimes": [], "jdd_echecs": [], "jdd_tiers_supprimes": [], "jdd_tiers_echecs": [], "organisation": None, "message": None}
            cli.executer_scriptable(args)
        confirmer_fn = m_vider.call_args.kwargs["confirmer_fn"]
        with mock.patch("rudi_commune_starterkit.cli.confirmer", return_value="appelé") as m_confirmer:
            confirmer_fn("message", mot_attendu="SUPPRIMER")
        m_confirmer.assert_called_once_with(
            "message", mot_attendu="SUPPRIMER", confirmation_scriptable="SUPPRIMER",
        )


_PROFIL_GEVEZE = {
    "code_insee": "35120", "nom": "Gévezé", "url_noeud": "https://noeud",
    "usr": "u", "url_catalog": None, "mode_producteur": "commune",
    "organisation_par_jdd": None, "contact_email_commune": "mairie@geveze.fr",
    "url_portail": None,
}


class TestExecuterScriptableDepuisRegistre(unittest.TestCase):
    def test_profil_absent_echec(self):
        args = cli._construire_parser().parse_args(["--code-insee", "35120", "--depuis-registre"])
        with mock.patch("rudi_commune_starterkit.cli.charger_profils", return_value=[]):
            code = cli.executer_scriptable(args)
        self.assertEqual(code, cli.EXIT_ECHEC_TOTAL)

    def test_ambiguite_sans_url_noeud_echec(self):
        args = cli._construire_parser().parse_args(["--code-insee", "35120", "--depuis-registre"])
        profils = [
            {**_PROFIL_GEVEZE, "url_noeud": "https://a.fr"},
            {**_PROFIL_GEVEZE, "url_noeud": "https://b.fr"},
        ]
        with mock.patch("rudi_commune_starterkit.cli.charger_profils", return_value=profils):
            code = cli.executer_scriptable(args)
        self.assertEqual(code, cli.EXIT_ECHEC_TOTAL)

    def test_ambiguite_desambiguisee_par_url_noeud(self):
        args = cli._construire_parser().parse_args([
            "--code-insee", "35120", "--depuis-registre", "--url-noeud", "https://b.fr", "--only", "population",
        ])
        profils = [
            {**_PROFIL_GEVEZE, "url_noeud": "https://a.fr", "contact_email_commune": "a@x.fr"},
            {**_PROFIL_GEVEZE, "url_noeud": "https://b.fr", "contact_email_commune": "b@x.fr"},
        ]
        with mock.patch("rudi_commune_starterkit.cli.charger_profils", return_value=profils), \
             mock.patch("rudi_commune_starterkit.cli.lire_mot_de_passe_trousseau", return_value="secret"), \
             mock.patch("rudi_commune_starterkit.cli.resoudre_commune", return_value=_GEVEZE), \
             mock.patch("rudi_commune_starterkit.cli.tester_connexion_noeud", return_value=True), \
             mock.patch("rudi_commune_starterkit.cli.executer_run", return_value=0) as m_run:
            code = cli.executer_scriptable(args)
        self.assertEqual(code, 0)
        self.assertEqual(m_run.call_args.kwargs["contact_email_commune"], "b@x.fr")

    def test_profil_unique_utilise_sans_url_noeud(self):
        args = cli._construire_parser().parse_args([
            "--code-insee", "35120", "--depuis-registre", "--only", "population",
        ])
        with mock.patch("rudi_commune_starterkit.cli.charger_profils", return_value=[_PROFIL_GEVEZE]), \
             mock.patch("rudi_commune_starterkit.cli.lire_mot_de_passe_trousseau", return_value="secret") as m_pwd, \
             mock.patch("rudi_commune_starterkit.cli.resoudre_commune", return_value=_GEVEZE), \
             mock.patch("rudi_commune_starterkit.cli.tester_connexion_noeud", return_value=True), \
             mock.patch("rudi_commune_starterkit.cli.executer_run", return_value=0) as m_run:
            code = cli.executer_scriptable(args)
        self.assertEqual(code, 0)
        m_pwd.assert_called_once_with(
            _PROFIL_GEVEZE["url_noeud"], _PROFIL_GEVEZE["usr"], autoriser_backend_non_reconnu=False,
        )
        self.assertEqual(
            m_run.call_args.kwargs["modes_par_jdd"][organisations.POPULATION],
            _PROFIL_GEVEZE["mode_producteur"],
        )

    def test_contact_commune_explicite_gagne_sur_le_profil(self):
        """Bug réel corrigé le 2026-11-14 : --contact-commune et
        --organisation-producteur explicites étaient écrasés par le profil."""
        args = cli._construire_parser().parse_args([
            "--code-insee", "35120", "--depuis-registre", "--only", "population",
            "--contact-commune", "explicite@mairie.fr", "--organisation-producteur", "source",
        ])
        self.assertEqual(_PROFIL_GEVEZE["mode_producteur"], "commune")
        with mock.patch("rudi_commune_starterkit.cli.charger_profils", return_value=[_PROFIL_GEVEZE]), \
             mock.patch("rudi_commune_starterkit.cli.lire_mot_de_passe_trousseau", return_value="secret"), \
             mock.patch("rudi_commune_starterkit.cli.resoudre_commune", return_value=_GEVEZE), \
             mock.patch("rudi_commune_starterkit.cli.tester_connexion_noeud", return_value=True), \
             mock.patch("rudi_commune_starterkit.cli.executer_run", return_value=0) as m_run:
            code = cli.executer_scriptable(args)
        self.assertEqual(code, 0)
        self.assertEqual(m_run.call_args.kwargs["contact_email_commune"], "explicite@mairie.fr")
        self.assertEqual(
            m_run.call_args.kwargs["modes_par_jdd"][organisations.POPULATION], "source",
        )


class TestExecuterDepuisProfil(unittest.TestCase):
    def test_confirmation_simple_lance_executer_run(self):
        with mock.patch("rudi_commune_starterkit.cli.resoudre_commune", return_value=_GEVEZE), \
             mock.patch("rudi_commune_starterkit.cli.lire_mot_de_passe_trousseau", return_value="secret"), \
             mock.patch("rudi_commune_starterkit.cli.tester_connexion_noeud", return_value=True), \
             mock.patch("rudi_commune_starterkit.cli.enregistrer_profil") as m_enreg, \
             mock.patch("rudi_commune_starterkit.cli.executer_run", return_value=0) as m_run, \
             mock.patch("builtins.input", side_effect=["", "non"]):
            code = cli._executer_depuis_profil(_PROFIL_GEVEZE, "/chemin/profils.json")
        self.assertEqual(code, 0)
        m_run.assert_called_once()
        kwargs = m_run.call_args.kwargs
        self.assertEqual(kwargs["conf"]["pwd"], "secret")
        self.assertEqual(kwargs["contact_email_commune"], "mairie@geveze.fr")
        self.assertEqual(kwargs["modes_par_jdd"][organisations.POPULATION], "commune")
        m_enreg.assert_called_once()

    def test_mot_de_passe_absent_du_trousseau_redemande(self):
        with mock.patch("rudi_commune_starterkit.cli.resoudre_commune", return_value=_GEVEZE), \
             mock.patch("rudi_commune_starterkit.cli.lire_mot_de_passe_trousseau", return_value=None), \
             mock.patch("rudi_commune_starterkit.cli.lire_mot_de_passe", return_value="nouveau") as m_pwd, \
             mock.patch("rudi_commune_starterkit.cli.tester_connexion_noeud", return_value=True), \
             mock.patch("rudi_commune_starterkit.cli.enregistrer_profil"), \
             mock.patch("rudi_commune_starterkit.cli.executer_run", return_value=0) as m_run, \
             mock.patch("builtins.input", side_effect=["", "non"]):
            cli._executer_depuis_profil(_PROFIL_GEVEZE, "/chemin/profils.json")
        m_pwd.assert_called_once()
        self.assertEqual(m_run.call_args.kwargs["conf"]["pwd"], "nouveau")

    def test_echec_connexion_narrete_sans_executer_run(self):
        with mock.patch("rudi_commune_starterkit.cli.resoudre_commune", return_value=_GEVEZE), \
             mock.patch("rudi_commune_starterkit.cli.lire_mot_de_passe_trousseau", return_value="secret"), \
             mock.patch("rudi_commune_starterkit.cli.tester_connexion_noeud", return_value=False), \
             mock.patch("rudi_commune_starterkit.cli.executer_run") as m_run, \
             mock.patch("builtins.input", side_effect=[""]):
            code = cli._executer_depuis_profil(_PROFIL_GEVEZE, "/chemin/profils.json")
        self.assertEqual(code, cli.EXIT_ECHEC_TOTAL)
        m_run.assert_not_called()

    def test_correction_du_contact_avant_de_continuer(self):
        with mock.patch("rudi_commune_starterkit.cli.resoudre_commune", return_value=_GEVEZE), \
             mock.patch("rudi_commune_starterkit.cli.lire_mot_de_passe_trousseau", return_value="secret"), \
             mock.patch("rudi_commune_starterkit.cli.tester_connexion_noeud", return_value=True), \
             mock.patch("rudi_commune_starterkit.cli.enregistrer_profil"), \
             mock.patch("rudi_commune_starterkit.cli.executer_run", return_value=0) as m_run, \
             mock.patch(
                 "builtins.input",
                 side_effect=["contact", "nouveau@geveze.fr", "", "non"],
             ):
            cli._executer_depuis_profil(_PROFIL_GEVEZE, "/chemin/profils.json")
        self.assertEqual(m_run.call_args.kwargs["contact_email_commune"], "nouveau@geveze.fr")


_GEVEZE_COMPLETE = {**_GEVEZE, "departement": "Ille-et-Vilaine", "region": "Bretagne", "population": 100}


class TestExecuterInteractifRegistre(unittest.TestCase):
    def test_sans_profil_enregistre_passe_directement_au_code_insee(self):
        with mock.patch("rudi_commune_starterkit.cli.charger_profils", return_value=[]), \
             mock.patch("rudi_commune_starterkit.cli.resoudre_commune", return_value=_GEVEZE_COMPLETE), \
             mock.patch("builtins.input", side_effect=["35120"]):
            # S'arrête à la première question posée après le code INSEE (URL du nœud,
            # jamais saisie ici) : KeyboardInterrupt simulé par StopIteration sur input().
            with self.assertRaises(StopIteration):
                cli.executer_interactif()

    def test_choix_0_part_sur_nouvelle_commune(self):
        with mock.patch("rudi_commune_starterkit.cli.charger_profils", return_value=[_PROFIL_GEVEZE]), \
             mock.patch("rudi_commune_starterkit.cli.resoudre_commune", return_value=_GEVEZE_COMPLETE), \
             mock.patch("builtins.input", side_effect=["0", "35120"]):
            with self.assertRaises(StopIteration):
                cli.executer_interactif()

    def test_choix_dindex_reprend_le_profil(self):
        with mock.patch("rudi_commune_starterkit.cli.charger_profils", return_value=[_PROFIL_GEVEZE]), \
             mock.patch(
                 "rudi_commune_starterkit.cli._executer_depuis_profil", return_value=0,
             ) as m_reprise, \
             mock.patch("builtins.input", side_effect=["1", "1"]):
            code = cli.executer_interactif()
        self.assertEqual(code, 0)
        m_reprise.assert_called_once_with(_PROFIL_GEVEZE, cli.CHEMIN_PROFILS_DEFAUT)

    def test_choix_dindex_puis_action_2_route_vers_le_vidage(self):
        with mock.patch("rudi_commune_starterkit.cli.charger_profils", return_value=[_PROFIL_GEVEZE]), \
             mock.patch(
                 "rudi_commune_starterkit.cli._vider_commune_interactif", return_value=0,
             ) as m_vidage, \
             mock.patch("rudi_commune_starterkit.cli._executer_depuis_profil") as m_reprise, \
             mock.patch("builtins.input", side_effect=["1", "2"]):
            code = cli.executer_interactif()
        self.assertEqual(code, 0)
        m_vidage.assert_called_once_with(_PROFIL_GEVEZE, cli.CHEMIN_PROFILS_DEFAUT)
        m_reprise.assert_not_called()

    def test_profils_json_corrompu_arrete_proprement(self):
        with mock.patch(
            "rudi_commune_starterkit.cli.charger_profils", side_effect=ValueError("corrompu"),
        ):
            self.assertEqual(cli.executer_interactif(), cli.EXIT_ECHEC_TOTAL)

    def test_choix_q_quitte_proprement(self):
        """Backlog v5 : menu « Quitter » — jusqu'ici seul Ctrl+C permettait de sortir
        proprement de cette boucle."""
        with mock.patch("rudi_commune_starterkit.cli.charger_profils", return_value=[_PROFIL_GEVEZE]), \
             mock.patch("rudi_commune_starterkit.cli.resoudre_commune") as m_resoudre, \
             mock.patch("builtins.input", side_effect=["q"]):
            code = cli.executer_interactif()
        self.assertEqual(code, cli.EXIT_SUCCES)
        m_resoudre.assert_not_called()


class TestExecuterInteractifDetectionDoublonCommune(unittest.TestCase):
    """Backlog v5 : rien ne signalait qu'un profil existe déjà pour cette commune
    (éventuellement sur un autre nœud) quand on passe par « 0) Nouvelle commune »
    plutôt que par la liste de reprise."""

    def test_un_seul_profil_existant_et_acceptation_reprend_directement(self):
        with mock.patch("rudi_commune_starterkit.cli.charger_profils", return_value=[_PROFIL_GEVEZE]), \
             mock.patch("rudi_commune_starterkit.cli.resoudre_commune", return_value=_GEVEZE_COMPLETE), \
             mock.patch(
                 "rudi_commune_starterkit.cli._executer_depuis_profil", return_value=0,
             ) as m_reprise, \
             mock.patch("builtins.input", side_effect=["0", "35120", "o"]):
            code = cli.executer_interactif()
        self.assertEqual(code, 0)
        m_reprise.assert_called_once_with(_PROFIL_GEVEZE, cli.CHEMIN_PROFILS_DEFAUT)

    def test_un_seul_profil_existant_et_refus_poursuit_la_saisie(self):
        with mock.patch("rudi_commune_starterkit.cli.charger_profils", return_value=[_PROFIL_GEVEZE]), \
             mock.patch("rudi_commune_starterkit.cli.resoudre_commune", return_value=_GEVEZE_COMPLETE), \
             mock.patch(
                 "rudi_commune_starterkit.cli._executer_depuis_profil",
             ) as m_reprise, \
             mock.patch("builtins.input", side_effect=["0", "35120", "non"]):
            # S'arrête à la question suivante (URL du nœud, jamais saisie ici) : la
            # saisie se poursuit normalement après le refus de reprendre l'existant.
            with self.assertRaises(StopIteration):
                cli.executer_interactif()
        m_reprise.assert_not_called()

    def test_aucun_profil_existant_namorce_pas_la_question(self):
        with mock.patch("rudi_commune_starterkit.cli.charger_profils", return_value=[]), \
             mock.patch("rudi_commune_starterkit.cli.resoudre_commune", return_value=_GEVEZE_COMPLETE), \
             mock.patch("builtins.input", side_effect=["35120"]):
            with self.assertRaises(StopIteration):
                cli.executer_interactif()

    def test_plusieurs_profils_existants_signale_sans_proposer_de_reprise_automatique(self):
        autre_noeud = {**_PROFIL_GEVEZE, "url_noeud": "https://autre-noeud"}
        with mock.patch(
            "rudi_commune_starterkit.cli.charger_profils",
            return_value=[_PROFIL_GEVEZE, autre_noeud],
        ), \
             mock.patch("rudi_commune_starterkit.cli.resoudre_commune", return_value=_GEVEZE_COMPLETE), \
             mock.patch(
                 "rudi_commune_starterkit.cli._executer_depuis_profil",
             ) as m_reprise, \
             mock.patch("builtins.input", side_effect=["0", "35120"]):
            # Ambiguïté (2 nœuds) : pas de question oui/non posée, la saisie se
            # poursuit directement — s'arrête à l'URL du nœud, jamais saisie ici.
            with self.assertRaises(StopIteration):
                cli.executer_interactif()
        m_reprise.assert_not_called()


class TestExecuterRunAvecAttenteValidation(unittest.TestCase):
    """Backlog v5 : reprendre après validation de l'animateur sans tout relancer."""

    _KWARGS = {"commune": _GEVEZE, "conf": _CONF, "modes_par_jdd": {},
               "contact_email_commune": None, "forcer_maj": False,
               "only": None, "skip": None, "dry_run": False,
               "dossier_sortie": "/d", "chemin_etat": "/e"}

    def test_pas_dattente_ne_demande_rien(self):
        with mock.patch(
            "rudi_commune_starterkit.cli.executer_run", return_value=cli.EXIT_SUCCES,
        ) as m_run, mock.patch("builtins.input") as m_input:
            code = cli._executer_run_avec_attente_validation(**self._KWARGS)
        self.assertEqual(code, cli.EXIT_SUCCES)
        m_run.assert_called_once_with(**self._KWARGS)
        m_input.assert_not_called()

    def test_q_quitte_sans_relancer_executer_run(self):
        with mock.patch(
            "rudi_commune_starterkit.cli.executer_run",
            return_value=cli.EXIT_EN_ATTENTE_VALIDATION,
        ) as m_run, mock.patch("builtins.input", side_effect=["q"]):
            code = cli._executer_run_avec_attente_validation(**self._KWARGS)
        self.assertEqual(code, cli.EXIT_EN_ATTENTE_VALIDATION)
        m_run.assert_called_once_with(**self._KWARGS)

    def test_validation_detectee_reprend_automatiquement(self):
        with mock.patch(
            "rudi_commune_starterkit.cli.executer_run",
            side_effect=[cli.EXIT_EN_ATTENTE_VALIDATION, cli.EXIT_SUCCES],
        ) as m_run, mock.patch("builtins.input", side_effect=[""]):
            code = cli._executer_run_avec_attente_validation(**self._KWARGS)
        self.assertEqual(code, cli.EXIT_SUCCES)
        self.assertEqual(m_run.call_count, 2)
        # 1er appel : kwargs d'origine, sans le flag (pas encore de tentative connue).
        self.assertEqual(m_run.call_args_list[0].kwargs, self._KWARGS)

    def test_toujours_en_attente_redemande_jusquau_q(self):
        with mock.patch(
            "rudi_commune_starterkit.cli.executer_run",
            return_value=cli.EXIT_EN_ATTENTE_VALIDATION,
        ) as m_run, mock.patch("builtins.input", side_effect=["", "", "q"]):
            code = cli._executer_run_avec_attente_validation(**self._KWARGS)
        self.assertEqual(code, cli.EXIT_EN_ATTENTE_VALIDATION)
        self.assertEqual(m_run.call_count, 3)

    def test_appels_suivants_signalent_la_tentative_deja_faite(self):
        """Bug réel corrigé le 2026-11-17 (Grand-Fougeray, nœud preprod) : sans ce
        paramètre, chaque « [Entrée] pour vérifier » avant la validation animateur
        redemandait la création de l'organisation — doublon sur un nœud qui n'honore
        pas l'id déterministe proposé. Dès le 1er EXIT_EN_ATTENTE_VALIDATION, tous les
        appels suivants doivent porter ``organisation_creation_deja_tentee=True``."""
        with mock.patch(
            "rudi_commune_starterkit.cli.executer_run",
            return_value=cli.EXIT_EN_ATTENTE_VALIDATION,
        ) as m_run, mock.patch("builtins.input", side_effect=["", "", "q"]):
            cli._executer_run_avec_attente_validation(**self._KWARGS)
        self.assertEqual(m_run.call_args_list[0].kwargs.get("organisation_creation_deja_tentee"), None)
        for appel in m_run.call_args_list[1:]:
            self.assertTrue(appel.kwargs["organisation_creation_deja_tentee"])


class TestViderCommuneInteractif(unittest.TestCase):
    def test_affiche_les_jdd_tiers(self):
        rapport = {
            "message": "ok", "jdd_supprimes": [], "jdd_echecs": [],
            "jdd_tiers_supprimes": ["g-sans-local-id"], "jdd_tiers_echecs": ["g-autre"],
            "organisation": None,
        }
        with mock.patch("rudi_commune_starterkit.cli.lire_mot_de_passe_trousseau", return_value="pwd"), \
             mock.patch("rudi_commune_starterkit.cli.vider_commune", return_value=rapport), \
             mock.patch("builtins.input", side_effect=["n"]), \
             mock.patch("builtins.print") as m_print:
            cli._vider_commune_interactif(_PROFIL_GEVEZE, cli.CHEMIN_PROFILS_DEFAUT)
        sortie = "\n".join(str(a[0]) if a else "" for a, _ in m_print.call_args_list)
        self.assertIn("g-sans-local-id", sortie)
        self.assertIn("g-autre", sortie)

    def test_mot_de_passe_trousseau_et_conf_correcte(self):
        rapport = {"message": "ok", "jdd_supprimes": ["lid-1"], "jdd_echecs": [], "jdd_tiers_supprimes": [], "jdd_tiers_echecs": [], "organisation": None}
        with mock.patch("rudi_commune_starterkit.cli.lire_mot_de_passe_trousseau", return_value="pwd"), \
             mock.patch("rudi_commune_starterkit.cli.vider_commune", return_value=rapport) as m_vider, \
             mock.patch("builtins.input", side_effect=["n"]):
            code = cli._vider_commune_interactif(_PROFIL_GEVEZE, cli.CHEMIN_PROFILS_DEFAUT)
        self.assertEqual(code, cli.EXIT_SUCCES)
        m_vider.assert_called_once_with(
            {"url": "https://noeud", "usr": "u", "pwd": "pwd"}, "35120",
            nom_commune="Gévezé", supprimer_organisation=False,
        )

    def test_mot_de_passe_absent_du_trousseau_sans_tty_echoue(self):
        with mock.patch("rudi_commune_starterkit.cli.lire_mot_de_passe_trousseau", return_value=None), \
             mock.patch("rudi_commune_starterkit.cli.charger_conf_rudi", return_value=None), \
             mock.patch("rudi_commune_starterkit.cli.lire_mot_de_passe",
                         side_effect=cli.AbsenceTerminalError("pas de TTY")):
            code = cli._vider_commune_interactif(_PROFIL_GEVEZE, cli.CHEMIN_PROFILS_DEFAUT)
        self.assertEqual(code, cli.EXIT_ECHEC_TOTAL)

    def test_mot_de_passe_absent_du_trousseau_relu_depuis_le_repli_clair(self):
        """Bug réel corrigé le 2026-11-14 : le fichier de repli en clair (conf/
        rudi_node.json, écrit à l'étape 5 de l'assistant si le trousseau est
        indisponible) n'était jamais relu — resaisie forcée à chaque reprise."""
        with mock.patch("rudi_commune_starterkit.cli.lire_mot_de_passe_trousseau", return_value=None), \
             mock.patch("rudi_commune_starterkit.cli.charger_conf_rudi",
                         return_value={"url": "https://noeud", "usr": "u", "pwd": "pwd-en-clair"}), \
             mock.patch("rudi_commune_starterkit.cli.lire_mot_de_passe") as m_prompt, \
             mock.patch("rudi_commune_starterkit.cli.vider_commune",
                         return_value={"message": "ok", "jdd_supprimes": [], "jdd_echecs": [],
                                       "jdd_tiers_supprimes": [], "jdd_tiers_echecs": [],
                                       "organisation": None}) as m_vider, \
             mock.patch("builtins.input", side_effect=["n"]):
            code = cli._vider_commune_interactif(_PROFIL_GEVEZE, cli.CHEMIN_PROFILS_DEFAUT)
        self.assertEqual(code, cli.EXIT_SUCCES)
        m_prompt.assert_not_called()
        self.assertEqual(m_vider.call_args[0][0]["pwd"], "pwd-en-clair")

    def test_repli_clair_dun_autre_noeud_ignore(self):
        """Fichier global, pas par commune : ne doit jamais être réutilisé pour un
        (url_noeud, usr) différent de celui du profil demandé."""
        with mock.patch("rudi_commune_starterkit.cli.lire_mot_de_passe_trousseau", return_value=None), \
             mock.patch("rudi_commune_starterkit.cli.charger_conf_rudi",
                         return_value={"url": "https://autre-noeud", "usr": "autre", "pwd": "pas-pour-toi"}), \
             mock.patch("rudi_commune_starterkit.cli.lire_mot_de_passe",
                         side_effect=cli.AbsenceTerminalError("pas de TTY")):
            code = cli._vider_commune_interactif(_PROFIL_GEVEZE, cli.CHEMIN_PROFILS_DEFAUT)
        self.assertEqual(code, cli.EXIT_ECHEC_TOTAL)

    def test_organisation_supprimee_propose_de_loublier_et_accepte(self):
        rapport = {"message": "ok", "jdd_supprimes": [], "jdd_echecs": [], "jdd_tiers_supprimes": [], "jdd_tiers_echecs": [], "organisation": "supprimee"}
        with mock.patch("rudi_commune_starterkit.cli.lire_mot_de_passe_trousseau", return_value="pwd"), \
             mock.patch("rudi_commune_starterkit.cli.vider_commune", return_value=rapport), \
             mock.patch("rudi_commune_starterkit.cli.oublier_profil") as m_oublier, \
             mock.patch("builtins.input", side_effect=["o", "o"]):
            code = cli._vider_commune_interactif(_PROFIL_GEVEZE, cli.CHEMIN_PROFILS_DEFAUT)
        self.assertEqual(code, cli.EXIT_SUCCES)
        m_oublier.assert_called_once_with("35120", "https://noeud", cli.CHEMIN_PROFILS_DEFAUT)

    def test_jdd_en_echec_renvoie_echecs_partiels(self):
        rapport = {"message": "ok", "jdd_supprimes": [], "jdd_echecs": ["lid-1"], "jdd_tiers_supprimes": [], "jdd_tiers_echecs": [], "organisation": None}
        with mock.patch("rudi_commune_starterkit.cli.lire_mot_de_passe_trousseau", return_value="pwd"), \
             mock.patch("rudi_commune_starterkit.cli.vider_commune", return_value=rapport), \
             mock.patch("builtins.input", side_effect=["n"]):
            code = cli._vider_commune_interactif(_PROFIL_GEVEZE, cli.CHEMIN_PROFILS_DEFAUT)
        self.assertEqual(code, cli.EXIT_ECHECS_PARTIELS)


class TestViderCommuneInteractifAttenteDetachement(unittest.TestCase):
    """Backlog v5bis : même système d'attente que la création d'organisation
    (:class:`TestExecuterRunAvecAttenteValidation`), appliqué ici au détachement."""

    _RAPPORT_EN_ATTENTE = {
        "message": "Détachement demandé.", "jdd_supprimes": [], "jdd_echecs": [],
        "jdd_tiers_supprimes": [], "jdd_tiers_echecs": [], "organisation": "detachement_demande",
    }
    _RAPPORT_SUPPRIMEE = {
        "message": "Organisation supprimée.", "jdd_supprimes": [], "jdd_echecs": [],
        "jdd_tiers_supprimes": [], "jdd_tiers_echecs": [], "organisation": "supprimee",
    }

    def test_q_quitte_sans_relancer_vider_commune(self):
        with mock.patch("rudi_commune_starterkit.cli.lire_mot_de_passe_trousseau", return_value="pwd"), \
             mock.patch(
                 "rudi_commune_starterkit.cli.vider_commune", return_value=self._RAPPORT_EN_ATTENTE,
             ) as m_vider, \
             mock.patch("builtins.input", side_effect=["o", "q"]):
            code = cli._vider_commune_interactif(_PROFIL_GEVEZE, cli.CHEMIN_PROFILS_DEFAUT)
        self.assertEqual(code, cli.EXIT_EN_ATTENTE_VALIDATION)
        m_vider.assert_called_once()

    def test_validation_detectee_relance_automatiquement_vers_suppression_noeud(self):
        with mock.patch("rudi_commune_starterkit.cli.lire_mot_de_passe_trousseau", return_value="pwd"), \
             mock.patch(
                 "rudi_commune_starterkit.cli.vider_commune",
                 side_effect=[self._RAPPORT_EN_ATTENTE, self._RAPPORT_SUPPRIMEE],
             ) as m_vider, \
             mock.patch("builtins.input", side_effect=["o", "", "n"]):
            code = cli._vider_commune_interactif(_PROFIL_GEVEZE, cli.CHEMIN_PROFILS_DEFAUT)
        self.assertEqual(code, cli.EXIT_SUCCES)
        self.assertEqual(m_vider.call_count, 2)
        for appel in m_vider.call_args_list:
            self.assertEqual(appel.kwargs, {"nom_commune": "Gévezé", "supprimer_organisation": True})

    def test_toujours_en_attente_redemande_jusquau_q(self):
        with mock.patch("rudi_commune_starterkit.cli.lire_mot_de_passe_trousseau", return_value="pwd"), \
             mock.patch(
                 "rudi_commune_starterkit.cli.vider_commune", return_value=self._RAPPORT_EN_ATTENTE,
             ) as m_vider, \
             mock.patch("builtins.input", side_effect=["o", "", "", "q"]):
            code = cli._vider_commune_interactif(_PROFIL_GEVEZE, cli.CHEMIN_PROFILS_DEFAUT)
        self.assertEqual(code, cli.EXIT_EN_ATTENTE_VALIDATION)
        self.assertEqual(m_vider.call_count, 3)

    def test_boucle_aussi_sur_attente_validation_detachement(self):
        """La boucle d'attente (ajoutée pour ``detachement_demande``) doit continuer
        aussi sur ``attente_validation_detachement`` (détachement demandé mais pas
        encore validé, statut distinct introduit le 2026-11-14) — sans quoi elle
        sortirait immédiatement dès cette étape."""
        rapport_en_attente = {**self._RAPPORT_EN_ATTENTE, "organisation": "attente_validation_detachement"}
        with mock.patch("rudi_commune_starterkit.cli.lire_mot_de_passe_trousseau", return_value="pwd"), \
             mock.patch(
                 "rudi_commune_starterkit.cli.vider_commune",
                 side_effect=[rapport_en_attente, self._RAPPORT_SUPPRIMEE],
             ) as m_vider, \
             mock.patch("builtins.input", side_effect=["o", "", "n"]):
            code = cli._vider_commune_interactif(_PROFIL_GEVEZE, cli.CHEMIN_PROFILS_DEFAUT)
        self.assertEqual(code, cli.EXIT_SUCCES)
        self.assertEqual(m_vider.call_count, 2)


class TestExecuterInteractifNouvelleCommuneUrlPortail(unittest.TestCase):
    """L'URL du portail est désormais demandée dès la 1ère saisie (étape 3) — sans
    elle, --vider-commune reste indisponible pour une commune enregistrée depuis
    l'assistant plutôt que depuis le registre."""

    def _executer(self, saisies: list[str]):
        with mock.patch("rudi_commune_starterkit.cli.charger_profils", return_value=[]), \
             mock.patch("rudi_commune_starterkit.cli.resoudre_commune", return_value=_GEVEZE_COMPLETE), \
             mock.patch("rudi_commune_starterkit.cli.diagnostic_couverture_structurelle", return_value={}), \
             mock.patch("rudi_commune_starterkit.cli.valider_url_noeud", side_effect=lambda u, **k: u), \
             mock.patch("rudi_commune_starterkit.cli.lire_mot_de_passe", return_value="secret"), \
             mock.patch("rudi_commune_starterkit.cli.tester_connexion_noeud", return_value=True), \
             mock.patch("rudi_commune_starterkit.cli.enregistrer_profil") as m_profil, \
             mock.patch("rudi_commune_starterkit.cli.executer_run", return_value=0) as m_run, \
             mock.patch("builtins.input", side_effect=saisies):
            code = cli.executer_interactif()
        return code, m_profil, m_run

    def test_url_portail_saisie_propagee_a_conf_et_au_profil(self):
        saisies = ["35120", "https://noeud", "", "https://portail", "robot", "non", "", ""]
        code, m_profil, m_run = self._executer(saisies)
        self.assertEqual(code, 0)
        conf_recue = m_run.call_args.kwargs["conf"]
        self.assertEqual(conf_recue["url_portail"], "https://portail")
        profil_enregistre = m_profil.call_args[0][0]
        self.assertEqual(profil_enregistre["url_portail"], "https://portail")

    def test_url_portail_laissee_vide_absente_de_conf_et_du_profil(self):
        saisies = ["35120", "https://noeud", "", "", "robot", "non", "", ""]
        code, m_profil, m_run = self._executer(saisies)
        self.assertEqual(code, 0)

    def test_url_portail_http_non_locale_refusee_puis_laissee_vide(self):
        """Bug réel corrigé le 2026-11-14 : url_portail n'était jamais validée (seule
        url_noeud l'était) — un portail en http:// non local y envoyait les
        identifiants portail en clair sans le moindre avertissement."""
        with mock.patch("rudi_commune_starterkit.cli.charger_profils", return_value=[]), \
             mock.patch("rudi_commune_starterkit.cli.resoudre_commune", return_value=_GEVEZE_COMPLETE), \
             mock.patch("rudi_commune_starterkit.cli.diagnostic_couverture_structurelle", return_value={}), \
             mock.patch("rudi_commune_starterkit.cli.lire_mot_de_passe", return_value="secret"), \
             mock.patch("rudi_commune_starterkit.cli.tester_connexion_noeud", return_value=True), \
             mock.patch("rudi_commune_starterkit.cli.enregistrer_profil") as m_profil, \
             mock.patch("rudi_commune_starterkit.cli.executer_run", return_value=0) as m_run, \
             mock.patch("builtins.input", side_effect=[
                 "35120", "https://noeud", "",
                 "http://portail-externe.example", "non", "",
                 "robot", "non", "", "",
             ]):
            code = cli.executer_interactif()
        self.assertEqual(code, 0)
        conf_recue = m_run.call_args.kwargs["conf"]
        self.assertIsNone(conf_recue.get("url_portail"))
        conf_recue = m_run.call_args.kwargs["conf"]
        self.assertNotIn("url_portail", conf_recue)
        profil_enregistre = m_profil.call_args[0][0]
        self.assertIsNone(profil_enregistre["url_portail"])


class TestMain(unittest.TestCase):
    def test_sans_argument_appelle_interactif(self):
        with mock.patch("rudi_commune_starterkit.cli.executer_interactif", return_value=0) as m:
            self.assertEqual(cli.main([]), 0)
        m.assert_called_once()

    def test_avec_argument_appelle_scriptable(self):
        with mock.patch("rudi_commune_starterkit.cli.executer_scriptable", return_value=0) as m:
            self.assertEqual(cli.main(["--code-insee", "35120"]), 0)
        m.assert_called_once()

    def test_version_affiche_et_quitte_code_zero(self):
        with mock.patch("sys.stdout", new_callable=io.StringIO) as m_stdout:
            with self.assertRaises(SystemExit) as ctx:
                cli.main(["--version"])
        self.assertEqual(ctx.exception.code, 0)
        self.assertIn(cli.__version__, m_stdout.getvalue())

    def test_configure_la_sortie_console_du_toolkit(self):
        # rudi_harvest_toolkit a migré print() -> logging (2026-11-15, v0.5.9) : sans
        # cet appel, ses messages (avertissements, erreurs de publication...)
        # disparaîtraient silencieusement — voir rudi_harvest_toolkit.console pour
        # le comportement du helper lui-même (déjà testé côté toolkit).
        with mock.patch("rudi_commune_starterkit.cli.configurer_sortie_console") as m, \
             mock.patch("rudi_commune_starterkit.cli.executer_interactif", return_value=0):
            cli.main([])
        m.assert_called_once()


class TestDemanderUrlsNoeudWizard(unittest.TestCase):
    """Étape 3 du wizard : catalogue/portail déduits automatiquement du nœud (voir
    resolution_noeud.resoudre_urls_automatiquement) avant de les demander à l'agent
    municipal — ne redemander que si la détection échoue ou si l'agent la refuse."""

    def test_detection_confirmee_ne_pose_pas_les_questions_catalogue_portail(self):
        with mock.patch(
            "rudi_commune_starterkit.cli.resoudre_urls_automatiquement",
            return_value=("https://x/catalog", "https://portail.fr"),
        ), mock.patch(
            "builtins.input",
            side_effect=["https://x", "o", ""],  # url_noeud, confirmer détection, portail (défaut)
        ) as m_input:
            url_noeud, url_catalog, url_portail = cli._demander_urls_noeud_wizard()
        self.assertEqual((url_noeud, url_catalog, url_portail),
                          ("https://x", "https://x/catalog", "https://portail.fr"))
        self.assertEqual(m_input.call_count, 3)

    def test_detection_refusee_repasse_en_saisie_manuelle(self):
        with mock.patch(
            "rudi_commune_starterkit.cli.resoudre_urls_automatiquement",
            return_value=("https://x/catalog", "https://portail.fr"),
        ), mock.patch(
            "builtins.input",
            side_effect=["https://x", "n", "https://manuel/catalog", "https://portail-manuel.fr"],
        ):
            url_noeud, url_catalog, url_portail = cli._demander_urls_noeud_wizard()
        self.assertEqual(
            (url_noeud, url_catalog, url_portail),
            ("https://x", "https://manuel/catalog", "https://portail-manuel.fr"),
        )

    def test_detection_infructueuse_demande_tout_manuellement(self):
        with mock.patch(
            "rudi_commune_starterkit.cli.resoudre_urls_automatiquement",
            return_value=(None, None),
        ), mock.patch(
            "builtins.input",
            side_effect=["https://x", "https://manuel/catalog", "https://portail-manuel.fr"],
        ) as m_input:
            url_noeud, url_catalog, url_portail = cli._demander_urls_noeud_wizard()
        self.assertEqual(
            (url_noeud, url_catalog, url_portail),
            ("https://x", "https://manuel/catalog", "https://portail-manuel.fr"),
        )
        self.assertEqual(m_input.call_count, 3)

    def test_detection_catalogue_seul_ne_bloque_pas_question_portail(self):
        # Node sans portalConnected : catalogue détecté, portail non — l'agent doit
        # pouvoir quand même saisir un portail à la main si l'administrateur lui en
        # a transmis un.
        with mock.patch(
            "rudi_commune_starterkit.cli.resoudre_urls_automatiquement",
            return_value=("https://x/catalog", None),
        ), mock.patch(
            "builtins.input",
            side_effect=["https://x", "o", "https://portail-manuel.fr"],
        ):
            url_noeud, url_catalog, url_portail = cli._demander_urls_noeud_wizard()
        self.assertEqual(
            (url_noeud, url_catalog, url_portail),
            ("https://x", "https://x/catalog", "https://portail-manuel.fr"),
        )

    def test_detection_echoue_tls_propose_ignorer_certificat_puis_retente(self):
        # Bug réel corrigé le 2026-11-16 : un certificat TLS non reconnu (nœud de
        # test/preprod, cas courant) faisait échouer *silencieusement* la détection
        # automatique (exception avalée sans distinction), repassant en saisie
        # manuelle complète des deux URLs alors que /manager/conf les avait bien
        # renvoyées — reproduit en conditions réelles contre un serveur mock HTTPS à
        # certificat auto-signé. Corrigé en proposant la même confirmation
        # ``ACCEPTER`` que pour le test de connexion (:func:`cli.
        # _tester_connexion_avec_repli_tls`), puis en retentant avec
        # ``verify=False``, jamais par défaut.
        appels_verify = []

        def faux_resoudre(url_noeud, *, verify=True, erreur_sortie=None):
            appels_verify.append(verify)
            if verify:
                if erreur_sortie is not None:
                    erreur_sortie["exception"] = requests.exceptions.SSLError("certificat non reconnu")
                return None, None
            return "https://x/catalog", "https://portail.fr"

        with mock.patch(
            "rudi_commune_starterkit.cli.resoudre_urls_automatiquement", side_effect=faux_resoudre,
        ), mock.patch(
            "rudi_commune_starterkit.cli.confirmer", return_value=True,
        ) as m_confirmer, mock.patch(
            "rudi_commune_starterkit.cli.desactiver_verification_tls_noeud",
        ) as m_desactiver, mock.patch(
            "builtins.input",
            side_effect=["https://x", "o", ""],  # url_noeud, confirmer détection, portail (défaut)
        ):
            url_noeud, url_catalog, url_portail = cli._demander_urls_noeud_wizard()
        self.assertEqual(
            (url_noeud, url_catalog, url_portail),
            ("https://x", "https://x/catalog", "https://portail.fr"),
        )
        self.assertEqual(m_confirmer.call_args.kwargs.get("mot_attendu"), "ACCEPTER")
        m_desactiver.assert_called_once()
        self.assertEqual(appels_verify, [True, False])

    def test_detection_echoue_tls_refusee_repasse_en_saisie_manuelle(self):
        # Jamais de désactivation TLS sans confirmation explicite : un refus doit
        # revenir exactement au comportement précédent (saisie manuelle complète).
        def faux_resoudre(url_noeud, *, verify=True, erreur_sortie=None):
            if erreur_sortie is not None:
                erreur_sortie["exception"] = requests.exceptions.SSLError("certificat non reconnu")
            return None, None

        with mock.patch(
            "rudi_commune_starterkit.cli.resoudre_urls_automatiquement", side_effect=faux_resoudre,
        ), mock.patch(
            "rudi_commune_starterkit.cli.confirmer", return_value=False,
        ), mock.patch(
            "rudi_commune_starterkit.cli.desactiver_verification_tls_noeud",
        ) as m_desactiver, mock.patch(
            "builtins.input",
            side_effect=["https://x", "https://manuel/catalog", "https://portail-manuel.fr"],
        ):
            url_noeud, url_catalog, url_portail = cli._demander_urls_noeud_wizard()
        self.assertEqual(
            (url_noeud, url_catalog, url_portail),
            ("https://x", "https://manuel/catalog", "https://portail-manuel.fr"),
        )
        m_desactiver.assert_not_called()

    def test_detection_echoue_non_tls_ne_propose_pas_ignorer_certificat(self):
        # Un échec non lié au certificat (nœud injoignable, timeout...) doit garder
        # le repli silencieux d'origine — jamais de prompt ACCEPTER hors de propos.
        def faux_resoudre(url_noeud, *, verify=True, erreur_sortie=None):
            if erreur_sortie is not None:
                erreur_sortie["exception"] = requests.exceptions.ConnectionError("injoignable")
            return None, None

        with mock.patch(
            "rudi_commune_starterkit.cli.resoudre_urls_automatiquement", side_effect=faux_resoudre,
        ), mock.patch(
            "rudi_commune_starterkit.cli.confirmer",
        ) as m_confirmer, mock.patch(
            "builtins.input",
            side_effect=["https://x", "https://manuel/catalog", "https://portail-manuel.fr"],
        ):
            cli._demander_urls_noeud_wizard()
        m_confirmer.assert_not_called()


if __name__ == "__main__":
    unittest.main()
