"""Tests de datasets/irve.py — FILE hybride, filtre combiné nom+code_insee."""
import tempfile
import unittest
from unittest import mock

from rudi_commune_starterkit.datasets import irve
from rudi_commune_starterkit.resultat import StatutConnecteur

_GEVEZE = {"nom": "Gévezé", "code_insee": "35120"}


def _reponse_records(total_count):
    r = mock.Mock()
    r.raise_for_status = mock.Mock()
    r.json.return_value = {"total_count": total_count}
    return r


def _reponse_streaming(contenu=b"id;nom\n1;Carrefour\n"):
    r = mock.Mock()
    r.raise_for_status = mock.Mock()
    r.headers = {}
    r.iter_content = mock.Mock(return_value=iter([contenu]))
    r.close = mock.Mock()
    return r


class TestMoissonnerIrve(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.dossier = self._tmp.name

    def test_publiable_sans_fichier_local(self):
        session = mock.Mock()
        session.get.side_effect = [_reponse_records(4), _reponse_streaming()]
        resultat = irve.moissonner(
            "35120", _GEVEZE, dossier_sortie=self.dossier, session_http=session,
        )
        self.assertEqual(resultat.statut, StatutConnecteur.PUBLIABLE)
        self.assertEqual(resultat.fichiers_filtres, [])

    def test_metadonnees_sans_em_dash(self):
        session = mock.Mock()
        session.get.side_effect = [_reponse_records(4), _reponse_streaming()]
        resultat = irve.moissonner(
            "35120", _GEVEZE, dossier_sortie=self.dossier, session_http=session,
        )
        self.assertNotIn("—", resultat.rudi_metadata["resource_title"])
        self.assertNotIn("—", resultat.rudi_metadata["synopsis"][0]["text"])
        self.assertNotIn("—", resultat.rudi_metadata["summary"][0]["text"])
        for media in resultat.rudi_metadata["available_formats"]:
            self.assertNotIn("—", media["media_caption"])

    def test_where_combine_nom_et_code_insee(self):
        session = mock.Mock()
        session.get.side_effect = [_reponse_records(4), _reponse_streaming()]
        irve.moissonner("35120", _GEVEZE, dossier_sortie=self.dossier, session_http=session)
        premier_appel = session.get.call_args_list[0]
        self.assertEqual(
            premier_appel.kwargs["params"]["where"],
            "consolidated_commune='Gévezé' AND code_insee_commune='35120'",
        )

    def test_echappement_apostrophe_dans_le_nom(self):
        session = mock.Mock()
        session.get.side_effect = [_reponse_records(0)]
        commune = {"nom": "L'Abergement-Clémenciat", "code_insee": "01001"}
        irve.moissonner("01001", commune, dossier_sortie=self.dossier, session_http=session)
        premier_appel = session.get.call_args_list[0]
        self.assertIn("''Abergement", premier_appel.kwargs["params"]["where"])

    def test_vide_sans_borne(self):
        session = mock.Mock()
        session.get.return_value = _reponse_records(0)
        resultat = irve.moissonner(
            "35120", _GEVEZE, dossier_sortie=self.dossier, session_http=session,
        )
        self.assertEqual(resultat.statut, StatutConnecteur.VIDE)

    def test_echec_reseau(self):
        session = mock.Mock()
        session.get.side_effect = RuntimeError("timeout")
        resultat = irve.moissonner(
            "35120", _GEVEZE, dossier_sortie=self.dossier, session_http=session,
        )
        self.assertEqual(resultat.statut, StatutConnecteur.ECHEC)


if __name__ == "__main__":
    unittest.main()
