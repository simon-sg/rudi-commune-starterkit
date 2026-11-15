"""Tests de securite.py — URL/email, getpass+TTY, permissions fichier, trousseau."""
import contextlib
import getpass
import io
import os
import stat
import sys
import tempfile
import unittest
import warnings
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

    def test_http_sous_domaine_localhost_accepte_si_autorise(self):
        """RFC 6761 : tout nom sous .localhost doit résoudre en loopback (ex. routage
        par sous-domaine d'un portail de dev, ``rudi.localhost``) — pas seulement le
        nom nu ``localhost``."""
        self.assertEqual(
            securite.valider_url_noeud("http://rudi.localhost", autoriser_http_local=True),
            "http://rudi.localhost",
        )

    def test_http_sous_domaine_localhost_refuse_sans_autorisation(self):
        with self.assertRaises(securite.UrlNoeudNonSecurisee):
            securite.valider_url_noeud("http://rudi.localhost")

    def test_http_faux_sous_domaine_localhost_refuse(self):
        """``notlocalhost`` ne doit pas matcher par un simple ``endswith`` naïf sur
        ``localhost`` sans le point séparateur."""
        with self.assertRaises(securite.UrlNoeudNonSecurisee):
            securite.valider_url_noeud("http://evil-notlocalhost", autoriser_http_local=True)

    def test_hote_vide_refuse(self):
        """Bug réel corrigé le 2026-11-14 : https:// seul passait la validation et
        échouait plus tard de façon opaque."""
        with self.assertRaises(securite.UrlNoeudNonSecurisee):
            securite.valider_url_noeud("https://")
        with self.assertRaises(securite.UrlNoeudNonSecurisee):
            securite.valider_url_noeud("http://", autoriser_http_local=True)

    def test_userinfo_dans_url_refuse(self):
        """Des identifiants dans l'URL (userinfo) se retrouveraient conservés puis
        affichés tels quels dans les messages d'erreur du reste du programme."""
        with self.assertRaises(securite.UrlNoeudNonSecurisee):
            securite.valider_url_noeud("https://usr:pwd@exemple.fr")
        with self.assertRaises(securite.UrlNoeudNonSecurisee):
            securite.valider_url_noeud("http://usr:pwd@localhost", autoriser_http_local=True)


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

    def test_tty_incapable_de_masquer_leve_plutot_que_decho(self):
        # TTY présent (isatty() True) mais getpass incapable de désactiver l'écho
        # (ex. termios ENOTTY, rencontré avec le binaire PyInstaller Linux) : ne
        # doit jamais dégrader silencieusement vers une saisie affichée en clair.
        def getpass_qui_echoue(invite):
            warnings.warn("Can not control echo on the terminal.", getpass.GetPassWarning)
            return "mot_de_passe_echo"  # jamais atteint si l'avertissement est bien élevé en erreur

        with mock.patch("sys.stdin.isatty", return_value=True), \
             mock.patch("getpass.getpass", side_effect=getpass_qui_echoue):
            with self.assertRaises(securite.AbsenceTerminalError):
                securite.lire_mot_de_passe()


