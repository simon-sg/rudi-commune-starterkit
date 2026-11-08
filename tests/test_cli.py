"""Tests de cli.py — cœur partagé (executer_run), résolution de modes, mode scriptable.

`only={...}` restreint systématiquement executer_run() à un seul module réel
(`population`), patché, pour ne jamais risquer un appel réseau vers les 12 autres
connecteurs réels référencés par registre.MODULES.
"""
import argparse
import tempfile
import unittest
from unittest import mock

from rudi_commune_starterkit import cli, organisations
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

    def _executer(self, **override):
        kwargs = dict(
            commune=_GEVEZE, conf=_CONF, modes_par_jdd=self.modes,
            contact_email_commune=None, forcer_maj=False,
            only={organisations.POPULATION}, skip=None, dry_run=False,
            dossier_sortie=self.dossier_sortie, chemin_etat=self.chemin_etat,
        )
        kwargs.update(override)
        return cli.executer_run(**kwargs)

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


class TestResoudreConfScriptable(unittest.TestCase):
    def test_rudi_conf_fichier(self):
        args = argparse.Namespace(rudi_conf="conf.json", url_noeud=None, usr=None,
                                   utiliser_trousseau=False)
        with mock.patch("rudi_commune_starterkit.cli.verifier_permissions_conf"), \
             mock.patch("rudi_commune_starterkit.cli.charger_conf_rudi",
                         return_value={"url": "https://x", "usr": "u", "pwd": "p"}):
            conf = cli._resoudre_conf_scriptable(args)
        self.assertEqual(conf["usr"], "u")

    def test_sans_rudi_conf_ni_url_leve(self):
        args = argparse.Namespace(rudi_conf=None, url_noeud=None, usr=None,
                                   utiliser_trousseau=False)
        with self.assertRaises(ValueError):
            cli._resoudre_conf_scriptable(args)

    def test_sans_trousseau_ni_conf_leve(self):
        args = argparse.Namespace(rudi_conf=None, url_noeud="https://x", usr="u",
                                   utiliser_trousseau=False)
        with self.assertRaises(ValueError):
            cli._resoudre_conf_scriptable(args)

    def test_trousseau_sans_mot_de_passe_enregistre_leve(self):
        args = argparse.Namespace(rudi_conf=None, url_noeud="https://x", usr="u",
                                   utiliser_trousseau=True)
        with mock.patch("rudi_commune_starterkit.cli.lire_mot_de_passe_trousseau", return_value=None):
            with self.assertRaises(ValueError):
                cli._resoudre_conf_scriptable(args)

    def test_trousseau_ok(self):
        args = argparse.Namespace(rudi_conf=None, url_noeud="https://x", usr="u",
                                   utiliser_trousseau=True)
        with mock.patch("rudi_commune_starterkit.cli.lire_mot_de_passe_trousseau", return_value="secret"):
            conf = cli._resoudre_conf_scriptable(args)
        self.assertEqual(conf["pwd"], "secret")


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


class TestExecuterScriptableViderCommune(unittest.TestCase):
    def test_supprimer_organisation_sans_vider_commune_echec(self):
        args = cli._construire_parser().parse_args([
            "--code-insee", "35120", "--supprimer-organisation",
        ])
        self.assertEqual(cli.executer_scriptable(args), cli.EXIT_ECHEC_TOTAL)

    def test_delegue_a_vider_commune_et_fusionne_url_portail(self):
        args = cli._construire_parser().parse_args([
            "--code-insee", "35120", "--rudi-conf", "conf.json", "--vider-commune",
            "--url-portail", "https://portail", "--confirmer", "SUPPRIMER",
        ])
        rapport = {"jdd_supprimes": ["lid-1"], "jdd_echecs": [], "organisation": None,
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
        rapport = {"jdd_supprimes": [], "jdd_echecs": ["lid-1"], "organisation": None,
                   "message": "échec"}
        with mock.patch("rudi_commune_starterkit.cli._resoudre_conf_scriptable", return_value=dict(_CONF)), \
             mock.patch("rudi_commune_starterkit.cli.vider_commune", return_value=rapport):
            code = cli.executer_scriptable(args)
        self.assertEqual(code, cli.EXIT_ECHECS_PARTIELS)

    def test_organisation_en_attente_de_detachement_rapporte_echecs_partiels(self):
        args = cli._construire_parser().parse_args([
            "--code-insee", "35120", "--rudi-conf", "conf.json", "--vider-commune",
            "--supprimer-organisation", "--url-portail", "https://portail",
            "--confirmer", "SUPPRIMER",
        ])
        rapport = {"jdd_supprimes": ["lid-1"], "jdd_echecs": [],
                   "organisation": "detachement_demande", "message": "en attente"}
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
        rapport = {"jdd_supprimes": ["lid-1"], "jdd_echecs": [],
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
            m_vider.return_value = {"jdd_supprimes": [], "jdd_echecs": [], "organisation": None, "message": None}
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
        m_pwd.assert_called_once_with(_PROFIL_GEVEZE["url_noeud"], _PROFIL_GEVEZE["usr"])
        self.assertEqual(
            m_run.call_args.kwargs["modes_par_jdd"][organisations.POPULATION],
            _PROFIL_GEVEZE["mode_producteur"],
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
             mock.patch("builtins.input", side_effect=["1"]):
            code = cli.executer_interactif()
        self.assertEqual(code, 0)
        m_reprise.assert_called_once_with(_PROFIL_GEVEZE, cli.CHEMIN_PROFILS_DEFAUT)

    def test_profils_json_corrompu_arrete_proprement(self):
        with mock.patch(
            "rudi_commune_starterkit.cli.charger_profils", side_effect=ValueError("corrompu"),
        ):
            self.assertEqual(cli.executer_interactif(), cli.EXIT_ECHEC_TOTAL)


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


if __name__ == "__main__":
    unittest.main()
