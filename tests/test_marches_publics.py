"""Tests de datasets/marches_publics.py — source DECP remplacée (Colin Maudry, v3
Axe 4) : résolution SIREN, téléchargement intégral du CSV.gz, filtrage local en flux
préfixé sur acheteur_id (SIRET).

``telecharger()`` est mocké (pas seulement ``session.get``) : le cache DECP est
partagé à la racine du projet (``DOSSIER_CACHE_DECP``), pas nested dans
``dossier_sortie`` comme les autres modules — laisser le vrai ``telecharger()``
s'exécuter écrirait un fichier réel hors du répertoire temporaire de test.
"""
import csv as csv_module
import os
import tempfile
import unittest
from unittest import mock

from rudi_commune_starterkit import licences
from rudi_commune_starterkit.datasets import marches_publics
from rudi_commune_starterkit.resultat import StatutConnecteur

_GEVEZE = {"nom": "Gévezé", "code_insee": "35120"}
_SIREN = "213501208"

_ENTETE_DECP = "uid;id;nature;acheteur_id;objet;montant\n"


def _reponse_siren(siren=_SIREN):
    r = mock.Mock()
    r.raise_for_status = mock.Mock()
    r.json.return_value = {"results": [{"siren": siren}], "total_results": 1}
    return r


def _reponse_metadata(
    license="lov2", last_modified="2026-11-09T13:58:30.789000+00:00", contact_points=None,
):
    r = mock.Mock()
    r.raise_for_status = mock.Mock()
    r.json.return_value = {
        "license": license,
        "page": "https://www.data.gouv.fr/datasets/donnees-essentielles-de-la-commande-publique-consolidees-format-tabulaire",
        "contact_points": contact_points or [],
        "resources": [
            {"id": "a", "title": "decp.parquet", "format": "parquet",
             "url": "https://static.data.gouv.fr/decp.parquet"},
            {"id": "b", "title": "decp.csv.gz", "format": "csv.gz",
             "url": "https://static.data.gouv.fr/decp.csv.gz",
             "last_modified": last_modified},
        ],
    }
    return r


def _ligne_decp(i, acheteur):
    return f"u{i};{i};marché;{acheteur};objet {i};1000\n"


