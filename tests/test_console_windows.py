import io
import unittest
from unittest import mock

from rudi_commune_starterkit.console_windows import forcer_utf8_console


class TestForcerUtf8Console(unittest.TestCase):
    def test_reconfigure_stdout_et_stderr_en_utf8(self):
        m_stdout = mock.Mock()
        m_stderr = mock.Mock()
        with mock.patch("sys.stdout", m_stdout), mock.patch("sys.stderr", m_stderr):
            forcer_utf8_console()
        m_stdout.reconfigure.assert_called_once_with(encoding="utf-8", errors="replace")
        m_stderr.reconfigure.assert_called_once_with(encoding="utf-8", errors="replace")

    def test_flux_sans_reconfigure_ne_leve_pas(self):
        """Un flux redirigé vers un objet sans `reconfigure` (ex. certains contextes
        de test) ne doit jamais faire planter l'appelant — ce correctif est un
        confort, jamais une condition requise."""
        with mock.patch("sys.stdout", io.StringIO()):
            forcer_utf8_console()  # ne doit pas lever

    def test_erreur_a_la_reconfiguration_est_avalee(self):
        m_stdout = mock.Mock()
        m_stdout.reconfigure.side_effect = ValueError("flux déjà utilisé")
        with mock.patch("sys.stdout", m_stdout):
            forcer_utf8_console()  # ne doit pas lever

    def test_caractere_hors_cp1252_imprime_sans_lever(self):
        """Bug réel corrigé le 2026-11-17 (VM Windows 11 fr-FR) : sans ce
        correctif, `print()` d'un caractère comme « → » lève `UnicodeEncodeError`
        sur un flux encodé en cp1252/cp850 (codepage par défaut de la console
        Windows). Reproduit ici avec un vrai flux texte encodé en cp1252, pas un
        mock de `print`."""
        flux = io.TextIOWrapper(io.BytesIO(), encoding="cp1252")
        with mock.patch("sys.stdout", flux), mock.patch("sys.stderr", flux):
            forcer_utf8_console()
        print("→ test", file=flux)  # ne doit pas lever UnicodeEncodeError
        flux.flush()


if __name__ == "__main__":
    unittest.main()
