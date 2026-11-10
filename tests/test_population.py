"""Tests de datasets/population.py — FILE hybride, zéro fichier local."""
import os
import tempfile
import unittest
from unittest import mock

from rudi_commune_starterkit.datasets import population
from rudi_commune_starterkit.resultat import StatutConnecteur

_GEVEZE = {"nom": "Gévezé", "code_insee": "35120"}
_OBSERVATIONS = [
    {"dimensions": {"TIME_PERIOD": "2019", "POPREF_MEASURE": "PMUN"},
     "measures": {"OBS_VALUE_NIVEAU": {"value": 5521.0}}},
]


def _reponse_json(observations):
    r = mock.Mock()
    r.raise_for_status = mock.Mock()
    r.json.return_value = {"observations": observations}
    return r


def _reponse_streaming(contenu=b"[1,2,3]"):
    r = mock.Mock()
    r.raise_for_status = mock.Mock()
    r.headers = {}
    r.iter_content = mock.Mock(return_value=iter([contenu]))
    r.close = mock.Mock()
    return r


class TestMoissonnerPopulation(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.dossier = self._tmp.name

    def test_publiable_sans_fichier_local(self):
        session = mock.Mock()
        session.get.side_effect = [_reponse_json(_OBSERVATIONS), _reponse_streaming()]

        resultat = population.moissonner(
            "35120", _GEVEZE, dossier_sortie=self.dossier, session_http=session,
        )

        self.assertEqual(resultat.statut, StatutConnecteur.PUBLIABLE)
        licence = resultat.rudi_metadata["access_condition"]["licence"]
        self.assertEqual(licence["licence_type"], "STANDARD")
        self.assertEqual(licence["licence_label"], "etalab-2.0")
        self.assertEqual(resultat.fichiers_filtres, [])
        self.assertEqual(os.listdir(self.dossier), [])

    def test_metadonnees_sans_em_dash(self):
        session = mock.Mock()
        session.get.side_effect = [_reponse_json(_OBSERVATIONS), _reponse_streaming()]
        resultat = population.moissonner(
            "35120", _GEVEZE, dossier_sortie=self.dossier, session_http=session,
        )
        self.assertNotIn("—", resultat.rudi_metadata["resource_title"])
        self.assertNotIn("—", resultat.rudi_metadata["synopsis"][0]["text"])
        self.assertNotIn("—", resultat.rudi_metadata["summary"][0]["text"])
        for media in resultat.rudi_metadata["available_formats"]:
            self.assertNotIn("—", media["media_caption"])

    def test_media_hybride_url_distante_conservee(self):
        session = mock.Mock()
        session.get.side_effect = [_reponse_json(_OBSERVATIONS), _reponse_streaming()]
        resultat = population.moissonner(
            "35120", _GEVEZE, dossier_sortie=self.dossier, session_http=session,
        )
        media = resultat.rudi_metadata["available_formats"][0]
        self.assertEqual(media["media_type"], "FILE")
        self.assertIn("GEO=COM-35120", media["connector"]["url"])
        self.assertTrue(media["checksum"]["hash"])

    def test_vide_sans_observations(self):
        session = mock.Mock()
        session.get.return_value = _reponse_json([])
        resultat = population.moissonner(
            "35120", _GEVEZE, dossier_sortie=self.dossier, session_http=session,
        )
        self.assertEqual(resultat.statut, StatutConnecteur.VIDE)

    def test_echec_reseau(self):
        session = mock.Mock()
        session.get.side_effect = RuntimeError("timeout")
        resultat = population.moissonner(
            "35120", _GEVEZE, dossier_sortie=self.dossier, session_http=session,
        )
        self.assertEqual(resultat.statut, StatutConnecteur.ECHEC)

    def test_mode_commune(self):
        session = mock.Mock()
        session.get.side_effect = [_reponse_json(_OBSERVATIONS), _reponse_streaming()]
        resultat = population.moissonner(
            "35120", _GEVEZE, dossier_sortie=self.dossier, mode_producer="commune",
            contact_email_commune="mairie@geveze.fr", session_http=session,
        )
        self.assertEqual(
            resultat.rudi_metadata["producer"]["organization_name"], "Commune de Gévezé"
        )

    def test_geography_resolue_depuis_le_contour_commune(self):
        # Preuve bout-en-bout (v3, Axe 6) que geography_pour_commune() est bien
        # transmis jusqu'à construire_rudi_metadata() — le test de contrat statique
        # de test_registre.py vérifie les 13 modules mais pas que le câblage produit
        # réellement la clé attendue dans rudi_metadata.
        commune_avec_contour = {
            **_GEVEZE,
            "contour": {
                "type": "Polygon",
                "coordinates": [[
                    [-1.75, 48.20], [-1.70, 48.20], [-1.70, 48.24], [-1.75, 48.24],
                    [-1.75, 48.20],
                ]],
            },
        }
        session = mock.Mock()
        session.get.side_effect = [_reponse_json(_OBSERVATIONS), _reponse_streaming()]
        resultat = population.moissonner(
            "35120", commune_avec_contour, dossier_sortie=self.dossier, session_http=session,
        )
        self.assertEqual(resultat.rudi_metadata["geography"]["bounding_box"], {
            "west_longitude": -1.75, "east_longitude": -1.70,
            "south_latitude": 48.20, "north_latitude": 48.24,
        })

    def test_pas_de_geography_si_contour_absent(self):
        session = mock.Mock()
        session.get.side_effect = [_reponse_json(_OBSERVATIONS), _reponse_streaming()]
        resultat = population.moissonner(
            "35120", _GEVEZE, dossier_sortie=self.dossier, session_http=session,
        )
        self.assertNotIn("geography", resultat.rudi_metadata)

    def test_description_riche_mise_en_page_et_contenu_metier(self):
        # v3, Axe 3 : forme (liste + lien final) ET contenu (mot-clé métier propre à ce
        # module) — un test de forme seul laisserait passer un contenu copié-collé.
        session = mock.Mock()
        session.get.side_effect = [_reponse_json(_OBSERVATIONS), _reponse_streaming()]
        resultat = population.moissonner(
            "35120", _GEVEZE, dossier_sortie=self.dossier, session_http=session,
        )
        html = resultat.rudi_metadata["summary"][0]["html"]
        self.assertIn("<ul>", html)
        self.assertIn("</a>", html)
        self.assertIn("Melodi", html)
        self.assertIn("démographie", resultat.rudi_metadata["keywords"])


if __name__ == "__main__":
    unittest.main()
