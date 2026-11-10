"""Tests de datasets/deliberations.py — hors Bretagne sans réseau, pagination par curseur."""
import csv
import tempfile
import unittest
from unittest import mock

from rudi_commune_starterkit.datasets import deliberations
from rudi_commune_starterkit.resultat import StatutConnecteur

_GEVEZE = {"nom": "Gévezé", "code_insee": "35120", "code_region": "53"}
_HORS_BRETAGNE = {"nom": "Lyon", "code_insee": "69123", "code_region": "84"}


def _reponse_siren(siren="213501208"):
    r = mock.Mock()
    r.raise_for_status = mock.Mock()
    r.json.return_value = {"results": [{"siren": siren}], "total_results": 1}
    return r


def _reponse_page(resultats, nb_resultats, page_suivante=None):
    r = mock.Mock()
    r.raise_for_status = mock.Mock()
    r.json.return_value = {
        "resultats": resultats, "nb_resultats": nb_resultats, "page_suivante": page_suivante,
    }
    return r


def _acte(id_):
    return {"id": id_, "date_acte": "2026-01-01", "objet": "x", "url": "https://x/" + id_}


class TestMoissonnerDeliberations(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.dossier = self._tmp.name

    def test_hors_bretagne_sans_appel_reseau(self):
        session = mock.Mock()
        resultat = deliberations.moissonner(
            "69123", _HORS_BRETAGNE, dossier_sortie=self.dossier, session_http=session,
        )
        self.assertEqual(resultat.statut, StatutConnecteur.HORS_COUVERTURE)
        session.get.assert_not_called()

    def test_publiable_une_seule_page(self):
        session = mock.Mock()
        session.get.side_effect = [
            _reponse_siren(),
            _reponse_page([_acte("a1"), _acte("a2")], nb_resultats=2, page_suivante=None),
        ]
        resultat = deliberations.moissonner(
            "35120", _GEVEZE, dossier_sortie=self.dossier, session_http=session,
        )
        self.assertEqual(resultat.statut, StatutConnecteur.PUBLIABLE)
        licence = resultat.rudi_metadata["access_condition"]["licence"]
        self.assertEqual(licence["licence_type"], "STANDARD")
        self.assertEqual(licence["licence_label"], "etalab-2.0")
        self.assertEqual(len(resultat.fichiers_filtres), 1)
        with open(resultat.fichiers_filtres[0], encoding="utf-8", newline="") as f:
            actes = list(csv.DictReader(f, delimiter=";"))
        self.assertEqual(len(actes), 2)

    def test_metadonnees_sans_em_dash(self):
        session = mock.Mock()
        session.get.side_effect = [
            _reponse_siren(),
            _reponse_page([_acte("a1"), _acte("a2")], nb_resultats=2, page_suivante=None),
        ]
        resultat = deliberations.moissonner(
            "35120", _GEVEZE, dossier_sortie=self.dossier, session_http=session,
        )
        self.assertNotIn("—", resultat.rudi_metadata["resource_title"])
        self.assertNotIn("—", resultat.rudi_metadata["synopsis"][0]["text"])
        self.assertNotIn("—", resultat.rudi_metadata["summary"][0]["text"])
        for media in resultat.rudi_metadata["available_formats"]:
            self.assertNotIn("—", media["media_caption"])

    def test_pagination_plusieurs_pages(self):
        session = mock.Mock()
        session.get.side_effect = [
            _reponse_siren(),
            _reponse_page([_acte("a1")], nb_resultats=2, page_suivante="curseur1"),
            _reponse_page([_acte("a2")], nb_resultats=2, page_suivante=None),
        ]
        resultat = deliberations.moissonner(
            "35120", _GEVEZE, dossier_sortie=self.dossier, session_http=session,
        )
        self.assertEqual(resultat.statut, StatutConnecteur.PUBLIABLE)
        with open(resultat.fichiers_filtres[0], encoding="utf-8", newline="") as f:
            actes = list(csv.DictReader(f, delimiter=";"))
        self.assertEqual([a["id"] for a in actes], ["a1", "a2"])

    def test_vide_sans_acte(self):
        session = mock.Mock()
        session.get.side_effect = [_reponse_siren(), _reponse_page([], nb_resultats=0)]
        resultat = deliberations.moissonner(
            "35120", _GEVEZE, dossier_sortie=self.dossier, session_http=session,
        )
        self.assertEqual(resultat.statut, StatutConnecteur.VIDE)

    def test_echec_reseau(self):
        session = mock.Mock()
        session.get.side_effect = RuntimeError("DNS")
        resultat = deliberations.moissonner(
            "35120", _GEVEZE, dossier_sortie=self.dossier, session_http=session,
        )
        self.assertEqual(resultat.statut, StatutConnecteur.ECHEC)

    def test_producteur_est_toujours_la_commune(self):
        session = mock.Mock()
        session.get.side_effect = [
            _reponse_siren(), _reponse_page([_acte("a1")], nb_resultats=1, page_suivante=None),
        ]
        resultat = deliberations.moissonner(
            "35120", _GEVEZE, dossier_sortie=self.dossier,
            mode_producer="source", session_http=session,
        )
        self.assertIn("Gévezé", resultat.rudi_metadata["producer"]["organization_name"])


if __name__ == "__main__":
    unittest.main()
