"""Tests de description_commune.py — repli explicite, attribution CC BY-SA intégrée au
texte. Zéro réseau (resumer_commune_wikipedia mocké)."""
import unittest
from unittest import mock

from rudi_commune_starterkit.description_commune import construire_description_commune

_GEVEZE = {"nom": "Gévezé", "code_insee": "35120"}


_RESUME_SANS_INFOS = {
    "caption": "Gévezé", "summary": "Gévezé est une commune.",
    "url": "https://fr.wikipedia.org/wiki/G%C3%A9vez%C3%A9", "qid": "Q1",
}


class TestConstruireDescriptionCommune(unittest.TestCase):
    def test_wikipedia_trouve(self):
        with mock.patch(
            "rudi_commune_starterkit.description_commune.resumer_commune_wikipedia",
            return_value=_RESUME_SANS_INFOS,
        ), mock.patch(
            "rudi_commune_starterkit.description_commune.maire_actuel", return_value=None,
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

    def test_paragraphe_complementaire_maire_gentile_superficie(self):
        resume = {**_RESUME_SANS_INFOS, "gentile": "Gévézéens", "superficie_km2": 29.55}
        with mock.patch(
            "rudi_commune_starterkit.description_commune.resumer_commune_wikipedia",
            return_value=resume,
        ), mock.patch(
            "rudi_commune_starterkit.description_commune.maire_actuel",
            return_value={"nom": "DEHAESE", "prenom": "Olivier",
                          "date_debut_fonction": "2026-03-20"},
        ):
            resultat = construire_description_commune(_GEVEZE)
        texte = resultat["organization_summary"]
        self.assertIn("Olivier DEHAESE", texte)
        self.assertIn("depuis 2026", texte)
        self.assertIn("Gévézéens", texte)
        self.assertIn("29,55 km²", texte)

    def test_paragraphe_complementaire_absent_si_rien_de_disponible(self):
        with mock.patch(
            "rudi_commune_starterkit.description_commune.resumer_commune_wikipedia",
            return_value=_RESUME_SANS_INFOS,
        ), mock.patch(
            "rudi_commune_starterkit.description_commune.maire_actuel", return_value=None,
        ):
            resultat = construire_description_commune(_GEVEZE)
        # Pas de double saut de ligne (paragraphe vide) entre le résumé et l'attribution.
        self.assertNotIn("\n\n\n", resultat["organization_summary"])
        self.assertIn("Gévezé est une commune.\n\nTexte issu de", resultat["organization_summary"])

    def test_paragraphe_complementaire_partiel_gentile_seul(self):
        resume = {**_RESUME_SANS_INFOS, "gentile": "Gévézéens"}
        with mock.patch(
            "rudi_commune_starterkit.description_commune.resumer_commune_wikipedia",
            return_value=resume,
        ), mock.patch(
            "rudi_commune_starterkit.description_commune.maire_actuel", return_value=None,
        ):
            resultat = construire_description_commune(_GEVEZE)
        texte = resultat["organization_summary"]
        self.assertIn("Ses habitants sont appelés les Gévézéens.", texte)
        self.assertNotIn("maire", texte.lower())

    def test_transmet_dossier_cache_rne_au_maire_actuel(self):
        with mock.patch(
            "rudi_commune_starterkit.description_commune.resumer_commune_wikipedia",
            return_value=_RESUME_SANS_INFOS,
        ), mock.patch(
            "rudi_commune_starterkit.description_commune.maire_actuel", return_value=None,
        ) as m_maire:
            session = mock.Mock()
            construire_description_commune(
                _GEVEZE, session_http=session, dossier_cache_rne="/tmp/rne",
            )
        m_maire.assert_called_once_with(
            "35120", session_http=session, dossier_cache="/tmp/rne",
        )


if __name__ == "__main__":
    unittest.main()