class TestEcrireConfFichier(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.chemin = os.path.join(self._tmp.name, "sous_dossier", "rudi_node.json")

    @unittest.skipIf(sys.platform == "win32", "permissions POSIX — sans objet sous Windows, voir TestEcrireConfFichierWindows")
    def test_ecrit_et_permissions_0600(self):
        securite.ecrire_conf_fichier(self.chemin, {"url": "https://x", "usr": "u", "pwd": "p"})
        mode = stat.S_IMODE(os.stat(self.chemin).st_mode)
        self.assertEqual(mode, 0o600)
        import json
        with open(self.chemin, encoding="utf-8") as f:
            self.assertEqual(json.load(f)["usr"], "u")

    @unittest.skipIf(sys.platform == "win32", "permissions POSIX — sans objet sous Windows, voir TestEcrireConfFichierWindows")
    def test_corrige_permissions_trop_larges_preexistantes(self):
        os.makedirs(os.path.dirname(self.chemin), exist_ok=True)
        with open(self.chemin, "w", encoding="utf-8") as f:
            f.write("{}")
        os.chmod(self.chemin, 0o644)
        securite.ecrire_conf_fichier(self.chemin, {"url": "https://x"})
        self.assertEqual(stat.S_IMODE(os.stat(self.chemin).st_mode), 0o600)


class TestEcrireConfFichierWindows(unittest.TestCase):
    """Chemin Windows de ecrire_conf_fichier() (icacls au lieu de chmod — NTFS n'a pas
    de permissions POSIX). Patché via sys.platform/subprocess.run pour être exécutable
    sur toute plateforme de développement, pas seulement sur un vrai Windows."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.chemin = os.path.join(self._tmp.name, "sous_dossier", "rudi_node.json")

    def test_ecrit_et_appelle_icacls(self):
        with mock.patch("sys.platform", "win32"), \
             mock.patch.dict(os.environ, {"USERNAME": "agent_municipal"}), \
             mock.patch("rudi_commune_starterkit.securite.subprocess.run") as m_run:
            m_run.return_value = mock.Mock(returncode=0, stderr="")
            securite.ecrire_conf_fichier(self.chemin, {"url": "https://x", "usr": "u"})

        m_run.assert_called_once()
        args = m_run.call_args.args[0]
        self.assertEqual(args[0], "icacls")
        self.assertIn(self.chemin, args)
        self.assertIn("agent_municipal:F", args)
        import json
        with open(self.chemin, encoding="utf-8") as f:
            self.assertEqual(json.load(f)["usr"], "u")

    def test_avertit_si_icacls_echoue(self):
        with mock.patch("sys.platform", "win32"), \
             mock.patch.dict(os.environ, {"USERNAME": "agent_municipal"}), \
             mock.patch("rudi_commune_starterkit.securite.subprocess.run") as m_run:
            m_run.return_value = mock.Mock(returncode=1, stderr="erreur icacls")
            tampon = io.StringIO()
            with contextlib.redirect_stdout(tampon):
                securite.ecrire_conf_fichier(self.chemin, {"url": "https://x"})
        self.assertIn("icacls", tampon.getvalue())

    def test_avertit_si_username_absent(self):
        with mock.patch("sys.platform", "win32"), \
             mock.patch.dict(os.environ, {"USERNAME": ""}), \
             mock.patch("rudi_commune_starterkit.securite.subprocess.run") as m_run:
            tampon = io.StringIO()
            with contextlib.redirect_stdout(tampon):
                securite.ecrire_conf_fichier(self.chemin, {"url": "https://x"})
        m_run.assert_not_called()
        self.assertIn("USERNAME", tampon.getvalue())

    def test_avertit_si_icacls_introuvable(self):
        """subprocess.run peut lever (icacls absent du PATH, poste verrouillé) —
        _restreindre_acces_windows() ne doit jamais laisser remonter l'exception."""
        with mock.patch("sys.platform", "win32"), \
             mock.patch.dict(os.environ, {"USERNAME": "agent_municipal"}), \
             mock.patch("rudi_commune_starterkit.securite.subprocess.run", side_effect=FileNotFoundError("icacls")):
            tampon = io.StringIO()
            with contextlib.redirect_stdout(tampon):
                securite.ecrire_conf_fichier(self.chemin, {"url": "https://x"})
        self.assertIn("icacls", tampon.getvalue())
        import json
        with open(self.chemin, encoding="utf-8") as f:
            self.assertEqual(json.load(f)["url"], "https://x")

    def test_restreint_avant_decrire_le_contenu_sensible(self):
        """Le contenu JSON (identifiants en clair) ne doit jamais être présent sur
        disque tant que la restriction icacls n'a pas été tentée — sinon on
        réintroduit la fenêtre POSIX que ce module évite explicitement par ailleurs."""
        contenu_au_moment_de_icacls = {}

        def _capturer(*args, **kwargs):
            with open(self.chemin, encoding="utf-8") as f:
                contenu_au_moment_de_icacls["brut"] = f.read()
            return mock.Mock(returncode=0, stderr="")

        with mock.patch("sys.platform", "win32"), \
             mock.patch.dict(os.environ, {"USERNAME": "agent_municipal"}), \
             mock.patch("rudi_commune_starterkit.securite.subprocess.run", side_effect=_capturer):
            securite.ecrire_conf_fichier(self.chemin, {"url": "https://x", "pwd": "secret"})

        self.assertEqual(contenu_au_moment_de_icacls["brut"], "")


class TestVerifierPermissionsConf(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.chemin = os.path.join(self._tmp.name, "rudi_node.json")

    @unittest.skipIf(sys.platform == "win32", "permissions POSIX — verifier_permissions_conf() est un no-op sous Windows")
    def test_avertit_si_permissions_trop_larges(self):
        with open(self.chemin, "w", encoding="utf-8") as f:
            f.write("{}")
        os.chmod(self.chemin, 0o644)
        tampon = io.StringIO()
        with contextlib.redirect_stdout(tampon):
            securite.verifier_permissions_conf(self.chemin)
        self.assertIn("0600", tampon.getvalue())

    @unittest.skipIf(sys.platform == "win32", "permissions POSIX — verifier_permissions_conf() est un no-op sous Windows")
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

    @unittest.skipIf(sys.platform == "win32", "chemin POSIX — os.stat() n'est appelé que hors Windows")
    def test_fail_open_avec_avertissement_si_stat_echoue(self):
        """Décision Simon (revue de code 2026-11-14) : fail-open explicite — une
        course entre os.path.exists() et os.stat() (ou tout autre OSError à la
        vérification) ne doit jamais faire planter l'appelant, mais ne doit jamais
        non plus rester silencieuse."""
        with open(self.chemin, "w", encoding="utf-8") as f:
            f.write("{}")
        # os.path.exists() avale elle-même un OSError de os.stat() (renvoie False) —
        # il faut donc laisser son appel interne réussir normalement et ne faire
        # échouer que le second appel, celui fait par verifier_permissions_conf(),
        # pour simuler une vraie course entre les deux.
        stat_reel = os.stat(self.chemin)
        with mock.patch(
            "rudi_commune_starterkit.securite.os.stat",
            side_effect=[stat_reel, OSError("boom")],
        ):
            tampon = io.StringIO()
            with contextlib.redirect_stdout(tampon):
                securite.verifier_permissions_conf(self.chemin)  # ne lève pas
        self.assertIn("impossible de vérifier", tampon.getvalue())

    def test_windows_avertit_si_acl_trop_large(self):
        with open(self.chemin, "w", encoding="utf-8") as f:
            f.write("{}")
        sortie_icacls = f"{self.chemin} BUILTIN\\Users:(R)\n"
        with mock.patch("sys.platform", "win32"), \
             mock.patch("rudi_commune_starterkit.securite.subprocess.run") as m_run:
            m_run.return_value = mock.Mock(returncode=0, stdout=sortie_icacls)
            tampon = io.StringIO()
            with contextlib.redirect_stdout(tampon):
                securite.verifier_permissions_conf(self.chemin)
        self.assertIn("NTFS", tampon.getvalue())

    def test_windows_silencieux_si_acl_restreinte(self):
        with open(self.chemin, "w", encoding="utf-8") as f:
            f.write("{}")
        sortie_icacls = f"{self.chemin} agent_municipal:(F)\n"
        with mock.patch("sys.platform", "win32"), \
             mock.patch("rudi_commune_starterkit.securite.subprocess.run") as m_run:
            m_run.return_value = mock.Mock(returncode=0, stdout=sortie_icacls)
            tampon = io.StringIO()
            with contextlib.redirect_stdout(tampon):
                securite.verifier_permissions_conf(self.chemin)
        self.assertEqual(tampon.getvalue(), "")

    def test_windows_silencieux_si_icacls_indisponible(self):
        with open(self.chemin, "w", encoding="utf-8") as f:
            f.write("{}")
        with mock.patch("sys.platform", "win32"), \
             mock.patch("rudi_commune_starterkit.securite.subprocess.run", side_effect=FileNotFoundError("icacls")):
            tampon = io.StringIO()
            with contextlib.redirect_stdout(tampon):
                securite.verifier_permissions_conf(self.chemin)
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

    def test_backend_non_reconnu_refuse_par_defaut(self):
        """Bug réel corrigé le 2026-11-14 : c'était une liste NOIRE (seul un backend
        explicitement connu pour stocker en clair était refusé, tout le reste — y
        compris un backend jamais vu — passait par défaut). Inversé en liste blanche :
        un backend non reconnu est désormais refusé par défaut (contournable
        explicitement, voir TestTrousseau)."""
        with mock.patch("keyring.get_keyring", return_value=_AutreBackendFactice()):
            sain, _nom = securite.backend_trousseau_est_sain()
        self.assertFalse(sain)

    def test_backend_liste_blanche_sain(self):
        class _BackendSurFactice:
            __module__ = "keyring.backends.SecretService"
            __qualname__ = "Keyring"
        with mock.patch("keyring.get_keyring", return_value=_BackendSurFactice()):
            sain, nom = securite.backend_trousseau_est_sain()
        self.assertTrue(sain)
        self.assertEqual(nom, "keyring.backends.SecretService.Keyring")


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

    def test_enregistrer_backend_non_reconnu_leve_le_sous_type_precis(self):
        with mock.patch.object(securite, "backend_trousseau_est_sain", return_value=(False, "x")), \
             mock.patch("keyring.set_password") as m:
            with self.assertRaises(securite.TrousseauBackendNonReconnuError):
                securite.enregistrer_mot_de_passe_trousseau("https://noeud", "alice", "secret")
        m.assert_not_called()

    def test_enregistrer_backend_en_clair_connu_refuse_meme_avec_contournement(self):
        """Le contournement ne vaut que pour un backend non reconnu — jamais pour un
        backend explicitement connu pour stocker en clair."""
        with mock.patch.object(
            securite, "backend_trousseau_est_sain",
            return_value=(False, "keyrings.alt.file.PlaintextKeyring"),
        ), mock.patch("keyring.set_password") as m:
            with self.assertRaises(securite.TrousseauEnClairError):
                securite.enregistrer_mot_de_passe_trousseau(
                    "https://noeud", "alice", "secret", autoriser_backend_non_reconnu=True,
                )
        m.assert_not_called()

    def test_enregistrer_backend_non_reconnu_delegue_avec_contournement(self):
        with mock.patch.object(securite, "backend_trousseau_est_sain", return_value=(False, "x")), \
             mock.patch("keyring.set_password") as m:
            securite.enregistrer_mot_de_passe_trousseau(
                "https://noeud", "alice", "secret", autoriser_backend_non_reconnu=True,
            )
        m.assert_called_once_with("rudi-commune-starterkit:https://noeud:alice", "alice", "secret")

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

    def test_lire_backend_non_reconnu_leve_le_sous_type_precis(self):
        with mock.patch.object(securite, "backend_trousseau_est_sain", return_value=(False, "x")), \
             mock.patch("keyring.get_password") as m:
            with self.assertRaises(securite.TrousseauBackendNonReconnuError):
                securite.lire_mot_de_passe_trousseau("https://noeud", "alice")
        m.assert_not_called()

    def test_lire_backend_en_clair_connu_refuse_meme_avec_contournement(self):
        with mock.patch.object(
            securite, "backend_trousseau_est_sain",
            return_value=(False, "keyrings.alt.file.PlaintextKeyring"),
        ), mock.patch("keyring.get_password") as m:
            with self.assertRaises(securite.TrousseauEnClairError):
                securite.lire_mot_de_passe_trousseau(
                    "https://noeud", "alice", autoriser_backend_non_reconnu=True,
                )
        m.assert_not_called()

    def test_lire_backend_non_reconnu_delegue_avec_contournement(self):
        with mock.patch.object(securite, "backend_trousseau_est_sain", return_value=(False, "x")), \
             mock.patch("keyring.get_password", return_value="secret") as m:
            resultat = securite.lire_mot_de_passe_trousseau(
                "https://noeud", "alice", autoriser_backend_non_reconnu=True,
            )
        self.assertEqual(resultat, "secret")
        m.assert_called_once_with("rudi-commune-starterkit:https://noeud:alice", "alice")

    def test_lire_sans_backend_fonctionnel_leve_indisponible_pas_crash(self):
        """Bug réel corrigé le 2026-11-14 : keyring.errors.NoKeyringError (aucun
        backend fonctionnel, ex. Linux minimal) n'est levée qu'À L'USAGE
        (keyring.backends.fail.Keyring.get_password), jamais détectée par
        backend_trousseau_est_sain() — sans ce traitement, elle remontait non
        attrapée jusqu'au CLI."""
        import keyring.errors
        with mock.patch.object(securite, "backend_trousseau_est_sain", return_value=(True, "x")), \
             mock.patch("keyring.get_password", side_effect=keyring.errors.NoKeyringError("non")):
            with self.assertRaises(securite.TrousseauIndisponibleError):
                securite.lire_mot_de_passe_trousseau("https://noeud", "alice")

    def test_enregistrer_sans_backend_fonctionnel_leve_indisponible_pas_crash(self):
        import keyring.errors
        with mock.patch.object(securite, "backend_trousseau_est_sain", return_value=(True, "x")), \
             mock.patch("keyring.set_password", side_effect=keyring.errors.NoKeyringError("non")):
            with self.assertRaises(securite.TrousseauIndisponibleError):
                securite.enregistrer_mot_de_passe_trousseau("https://noeud", "alice", "secret")

    def test_cle_trousseau_unique_par_noeud_et_utilisateur(self):
        cle_a = securite._cle_trousseau("https://noeud-a", "alice")
        cle_b = securite._cle_trousseau("https://noeud-b", "alice")
        self.assertNotEqual(cle_a, cle_b)


if __name__ == "__main__":
    unittest.main()
