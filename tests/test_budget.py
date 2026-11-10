"""Tests de datasets/budget.py — FILE hybride, split dep/icom, Corse-safe."""
import tempfile
import unittest
from unittest import mock

from rudi_commune_starterkit.datasets import budget
from rudi_commune_starterkit.datasets.budget import DepartementNonSupporte, _dep_icom
from rudi_commune_starterkit.resultat import StatutConnecteur

_GEVEZE = {"nom": "Gévezé", "code_insee": "35120"}


def _reponse_records(total_count):
    r = mock.Mock()
    r.raise_for_status = mock.Mock()
    r.json.return_value = {"total_count": total_count}
    return r


def _reponse_streaming(contenu=b"an;dep;icom\n2024;035;120\n"):
    r = mock.Mock()
    r.raise_for_status = mock.Mock()
    r.headers = {}
    r.iter_content = mock.Mock(return_value=iter([contenu]))
    r.close = mock.Mock()
    return r


def _reponse_dataset_meta(modified="2026-09-24T10:00:00+00:00"):
    r = mock.Mock()
    r.raise_for_status = mock.Mock()
    r.json.return_value = {"metas": {"default": {"modified": modified}}}
    return r


class TestDepIcom(unittest.TestCase):
    def test_metropole(self):
        self.assertEqual(_dep_icom("35120"), ("035", "120"))

    def test_corse_2a(self):
        self.assertEqual(_dep_icom("2A004"), ("02A", "004"))

    def test_corse_2b(self):
        self.assertEqual(_dep_icom("2B033"), ("02B", "033"))

    def test_dom_non_supporte(self):
        with self.assertRaises(DepartementNonSupporte):
            _dep_icom("97411")


class TestMoissonnerBudget(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.dossier = self._tmp.name

    def test_publiable_sans_fichier_local(self):
        session = mock.Mock()
        session.get.side_effect = [_reponse_records(2), _reponse_streaming(), _reponse_dataset_meta()]

        resultat = budget.moissonner(
            "35120", _GEVEZE, dossier_sortie=self.dossier, session_http=session,
        )

        self.assertEqual(resultat.statut, StatutConnecteur.PUBLIABLE)
        licence = resultat.rudi_metadata["access_condition"]["licence"]
        self.assertEqual(licence["licence_type"], "STANDARD")
        self.assertEqual(licence["licence_label"], "etalab-2.0")
        self.assertEqual(resultat.fichiers_filtres, [])

    def test_metadonnees_sans_em_dash(self):
        session = mock.Mock()
        session.get.side_effect = [_reponse_records(2), _reponse_streaming(), _reponse_dataset_meta()]
        resultat = budget.moissonner(
            "35120", _GEVEZE, dossier_sortie=self.dossier, session_http=session,
        )
        self.assertNotIn("—", resultat.rudi_metadata["resource_title"])
        self.assertNotIn("—", resultat.rudi_metadata["synopsis"][0]["text"])
        self.assertNotIn("—", resultat.rudi_metadata["summary"][0]["text"])
        for media in resultat.rudi_metadata["available_formats"]:
            self.assertNotIn("—", media["media_caption"])

    def test_date_source_derivee_de_metas_default_modified(self):
        session = mock.Mock()
        session.get.side_effect = [_reponse_records(2), _reponse_streaming(), _reponse_dataset_meta()]
        resultat = budget.moissonner(
            "35120", _GEVEZE, dossier_sortie=self.dossier, session_http=session,
        )
        self.assertEqual(
            resultat.rudi_metadata["dataset_dates"]["updated"], "2026-09-24T10:00:00Z",
        )

    def test_where_clause_utilise_dep_icom(self):
        session = mock.Mock()
        session.get.side_effect = [_reponse_records(2), _reponse_streaming(), _reponse_dataset_meta()]
        budget.moissonner("35120", _GEVEZE, dossier_sortie=self.dossier, session_http=session)
        premier_appel = session.get.call_args_list[0]
        self.assertEqual(premier_appel.kwargs["params"]["where"], "dep='035' AND icom='120'")

    def test_vide_sans_exercice(self):
        session = mock.Mock()
        session.get.return_value = _reponse_records(0)
        resultat = budget.moissonner(
            "35120", _GEVEZE, dossier_sortie=self.dossier, session_http=session,
        )
        self.assertEqual(resultat.statut, StatutConnecteur.VIDE)

    def test_echec_outre_mer(self):
        session = mock.Mock()
        resultat = budget.moissonner(
            "97411", {"nom": "Saint-Denis", "code_insee": "97411"},
            dossier_sortie=self.dossier, session_http=session,
        )
        self.assertEqual(resultat.statut, StatutConnecteur.ECHEC)
        session.get.assert_not_called()

    def test_echec_reseau(self):
        session = mock.Mock()
        session.get.side_effect = RuntimeError("timeout")
        resultat = budget.moissonner(
            "35120", _GEVEZE, dossier_sortie=self.dossier, session_http=session,
        )
        self.assertEqual(resultat.statut, StatutConnecteur.ECHEC)

    def test_media_url_pointe_vers_export_csv_filtre(self):
        session = mock.Mock()
        session.get.side_effect = [_reponse_records(2), _reponse_streaming(), _reponse_dataset_meta()]
        resultat = budget.moissonner(
            "35120", _GEVEZE, dossier_sortie=self.dossier, session_http=session,
        )
        media = resultat.rudi_metadata["available_formats"][0]
        self.assertIn("exports/csv", media["connector"]["url"])
        self.assertIn("where=", media["connector"]["url"])

    def test_description_riche_mise_en_page_et_contenu_metier(self):
        session = mock.Mock()
        session.get.side_effect = [_reponse_records(2), _reponse_streaming(), _reponse_dataset_meta()]
        resultat = budget.moissonner(
            "35120", _GEVEZE, dossier_sortie=self.dossier, session_http=session,
        )
        html = resultat.rudi_metadata["summary"][0]["html"]
        self.assertIn("<ul>", html)
        self.assertIn("</a>", html)
        self.assertIn("DGFiP", html)
        self.assertIn("comptes communaux", resultat.rudi_metadata["keywords"])


if __name__ == "__main__":
    unittest.main()
