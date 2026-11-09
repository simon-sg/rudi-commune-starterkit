"""Tests de description_commune.py — repli explicite, attribution CC BY-SA intégrée au
texte. Zéro réseau (resumer_commune_wikipedia mocké)."""
import unittest
from unittest import mock

from rudi_commune_starterkit.description_commune import construire_description_commune

_GEVEZE = {"nom": "Gévezé", "code_insee": "35120"}


class TestConstruireDescriptionCommune(unittest.TestCase):
    def test_wikipedia_trouve(self):
        with mock.patch(
            "rudi_commune_starterkit.description_commune.resumer_commune_wikipedia",
            return_value={"caption": "Gévezé", "summary": "Gévezé est une commune.",
                          "url": "https://fr.wikipedia.org/wiki/G%C3%A9vez%C3%A9", "qid": "Q1"},
        ):
            resultat = construire_description_commune(_GEVEZE)
        self.assertEqual(resultat["source"], "wikipedia")
        self.assertIn("Gévezé est une commune.", resultat["organization_summary"])
        self.assertIn("CC BY-SA", resultat["organization_summary"])
        self.assertIn("creativecommons.org/licenses/by-sa", resultat["organization_summary"])
        self.assertEqual(resultat["url"], "https://fr.wikipedia.org/wiki/G%C3%A9vez%C3%A9")

    def test_repli_generique_si_wikipedia_absent(self):
        with mock.patch(
            "rudi_commune_starterkit.description_commune.resumer_commune_wikipedia",
            return_value=None,
        ):
            resultat = construire_description_commune(_GEVEZE)
        self.assertEqual(resultat["source"], "repli_generique")
        self.assertIsNone(resultat["url"])
        self.assertIn("Gévezé", resultat["organization_summary"])
        self.assertIn("35120", resultat["organization_summary"])

    def test_transmet_code_insee_session_et_cache(self):
        with mock.patch(
            "rudi_commune_starterkit.description_commune.resumer_commune_wikipedia",
            return_value=None,
        ) as m_resumer:
            session = mock.Mock()
            construire_description_commune(_GEVEZE, session_http=session, dossier_cache="/tmp/x")
        m_resumer.assert_called_once_with(
            "35120", session_http=session, dossier_cache="/tmp/x",
        )


if __name__ == "__main__":
    unittest.main()
