"""Tests de datasets/marches_publics.py — résolution SIREN puis filtre startswith."""
import tempfile
import unittest
from unittest import mock

from rudi_commune_starterkit.datasets import marches_publics
from rudi_commune_starterkit.resultat import StatutConnecteur

_GEVEZE = {"nom": "Gévezé", "code_insee": "35120"}


def _reponse_siren(siren="213501208"):
    r = mock.Mock()
    r.raise_for_status = mock.Mock()
    r.json.return_value = {"results": [{"siren": siren}], "total_results": 1}
    return r


def _reponse_records(total_count):
    r = mock.Mock()
    r.raise_for_status = mock.Mock()
    r.json.return_value = {"total_count": total_count}
    return r


def _reponse_streaming(contenu=b"id;acheteur_id\n1;213501208xxxxx\n"):
    r = mock.Mock()
    r.raise_for_status = mock.Mock()
    r.headers = {}
    r.iter_content = mock.Mock(return_value=iter([contenu]))
    r.close = mock.Mock()
    return r


class TestMoissonnerMarchesPublics(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.dossier = self._tmp.name

    def test_publiable(self):
        session = mock.Mock()
        session.get.side_effect = [_reponse_siren(), _reponse_records(13), _reponse_streaming()]
        resultat = marches_publics.moissonner(
            "35120", _GEVEZE, dossier_sortie=self.dossier, session_http=session,
        )
        self.assertEqual(resultat.statut, StatutConnecteur.PUBLIABLE)
        self.assertEqual(resultat.fichiers_filtres, [])

    def test_metadonnees_sans_em_dash(self):
        session = mock.Mock()
        session.get.side_effect = [_reponse_siren(), _reponse_records(13), _reponse_streaming()]
        resultat = marches_publics.moissonner(
            "35120", _GEVEZE, dossier_sortie=self.dossier, session_http=session,
        )
        self.assertNotIn("—", resultat.rudi_metadata["resource_title"])
        self.assertNotIn("—", resultat.rudi_metadata["synopsis"][0]["text"])
        self.assertNotIn("—", resultat.rudi_metadata["summary"][0]["text"])
        for media in resultat.rudi_metadata["available_formats"]:
            self.assertNotIn("—", media["media_caption"])

    def test_where_utilise_startswith_sur_le_siren_resolu(self):
        session = mock.Mock()
        session.get.side_effect = [_reponse_siren("213501208"), _reponse_records(13), _reponse_streaming()]
        marches_publics.moissonner("35120", _GEVEZE, dossier_sortie=self.dossier, session_http=session)
        deuxieme_appel = session.get.call_args_list[1]
        self.assertEqual(
            deuxieme_appel.kwargs["params"]["where"], "startswith(acheteur_id, '213501208')"
        )

    def test_vide_sans_marche(self):
        session = mock.Mock()
        session.get.side_effect = [_reponse_siren(), _reponse_records(0)]
        resultat = marches_publics.moissonner(
            "35120", _GEVEZE, dossier_sortie=self.dossier, session_http=session,
        )
        self.assertEqual(resultat.statut, StatutConnecteur.VIDE)

    def test_echec_resolution_siren(self):
        session = mock.Mock()
        session.get.side_effect = RuntimeError("DNS")
        resultat = marches_publics.moissonner(
            "35120", _GEVEZE, dossier_sortie=self.dossier, session_http=session,
        )
        self.assertEqual(resultat.statut, StatutConnecteur.ECHEC)

    def test_echec_requete_decp(self):
        session = mock.Mock()
        session.get.side_effect = [_reponse_siren(), RuntimeError("500")]
        resultat = marches_publics.moissonner(
            "35120", _GEVEZE, dossier_sortie=self.dossier, session_http=session,
        )
        self.assertEqual(resultat.statut, StatutConnecteur.ECHEC)


if __name__ == "__main__":
    unittest.main()
