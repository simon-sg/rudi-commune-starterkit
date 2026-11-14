"""Tests de datasets/immobilier_dvf.py — résolution dynamique de la ressource DVF
nationale unique, filtrage par commune, dates dérivées de date_mutation."""
import csv
import gzip
import io
import tempfile
import unittest
from unittest import mock

from rudi_commune_starterkit.datasets import immobilier_dvf
from rudi_commune_starterkit.resultat import StatutConnecteur

_GEVEZE = {"nom": "Gévezé", "code_insee": "35120", "code_departement": "35"}

_META_DATASET = {
    "resources": [
        {"title": "DVF 2025", "format": "csv.gz", "url": "https://x/full-2025.csv.gz"},
        {
            "title": "DVF juillet 2021 - juin 2026 - fichier unique",
            "format": "csv.gz",
            "url": "https://static.data.gouv.fr/x/dvf.csv.gz",
        },
    ],
}

_ENTETES = ["id_mutation", "date_mutation", "code_commune", "nom_commune", "valeur_fonciere"]
_LIGNE_2024 = {"id_mutation": "1", "date_mutation": "2024-05-01", "code_commune": "35120",
               "nom_commune": "Gévezé", "valeur_fonciere": "150000"}

_ENTETES_AVEC_COORDONNEES = _ENTETES + ["type_local", "surface_reelle_bati", "longitude", "latitude"]
_LIGNE_AVEC_COORDONNEES = {
    **_LIGNE_2024, "type_local": "Maison", "surface_reelle_bati": "90",
    "longitude": "-1.791200372", "latitude": "48.219343653",
}


def _csv_dvf_gz(lignes, entetes=_ENTETES):
    tampon = io.StringIO()
    writer = csv.DictWriter(tampon, fieldnames=entetes)
    writer.writeheader()
    writer.writerows(lignes)
    return gzip.compress(tampon.getvalue().encode("utf-8"))


def _reponse_json(payload):
    r = mock.Mock()
    r.raise_for_status = mock.Mock()
    r.json = mock.Mock(return_value=payload)
    return r


def _reponse_telechargement(contenu):
    r = mock.Mock()
    r.raise_for_status = mock.Mock()
    r.iter_content = mock.Mock(return_value=iter([contenu]))
    r.close = mock.Mock()
    return r


