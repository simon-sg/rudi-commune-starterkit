"""Tests de datasets/eau_potable.py — FILE hybride, fenêtre temporelle de 5 ans."""
import tempfile
import unittest
from unittest import mock

from rudi_commune_starterkit.datasets import eau_potable
from rudi_commune_starterkit.resultat import StatutConnecteur

_GEVEZE = {"nom": "Gévezé", "code_insee": "35120"}


def _reponse_json(count):
    r = mock.Mock()
    r.raise_for_status = mock.Mock()
    r.json.return_value = {"count": count, "data": []}
    return r


def _reponse_streaming(contenu=b'{"data": []}'):
    r = mock.Mock()
    r.raise_for_status = mock.Mock()
    r.headers = {}
    r.iter_content = mock.Mock(return_value=iter([contenu]))
    r.close = mock.Mock()
    return r


class TestMoissonnerEauPotable(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.dossier = self._tmp.name

    def test_publiable_sans_fichier_local(self):
        session = mock.Mock()
        session.get.side_effect = [_reponse_json(3148), _reponse_streaming()]
        resultat = eau_potable.moissonner(
            "35120", _GEVEZE, dossier_sortie=self.dossier, session_http=session,
        )
        self.assertEqual(resultat.statut, StatutConnecteur.PUBLIABLE)
        licence = resultat.rudi_metadata["access_condition"]["licence"]
        self.assertEqual(licence["licence_type"], "STANDARD")
        self.assertEqual(licence["licence_label"], "etalab-2.0")
        self.assertEqual(resultat.fichiers_filtres, [])

    def test_metadonnees_sans_em_dash(self):
        session = mock.Mock()
        session.get.side_effect = [_reponse_json(3148), _reponse_streaming()]
        resultat = eau_potable.moissonner(
            "35120", _GEVEZE, dossier_sortie=self.dossier, session_http=session,
        )
        self.assertNotIn("—", resultat.rudi_metadata["resource_title"])
        self.assertNotIn("—", resultat.rudi_metadata["synopsis"][0]["text"])
        self.assertNotIn("—", resultat.rudi_metadata["summary"][0]["text"])
        for media in resultat.rudi_metadata["available_formats"]:
            self.assertNotIn("—", media["media_caption"])

    def test_url_contient_code_commune_et_fenetre_temporelle(self):
        session = mock.Mock()
        session.get.side_effect = [_reponse_json(3148), _reponse_streaming()]
        resultat = eau_potable.moissonner(
            "35120", _GEVEZE, dossier_sortie=self.dossier, session_http=session,
        )
        media = resultat.rudi_metadata["available_formats"][0]
        url = media["connector"]["url"]
        self.assertIn("code_commune=35120", url)
        self.assertIn("date_min_prelevement=", url)

    def test_vide_sans_resultat(self):
        session = mock.Mock()
        session.get.return_value = _reponse_json(0)
        resultat = eau_potable.moissonner(
            "35120", _GEVEZE, dossier_sortie=self.dossier, session_http=session,
        )
        self.assertEqual(resultat.statut, StatutConnecteur.VIDE)

    def test_echec_reseau(self):
        session = mock.Mock()
        session.get.side_effect = RuntimeError("timeout")
        resultat = eau_potable.moissonner(
            "35120", _GEVEZE, dossier_sortie=self.dossier, session_http=session,
        )
        self.assertEqual(resultat.statut, StatutConnecteur.ECHEC)

    def test_producteur_ars_en_mode_source(self):
        session = mock.Mock()
        session.get.side_effect = [_reponse_json(3148), _reponse_streaming()]
        resultat = eau_potable.moissonner(
            "35120", _GEVEZE, dossier_sortie=self.dossier, session_http=session,
        )
        self.assertIn("ARS", resultat.rudi_metadata["producer"]["organization_name"])

    def test_description_riche_mise_en_page_et_contenu_metier(self):
        session = mock.Mock()
        session.get.side_effect = [_reponse_json(3148), _reponse_streaming()]
        resultat = eau_potable.moissonner(
            "35120", _GEVEZE, dossier_sortie=self.dossier, session_http=session,
        )
        html = resultat.rudi_metadata["summary"][0]["html"]
        self.assertIn("<ul>", html)
        self.assertIn("</a>", html)
        self.assertIn("SISE-Eaux", html)
        self.assertIn("santé publique", resultat.rudi_metadata["keywords"])


if __name__ == "__main__":
    unittest.main()
