"""Tests de datasets/adresses.py — FILE copie, filtrage d'un CSV.gz départemental."""
import csv
import gzip
import io
import tempfile
import unittest
from unittest import mock

from rudi_commune_starterkit.datasets import adresses
from rudi_commune_starterkit.resultat import StatutConnecteur

_GEVEZE = {"nom": "Gévezé", "code_insee": "35120", "code_departement": "35"}

_LIGNES_BAN = [
    {"id": "35120_0001", "numero": "1", "nom_voie": "Rue de la Mairie",
     "code_postal": "35630", "code_insee": "35120", "nom_commune": "Gévezé"},
    {"id": "35002_0001", "numero": "1", "nom_voie": "Rue Autre",
     "code_postal": "35150", "code_insee": "35002", "nom_commune": "Amanlis"},
]


def _gz_ban(lignes=_LIGNES_BAN):
    tampon = io.StringIO()
    writer = csv.DictWriter(tampon, fieldnames=list(lignes[0].keys()), delimiter=";")
    writer.writeheader()
    writer.writerows(lignes)
    return gzip.compress(tampon.getvalue().encode("utf-8"))


def _reponse_telechargement(contenu):
    r = mock.Mock()
    r.raise_for_status = mock.Mock()
    r.iter_content = mock.Mock(return_value=iter([contenu]))
    r.close = mock.Mock()
    return r


class TestMoissonnerAdresses(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.dossier = self._tmp.name

    def test_publiable_filtre_sur_la_commune(self):
        session = mock.Mock()
        session.get.return_value = _reponse_telechargement(_gz_ban())
        resultat = adresses.moissonner(
            "35120", _GEVEZE, dossier_sortie=self.dossier, session_http=session,
        )
        self.assertEqual(resultat.statut, StatutConnecteur.PUBLIABLE)
        with open(resultat.fichiers_filtres[0], encoding="utf-8") as f:
            lignes = list(csv.DictReader(f, delimiter=";"))
        self.assertEqual(len(lignes), 1)
        self.assertEqual(lignes[0]["nom_commune"], "Gévezé")

    def test_metadonnees_sans_em_dash(self):
        session = mock.Mock()
        session.get.return_value = _reponse_telechargement(_gz_ban())
        resultat = adresses.moissonner(
            "35120", _GEVEZE, dossier_sortie=self.dossier, session_http=session,
        )
        self.assertNotIn("—", resultat.rudi_metadata["resource_title"])
        self.assertNotIn("—", resultat.rudi_metadata["synopsis"][0]["text"])
        for media in resultat.rudi_metadata["available_formats"]:
            self.assertNotIn("—", media["media_caption"])

    def test_url_departementale_utilise_code_departement(self):
        session = mock.Mock()
        session.get.return_value = _reponse_telechargement(_gz_ban())
        adresses.moissonner("35120", _GEVEZE, dossier_sortie=self.dossier, session_http=session)
        url_appelee = session.get.call_args_list[0].args[0]
        self.assertIn("adresses-35.csv.gz", url_appelee)

    def test_vide_sans_adresse(self):
        session = mock.Mock()
        autre_commune = [{**l, "code_insee": "99999"} for l in _LIGNES_BAN]
        session.get.return_value = _reponse_telechargement(_gz_ban(autre_commune))
        resultat = adresses.moissonner(
            "35120", _GEVEZE, dossier_sortie=self.dossier, session_http=session,
        )
        self.assertEqual(resultat.statut, StatutConnecteur.VIDE)

    def test_echec_telechargement(self):
        session = mock.Mock()
        session.get.side_effect = RuntimeError("500")
        resultat = adresses.moissonner(
            "35120", _GEVEZE, dossier_sortie=self.dossier, session_http=session,
        )
        self.assertEqual(resultat.statut, StatutConnecteur.ECHEC)


if __name__ == "__main__":
    unittest.main()