class TestMoissonnerMarchesPublics(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.dossier = os.path.join(self._tmp.name, "sortie")

    def _ecrire_decp_cache(self, lignes_acheteur):
        chemin = os.path.join(self._tmp.name, "decp_cache.csv")
        with open(chemin, "w", encoding="utf-8") as f:
            f.write(_ENTETE_DECP)
            for i, acheteur in enumerate(lignes_acheteur):
                f.write(_ligne_decp(i, acheteur))
        return chemin

    def _patch_telecharger(self, chemin_cache):
        return mock.patch(
            "rudi_commune_starterkit.datasets.marches_publics.telecharger",
            return_value=chemin_cache,
        )

    def test_publiable_filtre_sur_le_siren_en_prefixe(self):
        chemin_cache = self._ecrire_decp_cache([f"{_SIREN}00019", "99999999900019"])
        session = mock.Mock()
        session.get.side_effect = [_reponse_siren(), _reponse_metadata()]
        with self._patch_telecharger(chemin_cache):
            resultat = marches_publics.moissonner(
                "35120", _GEVEZE, dossier_sortie=self.dossier, session_http=session,
            )
        self.assertEqual(resultat.statut, StatutConnecteur.PUBLIABLE)
        with open(resultat.fichiers_filtres[0], encoding="utf-8") as f:
            lignes = list(csv_module.DictReader(f, delimiter=";"))
        self.assertEqual(len(lignes), 1)
        self.assertEqual(lignes[0]["acheteur_id"], f"{_SIREN}00019")

    def test_filtrer_csv_appele_avec_prefixe_true_sur_le_siren(self):
        chemin_cache = self._ecrire_decp_cache([f"{_SIREN}00019"])
        session = mock.Mock()
        session.get.side_effect = [_reponse_siren(), _reponse_metadata()]
        with self._patch_telecharger(chemin_cache), mock.patch(
            "rudi_commune_starterkit.datasets.marches_publics.filtrer_csv",
            wraps=marches_publics.filtrer_csv,
        ) as mock_filtrer_csv:
            marches_publics.moissonner(
                "35120", _GEVEZE, dossier_sortie=self.dossier, session_http=session,
            )
        mock_filtrer_csv.assert_called_once()
        appel = mock_filtrer_csv.call_args
        self.assertEqual(appel.args[1], "acheteur_id")
        self.assertEqual(appel.args[2], _SIREN)
        self.assertTrue(appel.kwargs["prefixe"])

    def test_metadonnees_sans_em_dash(self):
        chemin_cache = self._ecrire_decp_cache([f"{_SIREN}00019"])
        session = mock.Mock()
        session.get.side_effect = [_reponse_siren(), _reponse_metadata()]
        with self._patch_telecharger(chemin_cache):
            resultat = marches_publics.moissonner(
                "35120", _GEVEZE, dossier_sortie=self.dossier, session_http=session,
            )
        self.assertNotIn("—", resultat.rudi_metadata["resource_title"])
        self.assertNotIn("—", resultat.rudi_metadata["synopsis"][0]["text"])
        self.assertNotIn("—", resultat.rudi_metadata["summary"][0]["text"])
        for media in resultat.rudi_metadata["available_formats"]:
            self.assertNotIn("—", media["media_caption"])

    def test_licence_dynamique_depuis_datagouv(self):
        chemin_cache = self._ecrire_decp_cache([f"{_SIREN}00019"])
        session = mock.Mock()
        session.get.side_effect = [_reponse_siren(), _reponse_metadata(license="lov2")]
        with self._patch_telecharger(chemin_cache):
            resultat = marches_publics.moissonner(
                "35120", _GEVEZE, dossier_sortie=self.dossier, session_http=session,
            )
        self.assertEqual(
            resultat.rudi_metadata["access_condition"]["licence"]["licence_label"], "etalab-2.0",
        )

    def test_licence_absente_retombe_sur_la_table_curee(self):
        chemin_cache = self._ecrire_decp_cache([f"{_SIREN}00019"])
        session = mock.Mock()
        session.get.side_effect = [_reponse_siren(), _reponse_metadata(license=None)]
        with self._patch_telecharger(chemin_cache):
            resultat = marches_publics.moissonner(
                "35120", _GEVEZE, dossier_sortie=self.dossier, session_http=session,
            )
        self.assertEqual(resultat.statut, StatutConnecteur.PUBLIABLE)

    def test_licence_inconnue_est_un_echec_isole(self):
        chemin_cache = self._ecrire_decp_cache([f"{_SIREN}00019"])
        session = mock.Mock()
        session.get.side_effect = [_reponse_siren(), _reponse_metadata(license=None)]
        table_sans_marches = {
            k: v for k, v in licences.LICENCES_CUREES.items() if k != marches_publics.CLE
        }
        with self._patch_telecharger(chemin_cache), \
                mock.patch.object(licences, "LICENCES_CUREES", table_sans_marches):
            resultat = marches_publics.moissonner(
                "35120", _GEVEZE, dossier_sortie=self.dossier, session_http=session,
            )
        self.assertEqual(resultat.statut, StatutConnecteur.ECHEC)

    def test_vide_sans_marche_pour_le_siren(self):
        chemin_cache = self._ecrire_decp_cache(["99999999900019"])
        session = mock.Mock()
        session.get.side_effect = [_reponse_siren(), _reponse_metadata()]
        with self._patch_telecharger(chemin_cache):
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

    def test_echec_telechargement_decp(self):
        session = mock.Mock()
        session.get.side_effect = [_reponse_siren(), RuntimeError("500")]
        resultat = marches_publics.moissonner(
            "35120", _GEVEZE, dossier_sortie=self.dossier, session_http=session,
        )
        self.assertEqual(resultat.statut, StatutConnecteur.ECHEC)

    def test_contact_dynamique_contact_points_priorite_sur_la_source_generique(self):
        # v3, Axe 2 : contact réel confirmé sur ce dataset (Colin Maudry via
        # contact_points) — priorité absolue sur le repli générique du producteur
        # (Ministère de l'Économie et des Finances).
        chemin_cache = self._ecrire_decp_cache([f"{_SIREN}00019"])
        session = mock.Mock()
        session.get.side_effect = [
            _reponse_siren(),
            _reponse_metadata(contact_points=[
                {"name": "Colin Maudry", "email": "colin@colmo.tech", "role": "creator"},
            ]),
        ]
        with self._patch_telecharger(chemin_cache):
            resultat = marches_publics.moissonner(
                "35120", _GEVEZE, dossier_sortie=self.dossier, session_http=session,
            )
        self.assertEqual(
            resultat.rudi_metadata["contacts"][0],
            {"contact_name": "Colin Maudry", "email": "colin@colmo.tech", "role": "creator"},
        )

    def test_sans_contact_points_retombe_sur_le_repli_generique(self):
        chemin_cache = self._ecrire_decp_cache([f"{_SIREN}00019"])
        session = mock.Mock()
        session.get.side_effect = [_reponse_siren(), _reponse_metadata(contact_points=[])]
        with self._patch_telecharger(chemin_cache):
            resultat = marches_publics.moissonner(
                "35120", _GEVEZE, dossier_sortie=self.dossier, session_http=session,
            )
        self.assertEqual(
            resultat.rudi_metadata["contacts"][0]["contact_name"],
            "Ministère de l'Économie et des Finances",
        )

    def test_avertissement_source_figee(self):
        chemin_cache = self._ecrire_decp_cache([f"{_SIREN}00019"])
        session = mock.Mock()
        session.get.side_effect = [
            _reponse_siren(), _reponse_metadata(last_modified="2020-01-01T00:00:00Z"),
        ]
        with self._patch_telecharger(chemin_cache), mock.patch("builtins.print") as mock_print:
            marches_publics.moissonner(
                "35120", _GEVEZE, dossier_sortie=self.dossier, session_http=session,
            )
        messages = " ".join(str(appel) for appel in mock_print.call_args_list)
        self.assertIn("figée", messages)


if __name__ == "__main__":
    unittest.main()
