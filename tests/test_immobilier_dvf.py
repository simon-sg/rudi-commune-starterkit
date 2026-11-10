"""Tests de datasets/immobilier_dvf.py — sondage HEAD par année, union de schéma."""
import csv
import datetime
import io
import tempfile
import unittest
from unittest import mock

from rudi_commune_starterkit.datasets import immobilier_dvf
from rudi_commune_starterkit.resultat import StatutConnecteur

_GEVEZE = {"nom": "Gévezé", "code_insee": "35120", "code_departement": "35"}
_ANNEE_COURANTE = datetime.date.today().year


def _csv_dvf(lignes, entetes):
    tampon = io.StringIO()
    writer = csv.DictWriter(tampon, fieldnames=entetes)
    writer.writeheader()
    writer.writerows(lignes)
    return tampon.getvalue().encode("utf-8")


def _tete(status_code):
    r = mock.Mock()
    r.status_code = status_code
    r.raise_for_status = mock.Mock()
    if status_code >= 400:
        r.raise_for_status.side_effect = Exception(f"HTTP {status_code}")
    return r


def _reponse_telechargement(contenu):
    r = mock.Mock()
    r.raise_for_status = mock.Mock()
    r.iter_content = mock.Mock(return_value=iter([contenu]))
    r.close = mock.Mock()
    return r


_ENTETES_2024 = ["id_mutation", "date_mutation", "code_commune", "nom_commune", "valeur_fonciere"]
_LIGNE_2024 = {"id_mutation": "1", "date_mutation": "2024-05-01", "code_commune": "35120",
               "nom_commune": "Gévezé", "valeur_fonciere": "150000"}


class TestMoissonnerImmobilierDvf(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.dossier = self._tmp.name

    def test_publiable_une_annee_disponible(self):
        session = mock.Mock()
        # NB_ANNEES_A_SONDER=6 : toutes 404 sauf la 1ère tentée (année courante - 1).
        session.head.side_effect = [_tete(200)] + [_tete(404)] * 5
        session.get.side_effect = [_reponse_telechargement(_csv_dvf([_LIGNE_2024], _ENTETES_2024))]
        resultat = immobilier_dvf.moissonner(
            "35120", _GEVEZE, dossier_sortie=self.dossier, session_http=session,
        )
        self.assertEqual(resultat.statut, StatutConnecteur.PUBLIABLE)
        licence = resultat.rudi_metadata["access_condition"]["licence"]
        self.assertEqual(licence["licence_type"], "STANDARD")
        self.assertEqual(licence["licence_label"], "etalab-2.0")
        with open(resultat.fichiers_filtres[0], encoding="utf-8") as f:
            lignes = list(csv.DictReader(f))
        self.assertEqual(len(lignes), 1)
        self.assertEqual(lignes[0]["annee_millesime_dvf"], str(_ANNEE_COURANTE - 1))

    def test_metadonnees_sans_em_dash(self):
        session = mock.Mock()
        session.head.side_effect = [_tete(200)] + [_tete(404)] * 5
        session.get.side_effect = [_reponse_telechargement(_csv_dvf([_LIGNE_2024], _ENTETES_2024))]
        resultat = immobilier_dvf.moissonner(
            "35120", _GEVEZE, dossier_sortie=self.dossier, session_http=session,
        )
        self.assertNotIn("—", resultat.rudi_metadata["resource_title"])
        self.assertNotIn("—", resultat.rudi_metadata["synopsis"][0]["text"])
        self.assertNotIn("—", resultat.rudi_metadata["summary"][0]["text"])
        for media in resultat.rudi_metadata["available_formats"]:
            self.assertNotIn("—", media["media_caption"])

    def test_concatene_plusieurs_annees(self):
        session = mock.Mock()
        ligne_2 = {**_LIGNE_2024, "id_mutation": "2", "date_mutation": "2023-01-01"}
        session.head.side_effect = [_tete(200), _tete(200)] + [_tete(404)] * 4
        session.get.side_effect = [
            _reponse_telechargement(_csv_dvf([_LIGNE_2024], _ENTETES_2024)),
            _reponse_telechargement(_csv_dvf([ligne_2], _ENTETES_2024)),
        ]
        resultat = immobilier_dvf.moissonner(
            "35120", _GEVEZE, dossier_sortie=self.dossier, session_http=session,
        )
        self.assertEqual(resultat.statut, StatutConnecteur.PUBLIABLE)
        with open(resultat.fichiers_filtres[0], encoding="utf-8") as f:
            lignes = list(csv.DictReader(f))
        self.assertEqual(len(lignes), 2)

    def test_union_schema_colonne_absente_laissee_vide(self):
        session = mock.Mock()
        entetes_annee_2 = _ENTETES_2024 + ["nouvelle_colonne"]
        ligne_2 = {**_LIGNE_2024, "id_mutation": "2", "nouvelle_colonne": "X"}
        session.head.side_effect = [_tete(200), _tete(200)] + [_tete(404)] * 4
        session.get.side_effect = [
            _reponse_telechargement(_csv_dvf([_LIGNE_2024], _ENTETES_2024)),
            _reponse_telechargement(_csv_dvf([ligne_2], entetes_annee_2)),
        ]
        resultat = immobilier_dvf.moissonner(
            "35120", _GEVEZE, dossier_sortie=self.dossier, session_http=session,
        )
        with open(resultat.fichiers_filtres[0], encoding="utf-8") as f:
            lecteur = csv.DictReader(f)
            self.assertIn("nouvelle_colonne", lecteur.fieldnames)
            lignes = list(lecteur)
        self.assertEqual(lignes[0]["nouvelle_colonne"], "")
        self.assertEqual(lignes[1]["nouvelle_colonne"], "X")

    def test_vide_sans_aucun_millesime_disponible(self):
        session = mock.Mock()
        session.head.side_effect = [_tete(404)] * 6
        resultat = immobilier_dvf.moissonner(
            "35120", _GEVEZE, dossier_sortie=self.dossier, session_http=session,
        )
        self.assertEqual(resultat.statut, StatutConnecteur.VIDE)

    def test_vide_millesimes_disponibles_mais_commune_absente(self):
        session = mock.Mock()
        autre = {**_LIGNE_2024, "code_commune": "99999"}
        session.head.side_effect = [_tete(200)] + [_tete(404)] * 5
        session.get.side_effect = [_reponse_telechargement(_csv_dvf([autre], _ENTETES_2024))]
        resultat = immobilier_dvf.moissonner(
            "35120", _GEVEZE, dossier_sortie=self.dossier, session_http=session,
        )
        self.assertEqual(resultat.statut, StatutConnecteur.VIDE)

    def test_echec_reseau_sur_head(self):
        session = mock.Mock()
        session.head.side_effect = RuntimeError("DNS")
        resultat = immobilier_dvf.moissonner(
            "35120", _GEVEZE, dossier_sortie=self.dossier, session_http=session,
        )
        self.assertEqual(resultat.statut, StatutConnecteur.ECHEC)

    def test_echec_serveur_distinct_du_404(self):
        session = mock.Mock()
        session.head.side_effect = [_tete(500)]
        resultat = immobilier_dvf.moissonner(
            "35120", _GEVEZE, dossier_sortie=self.dossier, session_http=session,
        )
        self.assertEqual(resultat.statut, StatutConnecteur.ECHEC)


if __name__ == "__main__":
    unittest.main()
