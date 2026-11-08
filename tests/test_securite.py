"""Tests de securite.py — URL/email, getpass+TTY, permissions fichier, trousseau."""
import contextlib
import io
import os
import stat
import tempfile
import unittest
from unittest import mock

from rudi_commune_starterkit import securite


class TestValiderUrlNoeud(unittest.TestCase):
    def test_https_accepte(self):
        self.assertEqual(securite.valider_url_noeud("https://exemple.fr/"), "https://exemple.fr")

    def test_http_refuse_par_defaut(self):
        with self.assertRaises(securite.UrlNoeudNonSecurisee):
            securite.valider_url_noeud("http://exemple.fr")

    def test_http_localhost_accepte_si_autorise(self):
        self.assertEqual(
            securite.valider_url_noeud("http://localhost:3000", autoriser_http_local=True),
            "http://localhost:3000",
        )
        securite.valider_url_noeud("http://127.0.0.1:3000", autoriser_http_local=True)

    def test_http_localhost_refuse_sans_autorisation(self):
        with self.assertRaises(securite.UrlNoeudNonSecurisee):
            securite.valider_url_noeud("http://localhost:3000")

    def test_http_ip_non_locale_refuse_meme_autorise(self):
        with self.assertRaises(securite.UrlNoeudNonSecurisee):
            securite.valider_url_noeud("http://192.168.1.5", autoriser_http_local=True)


class TestEmailValide(unittest.TestCase):
    def test_cas_positifs(self):
        for adresse in ("a@b.fr", "contact.mairie@geveze.fr"):
            self.assertTrue(securite.email_valide(adresse))

    def test_cas_negatifs(self):
        for adresse in ("", "pas-un-email", "a@b", "@b.fr", "a@.fr"):
            self.assertFalse(securite.email_valide(adresse))


class TestEmailSuspect(unittest.TestCase):
    def test_tld_reserves_detectes(self):
        for adresse in (
            "contact@geveze.local", "a@x.test", "a@x.example", "a@x.invalid",
        ):
            self.assertIsNotNone(securite.email_suspect(adresse))

    def test_tld_insensible_a_la_casse(self):
        self.assertIsNotNone(securite.email_suspect("contact@geveze.LOCAL"))

    def test_domaine_normal_non_suspect(self):
        for adresse in ("mairie@geveze.fr", "contact@megalis.bretagne.bzh", "a@b.com"):
            self.assertIsNone(securite.email_suspect(adresse))

    def test_adresse_mal_formee_non_suspecte(self):
        # Rôle d'email_valide(), pas de celle-ci — ne lève jamais, retourne None.
        for adresse in ("", "pas-un-email", "@b.fr"):
            self.assertIsNone(securite.email_suspect(adresse))

    def test_jamais_bloquant_cest_un_avertissement_textuel(self):
        avertissement = securite.email_suspect("contact@geveze.local")
        self.assertIsInstance(avertissement, str)
        self.assertIn("local", avertissement)


class TestLireMotDePasse(unittest.TestCase):
    def test_sans_tty_leve(self):
        with mock.patch("sys.stdin.isatty", return_value=False):
            with self.assertRaises(securite.AbsenceTerminalError):
                securite.lire_mot_de_passe()

    def test_avec_tty_appelle_getpass(self):
        with mock.patch("sys.stdin.isatty", return_value=True), \
             mock.patch("getpass.getpass", return_value="secret") as m:
            self.assertEqual(securite.lire_mot_de_passe("invite"), "secret")
            m.assert_called_once_with("invite")


