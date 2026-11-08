"""Tests de datasets/elections.py — format large, blocs de liste dynamiques."""
import csv
import io
import json
import tempfile
import unittest
from unittest import mock

from rudi_commune_starterkit.datasets import elections
from rudi_commune_starterkit.resultat import StatutConnecteur

_GEVEZE = {"nom": "Gévezé", "code_insee": "35120"}

_ENTETES = (
    ["Code département", "Libellé département", "Code commune", "Libellé commune",
     "Inscrits", "Votants", "Abstentions", "Exprimés", "Blancs", "Nuls"]
    + [
        f"{prefixe} {i}"
        for i in (1, 2, 3)
        for prefixe in (
            "Numéro de panneau", "Nom candidat", "Prénom candidat", "Sexe candidat",
            "Nuance liste", "Libellé abrégé de liste", "Libellé de liste", "Voix",
            "% Voix/inscrits", "% Voix/exprimés", "Elu", "Sièges au CM", "Sièges au CC",
        )
    ]
)

_LIGNE_GEVEZE = {
    "Code département": "35", "Libellé département": "Ille-et-Vilaine",
    "Code commune": "35120", "Libellé commune": "Gévezé",
    "Inscrits": "4487", "Votants": "2896", "Abstentions": "1591", "Exprimés": "2828",
    "Blancs": "42", "Nuls": "26",
    "Numéro de panneau 1": "1", "Libellé de liste 1": "GEVEZE, L'AVENIR EN CONFIANCE",
    "Libellé abrégé de liste 1": "GEVEZE, L'AVENIR EN CONFIANCE", "Nuance liste 1": "LDVD",
    "Voix 1": "1361", "% Voix/exprimés 1": "48,13%", "Elu 1": "",
    "Sièges au CM 1": "6", "Sièges au CC 1": "0",
    "Numéro de panneau 2": "2", "Libellé de liste 2": "VIVRE ENSEMBLE A GEVEZE",
    "Libellé abrégé de liste 2": "VIVRE ENSEMBLE A GEVEZE", "Nuance liste 2": "LDVG",
    "Voix 2": "1467", "% Voix/exprimés 2": "51,87%", "Elu 2": "",
    "Sièges au CM 2": "22", "Sièges au CC 2": "2",
    # bloc 3 : vide (pas de 3e liste à Gévezé)
    "Numéro de panneau 3": "", "Libellé de liste 3": "", "Libellé abrégé de liste 3": "",
    "Nuance liste 3": "", "Voix 3": "", "% Voix/exprimés 3": "", "Elu 3": "",
    "Sièges au CM 3": "", "Sièges au CC 3": "",
}


def _csv_national(lignes):
    tampon = io.StringIO()
    writer = csv.DictWriter(tampon, fieldnames=_ENTETES, delimiter=";")
    writer.writeheader()
    for ligne in lignes:
        writer.writerow({champ: ligne.get(champ, "") for champ in _ENTETES})
    return tampon.getvalue().encode("utf-8")


def _reponse_metadata():
    r = mock.Mock()
    r.raise_for_status = mock.Mock()
    r.json.return_value = {
        "resources": [
            {"id": "1", "title": "Municipales 2026 - Résultats - Communes_2026-03-20.csv",
             "url": "https://static.data.gouv.fr/municipales-communes.csv"},
            {"id": "2",
             "title": "Municipales Polynésie française 2026 - Résultats - Communes_2026-03-20.csv",
             "url": "https://static.data.gouv.fr/polynesie-communes.csv"},
        ]
    }
    return r


def _reponse_telechargement(contenu):
    r = mock.Mock()
    r.raise_for_status = mock.Mock()
    r.iter_content = mock.Mock(return_value=iter([contenu]))
    r.close = mock.Mock()
    return r


class TestMoissonnerElections(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.dossier = self._tmp.name

    def test_publiable_deux_listes(self):
        session = mock.Mock()
        session.get.side_effect = [
            _reponse_metadata(), _reponse_telechargement(_csv_national([_LIGNE_GEVEZE])),
        ]
        resultat = elections.moissonner(
            "35120", _GEVEZE, dossier_sortie=self.dossier, session_http=session,
        )
        self.assertEqual(resultat.statut, StatutConnecteur.PUBLIABLE)
        with open(resultat.fichiers_filtres[0], encoding="utf-8") as f:
            donnees = json.load(f)
        self.assertEqual(len(donnees["listes"]), 2)
        self.assertEqual(donnees["totaux"]["Inscrits"], "4487")
        noms = {l["libelle_liste"] for l in donnees["listes"]}
        self.assertEqual(noms, {"GEVEZE, L'AVENIR EN CONFIANCE", "VIVRE ENSEMBLE A GEVEZE"})

    def test_metadonnees_sans_em_dash(self):
        session = mock.Mock()
        session.get.side_effect = [
            _reponse_metadata(), _reponse_telechargement(_csv_national([_LIGNE_GEVEZE])),
        ]
        resultat = elections.moissonner(
            "35120", _GEVEZE, dossier_sortie=self.dossier, session_http=session,
        )
        self.assertNotIn("—", resultat.rudi_metadata["resource_title"])
        self.assertNotIn("—", resultat.rudi_metadata["synopsis"][0]["text"])
        self.assertNotIn("—", resultat.rudi_metadata["summary"][0]["text"])
        for media in resultat.rudi_metadata["available_formats"]:
            self.assertNotIn("—", media["media_caption"])

    def test_bloc_vide_ignore(self):
        session = mock.Mock()
        session.get.side_effect = [
            _reponse_metadata(), _reponse_telechargement(_csv_national([_LIGNE_GEVEZE])),
        ]
        resultat = elections.moissonner(
            "35120", _GEVEZE, dossier_sortie=self.dossier, session_http=session,
        )
        with open(resultat.fichiers_filtres[0], encoding="utf-8") as f:
            donnees = json.load(f)
        for liste in donnees["listes"]:
            self.assertTrue(liste["libelle_liste"])

    def test_vide_sans_ligne_pour_la_commune(self):
        session = mock.Mock()
        autre = {**_LIGNE_GEVEZE, "Code commune": "99999"}
        session.get.side_effect = [_reponse_metadata(), _reponse_telechargement(_csv_national([autre]))]
        resultat = elections.moissonner(
            "35120", _GEVEZE, dossier_sortie=self.dossier, session_http=session,
        )
        self.assertEqual(resultat.statut, StatutConnecteur.VIDE)

    def test_echec_metadonnees(self):
        session = mock.Mock()
        session.get.side_effect = RuntimeError("500")
        resultat = elections.moissonner(
            "35120", _GEVEZE, dossier_sortie=self.dossier, session_http=session,
        )
        self.assertEqual(resultat.statut, StatutConnecteur.ECHEC)


if __name__ == "__main__":
    unittest.main()
