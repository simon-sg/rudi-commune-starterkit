"""Tests de datasets/etablissements_scolaires.py — FILE hybride (CSV), GeoJSON déposé
sur le nœud (jamais hybride, voir le docstring du module), filtre code_commune."""
import tempfile
import unittest
from unittest import mock

from rudi_commune_starterkit.datasets import etablissements_scolaires
from rudi_commune_starterkit.resultat import StatutConnecteur

_GEVEZE = {"nom": "Gévezé", "code_insee": "35120"}


def _reponse_records(total_count):
    r = mock.Mock()
    r.raise_for_status = mock.Mock()
    r.json.return_value = {"total_count": total_count}
    return r


def _reponse_streaming(contenu=b"id;nom\n0350266Z;Ecole\n"):
    r = mock.Mock()
    r.raise_for_status = mock.Mock()
    r.headers = {}
    r.iter_content = mock.Mock(return_value=iter([contenu]))
    r.close = mock.Mock()
    return r


_CSV_AVEC_COORDONNEES = (
    b"nom_etablissement;type_etablissement;statut_public_prive;longitude;latitude\n"
    b"Ecole Leonard de Vinci;Ecole;Public;-1.791200372;48.219343653\n"
)


def _reponse_dataset_meta(modified="2026-11-10T06:01:21.851000+00:00"):
    r = mock.Mock()
    r.raise_for_status = mock.Mock()
    r.json.return_value = {"metas": {"default": {"modified": modified}}}
    return r


