"""Tests de datasets/associations.py — filtre nature_juridique=9220, statuts."""
import os
import tempfile
import unittest
from unittest import mock

from rudi_commune_starterkit.datasets import associations
from rudi_commune_starterkit.resultat import StatutConnecteur

_GEVEZE = {"nom": "Gévezé", "code_insee": "35120"}
_RESULTAT = {
    "siren": "775685506", "nom_complet": "ASSOCIATION TEST", "nature_juridique": "9220",
    "matching_etablissements": [{"siret": "77568550600010"}],
}


def _reponse_page(resultats):
    r = mock.Mock()
    r.raise_for_status = mock.Mock()
    r.json.return_value = {"results": resultats, "page": 1, "total_pages": 1}
    return r


class TestMoissonnerAssociations(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.dossier = self._tmp.name

    def test_filtre_nature_juridique_transmis(self):
        session = mock.Mock()
        session.get.return_value = _reponse_page([_RESULTAT])
        associations.moissonner("35120", _GEVEZE, dossier_sortie=self.dossier, session_http=session)
        _, kwargs = session.get.call_args
        self.assertEqual(kwargs["params"]["nature_juridique"], "9220")
        self.assertNotIn("etat_administratif", kwargs["params"])

    def test_publiable(self):
        session = mock.Mock()
        session.get.return_value = _reponse_page([_RESULTAT])
        resultat = associations.moissonner(
            "35120", _GEVEZE, dossier_sortie=self.dossier, session_http=session,
        )
        self.assertEqual(resultat.statut, StatutConnecteur.PUBLIABLE)
        licence = resultat.rudi_metadata["access_condition"]["licence"]
        self.assertEqual(licence["licence_type"], "CUSTOM")
        self.assertTrue(os.path.isfile(resultat.fichiers_filtres[0]))

    def test_date_source_derivee_du_max_date_mise_a_jour(self):
        session = mock.Mock()
        resultat_date = {**_RESULTAT, "date_mise_a_jour_rne": "2026-03-04T16:22:49"}
        session.get.return_value = _reponse_page([resultat_date])
        resultat = associations.moissonner(
            "35120", _GEVEZE, dossier_sortie=self.dossier, session_http=session,
        )
        self.assertEqual(
            resultat.rudi_metadata["dataset_dates"]["updated"], "2026-03-04T16:22:49Z",
        )

    def test_metadonnees_sans_em_dash(self):
        session = mock.Mock()
        session.get.return_value = _reponse_page([_RESULTAT])
        resultat = associations.moissonner(
            "35120", _GEVEZE, dossier_sortie=self.dossier, session_http=session,
        )
        self.assertNotIn("—", resultat.rudi_metadata["resource_title"])
        self.assertNotIn("—", resultat.rudi_metadata["synopsis"][0]["text"])
        self.assertNotIn("—", resultat.rudi_metadata["summary"][0]["text"])

    def test_second_media_geojson_si_coordonnees_exploitables(self):
        session = mock.Mock()
        resultat_avec_coords = {
            **_RESULTAT,
            "matching_etablissements": [{
                "siret": "77568550600010",
                "latitude": "48.220806213", "longitude": "-1.788383609",
            }],
        }
        session.get.return_value = _reponse_page([resultat_avec_coords])
        resultat = associations.moissonner(
            "35120", _GEVEZE, dossier_sortie=self.dossier, session_http=session,
        )
        medias_geojson = [
            m for m in resultat.rudi_metadata["available_formats"]
            if m["media_name"].endswith(".geojson")
        ]
        self.assertEqual(len(medias_geojson), 1)
        self.assertEqual(len(resultat.fichiers_filtres), 2)

    def test_pas_de_media_geojson_sans_coordonnees_exploitables(self):
        session = mock.Mock()
        session.get.return_value = _reponse_page([_RESULTAT])
        resultat = associations.moissonner(
            "35120", _GEVEZE, dossier_sortie=self.dossier, session_http=session,
        )
        medias_geojson = [
            m for m in resultat.rudi_metadata["available_formats"]
            if m["media_name"].endswith(".geojson")
        ]
        self.assertEqual(medias_geojson, [])

    def test_vide(self):
        session = mock.Mock()
        session.get.return_value = _reponse_page([])
        resultat = associations.moissonner(
            "35120", _GEVEZE, dossier_sortie=self.dossier, session_http=session,
        )
        self.assertEqual(resultat.statut, StatutConnecteur.VIDE)

    def test_cle_distincte_de_entreprises(self):
        from rudi_commune_starterkit.datasets import entreprises
        self.assertNotEqual(associations.CLE, entreprises.CLE)

    def test_description_riche_mise_en_page_et_contenu_metier(self):
        session = mock.Mock()
        session.get.return_value = _reponse_page([_RESULTAT])
        resultat = associations.moissonner(
            "35120", _GEVEZE, dossier_sortie=self.dossier, session_http=session,
        )
        html = resultat.rudi_metadata["summary"][0]["html"]
        self.assertIn("<ul>", html)
        self.assertIn("</a>", html)
        self.assertIn("9220", html)
        self.assertIn("vie associative", resultat.rudi_metadata["keywords"])


if __name__ == "__main__":
    unittest.main()
