"""Tests de datasets/irve.py — FILE hybride, filtre combiné nom+code_insee."""
import tempfile
import unittest
from unittest import mock

from rudi_commune_starterkit.datasets import irve
from rudi_commune_starterkit.resultat import StatutConnecteur

_GEVEZE = {"nom": "Gévezé", "code_insee": "35120"}


def _reponse_records(total_count, last_modified="2026-07-21T08:03:43+00:00"):
    r = mock.Mock()
    r.raise_for_status = mock.Mock()
    corps = {"total_count": total_count}
    if total_count:
        corps["results"] = [{"last_modified": last_modified}]
    r.json.return_value = corps
    return r


def _reponse_streaming(contenu=b"id;nom\n1;Carrefour\n"):
    r = mock.Mock()
    r.raise_for_status = mock.Mock()
    r.headers = {}
    r.iter_content = mock.Mock(return_value=iter([contenu]))
    r.close = mock.Mock()
    return r


_CSV_AVEC_COORDONNEES = (
    b"nom_station;nom_operateur;nbre_pdc;puissance_nominale;"
    b"consolidated_longitude;consolidated_latitude\n"
    b"Mairie;Operateur X;2;22;-1.788383609;48.220806213\n"
)


class TestMoissonnerIrve(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.dossier = self._tmp.name

    def test_publiable_sans_fichier_local(self):
        session = mock.Mock()
        session.get.side_effect = [_reponse_records(4), _reponse_streaming(), _reponse_streaming()]
        resultat = irve.moissonner(
            "35120", _GEVEZE, dossier_sortie=self.dossier, session_http=session,
        )
        self.assertEqual(resultat.statut, StatutConnecteur.PUBLIABLE)
        licence = resultat.rudi_metadata["access_condition"]["licence"]
        self.assertEqual(licence["licence_type"], "STANDARD")
        self.assertEqual(licence["licence_label"], "etalab-2.0")
        self.assertEqual(resultat.fichiers_filtres, [])

    def test_metadonnees_sans_em_dash(self):
        session = mock.Mock()
        session.get.side_effect = [_reponse_records(4), _reponse_streaming(), _reponse_streaming()]
        resultat = irve.moissonner(
            "35120", _GEVEZE, dossier_sortie=self.dossier, session_http=session,
        )
        self.assertNotIn("—", resultat.rudi_metadata["resource_title"])
        self.assertNotIn("—", resultat.rudi_metadata["synopsis"][0]["text"])
        self.assertNotIn("—", resultat.rudi_metadata["summary"][0]["text"])
        for media in resultat.rudi_metadata["available_formats"]:
            self.assertNotIn("—", media["media_caption"])

    def test_geojson_construit_depuis_consolidated_lon_lat(self):
        session = mock.Mock()
        session.get.side_effect = [
            _reponse_records(4), _reponse_streaming(), _reponse_streaming(_CSV_AVEC_COORDONNEES),
        ]
        resultat = irve.moissonner(
            "35120", _GEVEZE, dossier_sortie=self.dossier, session_http=session,
        )
        medias = resultat.rudi_metadata["available_formats"]
        medias_geojson = [m for m in medias if m["media_name"].endswith(".geojson")]
        self.assertEqual(len(medias_geojson), 1)
        self.assertEqual(len(resultat.fichiers_filtres), 1)
        self.assertTrue(resultat.fichiers_filtres[0].endswith(".geojson"))

    def test_media_geojson_precede_le_media_csv_hybride_dans_available_formats(self):
        # Garde-fou valider_alignement_medias() : le média réellement à uploader
        # (GeoJSON) doit précéder le média hybride déjà complet (CSV), jamais l'inverse.
        session = mock.Mock()
        session.get.side_effect = [
            _reponse_records(4), _reponse_streaming(), _reponse_streaming(_CSV_AVEC_COORDONNEES),
        ]
        resultat = irve.moissonner(
            "35120", _GEVEZE, dossier_sortie=self.dossier, session_http=session,
        )
        medias_file = [
            m for m in resultat.rudi_metadata["available_formats"] if m["media_type"] == "FILE"
        ]
        self.assertTrue(medias_file[0]["media_name"].endswith(".geojson"))
        self.assertTrue(medias_file[1]["media_name"].endswith(".csv"))

    def test_date_source_derivee_du_max_last_modified(self):
        session = mock.Mock()
        session.get.side_effect = [_reponse_records(4), _reponse_streaming(), _reponse_streaming()]
        resultat = irve.moissonner(
            "35120", _GEVEZE, dossier_sortie=self.dossier, session_http=session,
        )
        self.assertEqual(resultat.rudi_metadata["dataset_dates"]["updated"], "2026-07-21T08:03:43Z")

    def test_requete_triee_par_last_modified_desc(self):
        session = mock.Mock()
        session.get.side_effect = [_reponse_records(4), _reponse_streaming(), _reponse_streaming()]
        irve.moissonner("35120", _GEVEZE, dossier_sortie=self.dossier, session_http=session)
        premier_appel = session.get.call_args_list[0]
        self.assertEqual(premier_appel.kwargs["params"]["order_by"], "last_modified desc")

    def test_where_combine_nom_et_code_insee(self):
        session = mock.Mock()
        session.get.side_effect = [_reponse_records(4), _reponse_streaming(), _reponse_streaming()]
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

    def test_description_riche_mise_en_page_et_contenu_metier(self):
        session = mock.Mock()
        session.get.side_effect = [_reponse_records(4), _reponse_streaming(), _reponse_streaming()]
        resultat = irve.moissonner(
            "35120", _GEVEZE, dossier_sortie=self.dossier, session_http=session,
        )
        html = resultat.rudi_metadata["summary"][0]["html"]
        self.assertIn("<ul>", html)
        self.assertIn("</a>", html)
        self.assertIn("consolidated_commune", html)
        self.assertIn("mobilité électrique", resultat.rudi_metadata["keywords"])


if __name__ == "__main__":
    unittest.main()