class TestMoissonnerEtablissementsScolaires(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.dossier = self._tmp.name

    def test_publiable_sans_fichier_local(self):
        session = mock.Mock()
        session.get.side_effect = [_reponse_records(3), _reponse_streaming(), _reponse_streaming(), _reponse_dataset_meta()]
        resultat = etablissements_scolaires.moissonner(
            "35120", _GEVEZE, dossier_sortie=self.dossier, session_http=session,
        )
        self.assertEqual(resultat.statut, StatutConnecteur.PUBLIABLE)
        licence = resultat.rudi_metadata["access_condition"]["licence"]
        self.assertEqual(licence["licence_type"], "STANDARD")
        self.assertEqual(licence["licence_label"], "etalab-2.0")
        self.assertEqual(resultat.fichiers_filtres, [])

    def test_metadonnees_sans_em_dash(self):
        session = mock.Mock()
        session.get.side_effect = [_reponse_records(3), _reponse_streaming(), _reponse_streaming(), _reponse_dataset_meta()]
        resultat = etablissements_scolaires.moissonner(
            "35120", _GEVEZE, dossier_sortie=self.dossier, session_http=session,
        )
        self.assertNotIn("—", resultat.rudi_metadata["resource_title"])
        self.assertNotIn("—", resultat.rudi_metadata["synopsis"][0]["text"])
        self.assertNotIn("—", resultat.rudi_metadata["summary"][0]["text"])
        for media in resultat.rudi_metadata["available_formats"]:
            self.assertNotIn("—", media["media_caption"])

    def test_where_utilise_code_commune_exact(self):
        session = mock.Mock()
        session.get.side_effect = [_reponse_records(3), _reponse_streaming(), _reponse_streaming(), _reponse_dataset_meta()]
        etablissements_scolaires.moissonner(
            "35120", _GEVEZE, dossier_sortie=self.dossier, session_http=session,
        )
        premier_appel = session.get.call_args_list[0]
        self.assertEqual(premier_appel.kwargs["params"]["where"], "code_commune='35120'")

    def test_geojson_construit_depuis_longitude_latitude_et_depose_sur_le_noeud(self):
        session = mock.Mock()
        session.get.side_effect = [
            _reponse_records(3), _reponse_streaming(),
            _reponse_streaming(_CSV_AVEC_COORDONNEES), _reponse_dataset_meta(),
        ]
        resultat = etablissements_scolaires.moissonner(
            "35120", _GEVEZE, dossier_sortie=self.dossier, session_http=session,
        )
        medias = resultat.rudi_metadata["available_formats"]
        medias_geojson = [m for m in medias if m["media_name"].endswith(".geojson")]
        self.assertEqual(len(medias_geojson), 1)
        self.assertEqual(medias_geojson[0]["media_type"], "FILE")
        self.assertIn("GeoJSON", medias_geojson[0]["media_caption"])
        # Jamais hybride : contrairement au CSV, pas d'URL externe dans le connecteur —
        # le fichier est réellement déposé sur le nœud (voir le docstring du module,
        # correctif du bug d'apigateway constaté sur un nœud tiers le 2026-11-14).
        self.assertNotIn("data.education.gouv.fr", medias_geojson[0]["connector"]["url"])
        self.assertEqual(len(resultat.fichiers_filtres), 1)
        self.assertTrue(resultat.fichiers_filtres[0].endswith(".geojson"))

    def test_media_geojson_precede_le_media_csv_hybride_dans_available_formats(self):
        # Garde-fou valider_alignement_medias() : le média réellement à uploader
        # (GeoJSON) doit précéder le média hybride déjà complet (CSV), jamais l'inverse.
        session = mock.Mock()
        session.get.side_effect = [
            _reponse_records(3), _reponse_streaming(),
            _reponse_streaming(_CSV_AVEC_COORDONNEES), _reponse_dataset_meta(),
        ]
        resultat = etablissements_scolaires.moissonner(
            "35120", _GEVEZE, dossier_sortie=self.dossier, session_http=session,
        )
        medias_file = [
            m for m in resultat.rudi_metadata["available_formats"] if m["media_type"] == "FILE"
        ]
        self.assertTrue(medias_file[0]["media_name"].endswith(".geojson"))
        self.assertTrue(medias_file[1]["media_name"].endswith(".csv"))

    def test_sans_coordonnees_exploitables_pas_de_media_geojson(self):
        # Contenu CSV par défaut (sans longitude/latitude) : la carte est un bonus,
        # jamais au prix du CSV déjà publiable — aucun crash, juste pas de carte.
        session = mock.Mock()
        session.get.side_effect = [
            _reponse_records(3), _reponse_streaming(), _reponse_streaming(), _reponse_dataset_meta(),
        ]
        resultat = etablissements_scolaires.moissonner(
            "35120", _GEVEZE, dossier_sortie=self.dossier, session_http=session,
        )
        medias = resultat.rudi_metadata["available_formats"]
        self.assertFalse(any(m["media_name"].endswith(".geojson") for m in medias))
        self.assertEqual(resultat.fichiers_filtres, [])

    def test_date_source_derivee_de_metas_default_modified(self):
        session = mock.Mock()
        session.get.side_effect = [_reponse_records(3), _reponse_streaming(), _reponse_streaming(), _reponse_dataset_meta()]
        resultat = etablissements_scolaires.moissonner(
            "35120", _GEVEZE, dossier_sortie=self.dossier, session_http=session,
        )
        self.assertEqual(
            resultat.rudi_metadata["dataset_dates"]["updated"], "2026-11-10T06:01:21Z",
        )

    def test_vide_sans_etablissement(self):
        session = mock.Mock()
        session.get.return_value = _reponse_records(0)
        resultat = etablissements_scolaires.moissonner(
            "35120", _GEVEZE, dossier_sortie=self.dossier, session_http=session,
        )
        self.assertEqual(resultat.statut, StatutConnecteur.VIDE)

    def test_echec_reseau(self):
        session = mock.Mock()
        session.get.side_effect = RuntimeError("timeout")
        resultat = etablissements_scolaires.moissonner(
            "35120", _GEVEZE, dossier_sortie=self.dossier, session_http=session,
        )
        self.assertEqual(resultat.statut, StatutConnecteur.ECHEC)

    def test_description_riche_mise_en_page_et_contenu_metier(self):
        session = mock.Mock()
        session.get.side_effect = [_reponse_records(3), _reponse_streaming(), _reponse_streaming(), _reponse_dataset_meta()]
        resultat = etablissements_scolaires.moissonner(
            "35120", _GEVEZE, dossier_sortie=self.dossier, session_http=session,
        )
        html = resultat.rudi_metadata["summary"][0]["html"]
        self.assertIn("<ul>", html)
        self.assertIn("</a>", html)
        self.assertIn("annuaire de l'éducation", html)
        self.assertIn("collèges", resultat.rudi_metadata["keywords"])


if __name__ == "__main__":
    unittest.main()
