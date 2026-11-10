"""Tests de datasets/entreprises.py — statuts, alignement média/fichier, modes producer."""
import csv
import os
import tempfile
import unittest
from unittest import mock

from rudi_commune_starterkit.datasets import entreprises
from rudi_commune_starterkit.resultat import StatutConnecteur

_GEVEZE = {"nom": "Gévezé", "code_insee": "35120"}
_RESULTAT = {
    "siren": "775685506", "nom_complet": "ENTREPRISE TEST", "etat_administratif": "A",
    "matching_etablissements": [{"siret": "77568550600010", "adresse": "1 RUE X"}],
}


def _reponse_page(resultats):
    r = mock.Mock()
    r.raise_for_status = mock.Mock()
    r.json.return_value = {"results": resultats, "page": 1, "total_pages": 1}
    return r


class TestMoissonnerEntreprises(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.dossier = self._tmp.name

    def test_publiable_ecrit_un_fichier_csv_et_un_media_aligne(self):
        session = mock.Mock()
        session.get.return_value = _reponse_page([_RESULTAT])

        resultat = entreprises.moissonner(
            "35120", _GEVEZE, dossier_sortie=self.dossier, session_http=session,
        )

        self.assertEqual(resultat.statut, StatutConnecteur.PUBLIABLE)
        licence = resultat.rudi_metadata["access_condition"]["licence"]
        self.assertEqual(licence["licence_type"], "CUSTOM")
        self.assertEqual(len(resultat.fichiers_filtres), 1)
        self.assertTrue(os.path.isfile(resultat.fichiers_filtres[0]))
        with open(resultat.fichiers_filtres[0], encoding="utf-8", newline="") as f:
            lignes = list(csv.DictReader(f, delimiter=";"))
        self.assertEqual(lignes[0]["siren"], "775685506")
        self.assertEqual(lignes[0]["etablissement_siret"], "77568550600010")

        medias = resultat.rudi_metadata["available_formats"]
        self.assertEqual(medias[0]["media_type"], "FILE")
        self.assertEqual(
            medias[0]["media_name"], os.path.basename(resultat.fichiers_filtres[0])
        )

    def test_vide_sans_fichier_ni_media(self):
        session = mock.Mock()
        session.get.return_value = _reponse_page([])
        resultat = entreprises.moissonner(
            "35120", _GEVEZE, dossier_sortie=self.dossier, session_http=session,
        )
        self.assertEqual(resultat.statut, StatutConnecteur.VIDE)
        self.assertEqual(os.listdir(self.dossier), [])

    def test_echec_reseau(self):
        session = mock.Mock()
        session.get.side_effect = RuntimeError("DNS")
        resultat = entreprises.moissonner(
            "35120", _GEVEZE, dossier_sortie=self.dossier, session_http=session,
        )
        self.assertEqual(resultat.statut, StatutConnecteur.ECHEC)
        self.assertIn("DNS", resultat.message)

    def test_mode_source_producer_insee(self):
        session = mock.Mock()
        session.get.return_value = _reponse_page([_RESULTAT])
        resultat = entreprises.moissonner(
            "35120", _GEVEZE, dossier_sortie=self.dossier, mode_producer="source",
            session_http=session,
        )
        self.assertEqual(resultat.rudi_metadata["producer"]["organization_name"], "INSEE")
        self.assertEqual(
            resultat.rudi_metadata["contacts"],
            [{"contact_name": "Support APIM", "email": "support-apim@insee.fr"}],
        )

    def test_mode_commune_producer_et_contact(self):
        session = mock.Mock()
        session.get.return_value = _reponse_page([_RESULTAT])
        resultat = entreprises.moissonner(
            "35120", _GEVEZE, dossier_sortie=self.dossier, mode_producer="commune",
            contact_email_commune="mairie@geveze.fr", session_http=session,
        )
        self.assertEqual(
            resultat.rudi_metadata["producer"]["organization_name"], "Commune de Gévezé"
        )
        self.assertEqual(
            resultat.rudi_metadata["contacts"],
            [
                {"contact_name": "Commune de Gévezé", "email": "mairie@geveze.fr"},
                {"contact_name": "Support APIM", "email": "support-apim@insee.fr"},
            ],
        )

    def test_titre_contient_commune_et_code_insee(self):
        session = mock.Mock()
        session.get.return_value = _reponse_page([_RESULTAT])
        resultat = entreprises.moissonner(
            "35120", _GEVEZE, dossier_sortie=self.dossier, session_http=session,
        )
        self.assertIn("Gévezé", resultat.rudi_metadata["resource_title"])
        self.assertIn("35120", resultat.rudi_metadata["resource_title"])

    def test_local_id_stable_entre_deux_appels(self):
        session = mock.Mock()
        session.get.return_value = _reponse_page([_RESULTAT])
        r1 = entreprises.moissonner("35120", _GEVEZE, dossier_sortie=self.dossier, session_http=session)
        r2 = entreprises.moissonner("35120", _GEVEZE, dossier_sortie=self.dossier, session_http=session)
        self.assertEqual(r1.rudi_metadata["local_id"], r2.rudi_metadata["local_id"])

    def test_filtre_etat_administratif_actif_transmis(self):
        session = mock.Mock()
        session.get.return_value = _reponse_page([_RESULTAT])
        entreprises.moissonner("35120", _GEVEZE, dossier_sortie=self.dossier, session_http=session)
        _, kwargs = session.get.call_args
        self.assertEqual(kwargs["params"]["etat_administratif"], "A")
        self.assertNotIn("nature_juridique", kwargs["params"])

    def test_description_riche_mise_en_page_et_contenu_metier(self):
        session = mock.Mock()
        session.get.return_value = _reponse_page([_RESULTAT])
        resultat = entreprises.moissonner(
            "35120", _GEVEZE, dossier_sortie=self.dossier, session_http=session,
        )
        html = resultat.rudi_metadata["summary"][0]["html"]
        self.assertIn("<ul>", html)
        self.assertIn("</a>", html)
        self.assertIn("SIRENE", html)
        self.assertIn("établissements", resultat.rudi_metadata["keywords"])


if __name__ == "__main__":
    unittest.main()