class TestEcrireConfFichier(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.chemin = os.path.join(self._tmp.name, "sous_dossier", "rudi_node.json")

    def test_ecrit_et_permissions_0600(self):
        securite.ecrire_conf_fichier(self.chemin, {"url": "https://x", "usr": "u", "pwd": "p"})
        mode = stat.S_IMODE(os.stat(self.chemin).st_mode)
        self.assertEqual(mode, 0o600)
        import json
        with open(self.chemin, encoding="utf-8") as f:
            self.assertEqual(json.load(f)["usr"], "u")

    def test_corrige_permissions_trop_larges_preexistantes(self):
        os.makedirs(os.path.dirname(self.chemin), exist_ok=True)
        with open(self.chemin, "w", encoding="utf-8") as f:
            f.write("{}")
        os.chmod(self.chemin, 0o644)
        securite.ecrire_conf_fichier(self.chemin, {"url": "https://x"})
        self.assertEqual(stat.S_IMODE(os.stat(self.chemin).st_mode), 0o600)


class TestVerifierPermissionsConf(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.chemin = os.path.join(self._tmp.name, "rudi_node.json")

    def test_avertit_si_permissions_trop_larges(self):
        with open(self.chemin, "w", encoding="utf-8") as f:
            f.write("{}")
        os.chmod(self.chemin, 0o644)
        tampon = io.StringIO()
        with contextlib.redirect_stdout(tampon):
            securite.verifier_permissions_conf(self.chemin)
        self.assertIn("0600", tampon.getvalue())

    def test_silencieux_si_permissions_correctes(self):
        with open(self.chemin, "w", encoding="utf-8") as f:
            f.write("{}")
        os.chmod(self.chemin, 0o600)
        tampon = io.StringIO()
        with contextlib.redirect_stdout(tampon):
            securite.verifier_permissions_conf(self.chemin)
        self.assertEqual(tampon.getvalue(), "")

    def test_rien_si_fichier_absent(self):
        tampon = io.StringIO()
        with contextlib.redirect_stdout(tampon):
            securite.verifier_permissions_conf(os.path.join(self._tmp.name, "absent.json"))
        self.assertEqual(tampon.getvalue(), "")


class _BackendEnClairFactice:
    __module__ = "keyrings.alt.file"
    __qualname__ = "PlaintextKeyring"


class _AutreBackendFactice:
    pass


class TestBackendTrousseauEstSain(unittest.TestCase):
    def test_backend_en_clair_detecte(self):
        with mock.patch("keyring.get_keyring", return_value=_BackendEnClairFactice()):
            sain, nom = securite.backend_trousseau_est_sain()
        self.assertFalse(sain)
        self.assertEqual(nom, "keyrings.alt.file.PlaintextKeyring")

    def test_autre_backend_sain(self):
        with mock.patch("keyring.get_keyring", return_value=_AutreBackendFactice()):
            sain, _nom = securite.backend_trousseau_est_sain()
        self.assertTrue(sain)


class TestTrousseau(unittest.TestCase):
    def test_enregistrer_delegue_si_backend_sain(self):
        with mock.patch.object(securite, "backend_trousseau_est_sain", return_value=(True, "x")), \
             mock.patch("keyring.set_password") as m:
            securite.enregistrer_mot_de_passe_trousseau("https://noeud", "alice", "secret")
        m.assert_called_once_with("rudi-commune-starterkit:https://noeud:alice", "alice", "secret")

    def test_enregistrer_refuse_si_backend_en_clair(self):
        with mock.patch.object(securite, "backend_trousseau_est_sain", return_value=(False, "x")), \
             mock.patch("keyring.set_password") as m:
            with self.assertRaises(securite.TrousseauEnClairError):
                securite.enregistrer_mot_de_passe_trousseau("https://noeud", "alice", "secret")
        m.assert_not_called()

    def test_lire_delegue_si_backend_sain(self):
        with mock.patch.object(securite, "backend_trousseau_est_sain", return_value=(True, "x")), \
             mock.patch("keyring.get_password", return_value="secret") as m:
            resultat = securite.lire_mot_de_passe_trousseau("https://noeud", "alice")
        self.assertEqual(resultat, "secret")
        m.assert_called_once_with("rudi-commune-starterkit:https://noeud:alice", "alice")

    def test_lire_refuse_si_backend_en_clair(self):
        with mock.patch.object(securite, "backend_trousseau_est_sain", return_value=(False, "x")), \
             mock.patch("keyring.get_password") as m:
            with self.assertRaises(securite.TrousseauEnClairError):
                securite.lire_mot_de_passe_trousseau("https://noeud", "alice")
        m.assert_not_called()

    def test_cle_trousseau_unique_par_noeud_et_utilisateur(self):
        cle_a = securite._cle_trousseau("https://noeud-a", "alice")
        cle_b = securite._cle_trousseau("https://noeud-b", "alice")
        self.assertNotEqual(cle_a, cle_b)


if __name__ == "__main__":
    unittest.main()
