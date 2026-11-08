"""Tests de interaction.py — confirmation destructrice, interactif et scriptable."""
import unittest
from unittest import mock

from rudi_commune_starterkit.interaction import confirmer


class TestConfirmerInteractif(unittest.TestCase):
    def test_mot_correct_confirme(self):
        with mock.patch("sys.stdin.isatty", return_value=True), \
             mock.patch("builtins.input", return_value="SUPPRIMER"):
            self.assertTrue(confirmer("Attention", mot_attendu="SUPPRIMER"))

    def test_mot_incorrect_refuse(self):
        with mock.patch("sys.stdin.isatty", return_value=True), \
             mock.patch("builtins.input", return_value="oui"):
            self.assertFalse(confirmer("Attention", mot_attendu="SUPPRIMER"))

    def test_entree_vide_refuse(self):
        with mock.patch("sys.stdin.isatty", return_value=True), \
             mock.patch("builtins.input", return_value=""):
            self.assertFalse(confirmer("Attention", mot_attendu="SUPPRIMER"))


class TestConfirmerScriptable(unittest.TestCase):
    def test_sans_tty_jamais_de_prompt(self):
        with mock.patch("sys.stdin.isatty", return_value=False), \
             mock.patch("builtins.input") as m_input:
            confirmer("Attention", mot_attendu="SUPPRIMER", confirmation_scriptable="SUPPRIMER")
        m_input.assert_not_called()

    def test_sans_tty_mot_correct_confirme(self):
        with mock.patch("sys.stdin.isatty", return_value=False):
            self.assertTrue(
                confirmer("Attention", mot_attendu="SUPPRIMER", confirmation_scriptable="SUPPRIMER")
            )

    def test_sans_tty_mot_absent_refuse(self):
        with mock.patch("sys.stdin.isatty", return_value=False):
            self.assertFalse(confirmer("Attention", mot_attendu="SUPPRIMER"))

    def test_sans_tty_mot_incorrect_refuse(self):
        with mock.patch("sys.stdin.isatty", return_value=False):
            self.assertFalse(
                confirmer("Attention", mot_attendu="SUPPRIMER", confirmation_scriptable="oui")
            )


if __name__ == "__main__":
    unittest.main()