class TestMoissonnerImmobilierDvf(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.dossier = self._tmp.name

    def _session(self, lignes_source, entetes=_ENTETES):
        session = mock.Mock()
        session.get.side_effect = [
            _reponse_json(_META_DATASET),
            _reponse_telechargement(_csv_dvf_gz(lignes_source, entetes)),
        ]
        return session

    def test_publiable(self):
        session = self._session([_LIGNE_2024])
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
        self.assertEqual(lignes[0]["date_mutation"], "2024-05-01")

    def test_resout_la_ressource_fichier_unique_pas_la_ressource_annuelle(self):
        session = self._session([_LIGNE_2024])
        immobilier_dvf.moissonner(
            "35120", _GEVEZE, dossier_sortie=self.dossier, session_http=session,
        )
        url_telechargee = session.get.call_args_list[1].args[0]
        self.assertEqual(url_telechargee, "https://static.data.gouv.fr/x/dvf.csv.gz")

    def test_metadonnees_sans_em_dash(self):
        session = self._session([_LIGNE_2024])
        resultat = immobilier_dvf.moissonner(
            "35120", _GEVEZE, dossier_sortie=self.dossier, session_http=session,
        )
        self.assertNotIn("—", resultat.rudi_metadata["resource_title"])
        self.assertNotIn("—", resultat.rudi_metadata["synopsis"][0]["text"])
        self.assertNotIn("—", resultat.rudi_metadata["summary"][0]["text"])
        for media in resultat.rudi_metadata["available_formats"]:
            self.assertNotIn("—", media["media_caption"])

    def test_plusieurs_annees_dans_le_fichier_unique(self):
        ligne_2 = {**_LIGNE_2024, "id_mutation": "2", "date_mutation": "2022-01-01"}
        session = self._session([_LIGNE_2024, ligne_2])
        resultat = immobilier_dvf.moissonner(
            "35120", _GEVEZE, dossier_sortie=self.dossier, session_http=session,
        )
        self.assertEqual(resultat.statut, StatutConnecteur.PUBLIABLE)
        with open(resultat.fichiers_filtres[0], encoding="utf-8") as f:
            lignes = list(csv.DictReader(f))
        self.assertEqual(len(lignes), 2)
        self.assertIn("2022, 2024", resultat.rudi_metadata["available_formats"][0]["media_caption"])

    def test_vide_si_commune_absente_du_fichier(self):
        autre = {**_LIGNE_2024, "code_commune": "99999"}
        session = self._session([autre])
        resultat = immobilier_dvf.moissonner(
            "35120", _GEVEZE, dossier_sortie=self.dossier, session_http=session,
        )
        self.assertEqual(resultat.statut, StatutConnecteur.VIDE)

    def test_date_source_derivee_de_la_mtime_du_cache(self):
        import datetime
        session = self._session([_LIGNE_2024])
        resultat = immobilier_dvf.moissonner(
            "35120", _GEVEZE, dossier_sortie=self.dossier, session_http=session,
        )
        updated = resultat.rudi_metadata["dataset_dates"]["updated"]
        age = datetime.datetime.now(datetime.timezone.utc) - datetime.datetime.strptime(
            updated, "%Y-%m-%dT%H:%M:%SZ",
        ).replace(tzinfo=datetime.timezone.utc)
        self.assertLess(age.total_seconds(), 60)

    def test_echec_reseau_sur_resolution_dataset(self):
        session = mock.Mock()
        session.get.side_effect = RuntimeError("DNS")
        resultat = immobilier_dvf.moissonner(
            "35120", _GEVEZE, dossier_sortie=self.dossier, session_http=session,
        )
        self.assertEqual(resultat.statut, StatutConnecteur.ECHEC)

    def test_echec_telechargement(self):
        session = mock.Mock()
        reponse_echec = mock.Mock()
        reponse_echec.raise_for_status = mock.Mock(side_effect=Exception("HTTP 500"))
        session.get.side_effect = [_reponse_json(_META_DATASET), reponse_echec]
        resultat = immobilier_dvf.moissonner(
            "35120", _GEVEZE, dossier_sortie=self.dossier, session_http=session,
        )
        self.assertEqual(resultat.statut, StatutConnecteur.ECHEC)

    def test_description_riche_mise_en_page_et_contenu_metier(self):
        session = self._session([_LIGNE_2024])
        resultat = immobilier_dvf.moissonner(
            "35120", _GEVEZE, dossier_sortie=self.dossier, session_http=session,
        )
        html = resultat.rudi_metadata["summary"][0]["html"]
        self.assertIn("<ul>", html)
        self.assertIn("</a>", html)
        self.assertIn("DVF", html)
        self.assertIn("mutations", resultat.rudi_metadata["keywords"])

    def test_geojson_construit_depuis_longitude_latitude_et_depose_sur_le_noeud(self):
        session = self._session([_LIGNE_AVEC_COORDONNEES], entetes=_ENTETES_AVEC_COORDONNEES)
        resultat = immobilier_dvf.moissonner(
            "35120", _GEVEZE, dossier_sortie=self.dossier, session_http=session,
        )
        medias = resultat.rudi_metadata["available_formats"]
        medias_geojson = [m for m in medias if m["media_name"].endswith(".geojson")]
        self.assertEqual(len(medias_geojson), 1)
        self.assertEqual(medias_geojson[0]["media_type"], "FILE")
        self.assertIn("GeoJSON", medias_geojson[0]["media_caption"])
        self.assertNotIn("data.gouv.fr", medias_geojson[0]["connector"]["url"])
        self.assertEqual(len(resultat.fichiers_filtres), 2)
        self.assertTrue(resultat.fichiers_filtres[0].endswith(".geojson"))
        self.assertTrue(resultat.fichiers_filtres[1].endswith(".csv"))

    def test_media_geojson_precede_le_media_csv_dans_available_formats(self):
        # Garde-fou valider_alignement_medias() : les deux médias FILE réellement à
        # uploader (ni l'un ni l'autre n'est hybride ici) doivent apparaître dans le
        # même ordre que fichiers_filtres — geojson avant csv.
        session = self._session([_LIGNE_AVEC_COORDONNEES], entetes=_ENTETES_AVEC_COORDONNEES)
        resultat = immobilier_dvf.moissonner(
            "35120", _GEVEZE, dossier_sortie=self.dossier, session_http=session,
        )
        medias_file = resultat.rudi_metadata["available_formats"]
        self.assertTrue(medias_file[0]["media_name"].endswith(".geojson"))
        self.assertTrue(medias_file[1]["media_name"].endswith(".csv"))

    def test_sans_longitude_latitude_pas_de_media_geojson(self):
        # Fixture par défaut (_ENTETES) : aucune colonne longitude/latitude — la
        # carte est un bonus, jamais au prix du CSV déjà publiable, aucun crash.
        session = self._session([_LIGNE_2024])
        resultat = immobilier_dvf.moissonner(
            "35120", _GEVEZE, dossier_sortie=self.dossier, session_http=session,
        )
        medias = resultat.rudi_metadata["available_formats"]
        self.assertFalse(any(m["media_name"].endswith(".geojson") for m in medias))
        self.assertEqual(resultat.fichiers_filtres, [resultat.fichiers_filtres[0]])
        self.assertTrue(resultat.fichiers_filtres[0].endswith(".csv"))

    def test_description_riche_glossaire_et_limites(self):
        session = self._session([_LIGNE_2024])
        resultat = immobilier_dvf.moissonner(
            "35120", _GEVEZE, dossier_sortie=self.dossier, session_http=session,
        )
        html = resultat.rudi_metadata["summary"][0]["html"]
        self.assertIn("id_mutation", html)
        self.assertIn("id_parcelle", html)
        self.assertIn("Limites de couverture", html)


if __name__ == "__main__":
    unittest.main()
