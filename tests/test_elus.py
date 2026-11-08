"""Tests de datasets/elus.py — FILE copie, allowlist de colonnes personnelles."""
import csv
import io
import tempfile
import unittest
from unittest import mock

from rudi_commune_starterkit.datasets import elus
from rudi_commune_starterkit.resultat import StatutConnecteur

_GEVEZE = {"nom": "Gévezé", "code_insee": "35120"}

_ENTETES_RNE = [
    "Code du département", "Libellé du département", "Code de la commune",
    "Libellé de la commune", "Nom de l'élu", "Prénom de l'élu", "Code sexe",
    "Date de naissance", "Code de la catégorie socio-professionnelle",
    "Libellé de la catégorie socio-professionnelle", "Date de début du mandat",
    "Libellé de la fonction", "Date de début de la fonction", "Code nationalité",
]

_LIGNES_RNE = [
    {"Code du département": "35", "Libellé du département": "Ille-et-Vilaine",
     "Code de la commune": "35120", "Libellé de la commune": "Gévezé",
     "Nom de l'élu": "DUPONT", "Prénom de l'élu": "Marie", "Code sexe": "F",
     "Date de naissance": "1970-01-01",
     "Code de la catégorie socio-professionnelle": "37",
     "Libellé de la catégorie socio-professionnelle": "Cadre",
     "Date de début du mandat": "2026-03-15", "Libellé de la fonction": "Maire",
     "Date de début de la fonction": "2026-03-20", "Code nationalité": "FR"},
    {"Code du département": "35", "Libellé du département": "Ille-et-Vilaine",
     "Code de la commune": "35002", "Libellé de la commune": "Amanlis",
     "Nom de l'élu": "AUTRE", "Prénom de l'élu": "Paul", "Code sexe": "M",
     "Date de naissance": "1980-01-01",
     "Code de la catégorie socio-professionnelle": "12",
     "Libellé de la catégorie socio-professionnelle": "Agriculteur",
     "Date de début du mandat": "2026-03-15", "Libellé de la fonction": "",
     "Date de début de la fonction": "", "Code nationalité": "FR"},
]


def _csv_rne(lignes=_LIGNES_RNE):
    tampon = io.StringIO()
    writer = csv.DictWriter(tampon, fieldnames=_ENTETES_RNE, delimiter=";")
    writer.writeheader()
    writer.writerows(lignes)
    return tampon.getvalue().encode("utf-8")


def _reponse_metadata():
    r = mock.Mock()
    r.raise_for_status = mock.Mock()
    r.json.return_value = {
        "resources": [
            {"id": "1", "title": "elus-conseiller-municipal-cm.csv",
             "url": "https://static.data.gouv.fr/elus-conseiller-municipal-cm.csv"},
            {"id": "2", "title": "elus-maires-mai.csv",
             "url": "https://static.data.gouv.fr/elus-maires-mai.csv"},
        ]
    }
    return r


def _reponse_telechargement(contenu):
    r = mock.Mock()
    r.raise_for_status = mock.Mock()
    r.iter_content = mock.Mock(return_value=iter([contenu]))
    r.close = mock.Mock()
    return r


class TestMoissonnerElus(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.dossier = self._tmp.name

    def test_publiable_filtre_sur_la_commune(self):
        session = mock.Mock()
        session.get.side_effect = [_reponse_metadata(), _reponse_telechargement(_csv_rne())]
        resultat = elus.moissonner(
            "35120", _GEVEZE, dossier_sortie=self.dossier, session_http=session,
        )
        self.assertEqual(resultat.statut, StatutConnecteur.PUBLIABLE)
        with open(resultat.fichiers_filtres[0], encoding="utf-8") as f:
            lignes = list(csv.DictReader(f, delimiter=";"))
        self.assertEqual(len(lignes), 1)
        self.assertEqual(lignes[0]["Nom de l'élu"], "DUPONT")

    def test_metadonnees_sans_em_dash(self):
        session = mock.Mock()
        session.get.side_effect = [_reponse_metadata(), _reponse_telechargement(_csv_rne())]
        resultat = elus.moissonner(
            "35120", _GEVEZE, dossier_sortie=self.dossier, session_http=session,
        )
        self.assertNotIn("—", resultat.rudi_metadata["resource_title"])
        self.assertNotIn("—", resultat.rudi_metadata["synopsis"][0]["text"])
        self.assertNotIn("—", resultat.rudi_metadata["summary"][0]["text"])
        for media in resultat.rudi_metadata["available_formats"]:
            self.assertNotIn("—", media["media_caption"])

    def test_allowlist_exclut_colonnes_sensibles(self):
        session = mock.Mock()
        session.get.side_effect = [_reponse_metadata(), _reponse_telechargement(_csv_rne())]
        resultat = elus.moissonner(
            "35120", _GEVEZE, dossier_sortie=self.dossier, session_http=session,
        )
        with open(resultat.fichiers_filtres[0], encoding="utf-8") as f:
            entetes = next(csv.reader(f, delimiter=";"))
        for colonne_interdite in (
            "Date de naissance", "Code de la catégorie socio-professionnelle",
            "Libellé de la catégorie socio-professionnelle", "Code sexe",
            "Code nationalité", "Date de début de la fonction",
        ):
            self.assertNotIn(colonne_interdite, entetes)
        for colonne_attendue in ("Nom de l'élu", "Prénom de l'élu", "Libellé de la fonction",
                                  "Date de début du mandat"):
            self.assertIn(colonne_attendue, entetes)

    def test_vide_sans_elu(self):
        session = mock.Mock()
        autre_commune = [{**l, "Code de la commune": "99999"} for l in _LIGNES_RNE]
        session.get.side_effect = [_reponse_metadata(), _reponse_telechargement(_csv_rne(autre_commune))]
        resultat = elus.moissonner(
            "35120", _GEVEZE, dossier_sortie=self.dossier, session_http=session,
        )
        self.assertEqual(resultat.statut, StatutConnecteur.VIDE)

    def test_echec_metadonnees(self):
        session = mock.Mock()
        session.get.side_effect = RuntimeError("500")
        resultat = elus.moissonner(
            "35120", _GEVEZE, dossier_sortie=self.dossier, session_http=session,
        )
        self.assertEqual(resultat.statut, StatutConnecteur.ECHEC)


if __name__ == "__main__":
    unittest.main()
