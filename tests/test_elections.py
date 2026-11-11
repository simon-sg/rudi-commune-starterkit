"""Tests de datasets/elections.py — jeu agrégé (format long, plusieurs élections),
fichiers Parquet réels (pas de mock pyarrow — fixtures écrites sur disque via
pyarrow.parquet.write_table(), lues pour de vrai par lire_parquet_filtre())."""
import os
import tempfile
import unittest
from unittest import mock

import pyarrow as pa
import pyarrow.parquet as pq

from rudi_commune_starterkit import licences
from rudi_commune_starterkit.datasets import elections
from rudi_commune_starterkit.resultat import StatutConnecteur

_GEVEZE = {"nom": "Gévezé", "code_insee": "35120"}

_GENERAL_ROWS = [
    {"id_election": "2026_muni_t1", "code_commune": "35120", "code_bv": "35120_0001",
     "libelle_commune": "Gévezé", "inscrits": 2243, "abstentions": 898, "votants": 1345,
     "blancs": 21, "nuls": 13, "exprimes": 1311,
     "code_canton": "3512", "libelle_canton": "Canton de Betton",
     "code_circonscription": "3503", "libelle_circonscription": "3e circonscription"},
    {"id_election": "2026_muni_t1", "code_commune": "35120", "code_bv": "35120_0002",
     "libelle_commune": "Gévezé", "inscrits": 2244, "abstentions": 896, "votants": 1348,
     "blancs": 21, "nuls": 13, "exprimes": 1314,
     "code_canton": "3512", "libelle_canton": "Canton de Betton",
     "code_circonscription": "3503", "libelle_circonscription": "3e circonscription"},
    {"id_election": "2022_pres_t1", "code_commune": "35120", "code_bv": "35120_0001",
     "libelle_commune": "Gévezé", "inscrits": 2200, "abstentions": 500, "votants": 1700,
     "blancs": 20, "nuls": 10, "exprimes": 1670,
     "code_canton": "3512", "libelle_canton": "Canton de Betton",
     "code_circonscription": "3503", "libelle_circonscription": "3e circonscription"},
    {"id_election": "2026_muni_t1", "code_commune": "35238", "code_bv": "35238_0001",
     "libelle_commune": "Rennes", "inscrits": 9999, "abstentions": 1, "votants": 1,
     "blancs": 0, "nuls": 0, "exprimes": 1,
     "code_canton": "", "libelle_canton": "",
     "code_circonscription": "", "libelle_circonscription": ""},
]

_CANDIDATS_ROWS = [
    {"id_election": "2026_muni_t1", "code_commune": "35120", "code_bv": "35120_0001",
     "voix": 681, "no_panneau": 1, "nuance": "LDVD", "nom": None, "prenom": None,
     "liste": None, "libelle_abrege_liste": "GEVEZE, L'AVENIR EN CONFIANCE",
     "libelle_etendu_liste": "GEVEZE, L'AVENIR EN CONFIANCE"},
    {"id_election": "2026_muni_t1", "code_commune": "35120", "code_bv": "35120_0002",
     "voix": 680, "no_panneau": 1, "nuance": "LDVD", "nom": None, "prenom": None,
     "liste": None, "libelle_abrege_liste": "GEVEZE, L'AVENIR EN CONFIANCE",
     "libelle_etendu_liste": "GEVEZE, L'AVENIR EN CONFIANCE"},
    {"id_election": "2026_muni_t1", "code_commune": "35120", "code_bv": "35120_0001",
     "voix": 730, "no_panneau": 2, "nuance": "LDVG", "nom": None, "prenom": None,
     "liste": None, "libelle_abrege_liste": "VIVRE ENSEMBLE A GEVEZE",
     "libelle_etendu_liste": "VIVRE ENSEMBLE A GEVEZE"},
    {"id_election": "2026_muni_t1", "code_commune": "35120", "code_bv": "35120_0002",
     "voix": 737, "no_panneau": 2, "nuance": "LDVG", "nom": None, "prenom": None,
     "liste": None, "libelle_abrege_liste": "VIVRE ENSEMBLE A GEVEZE",
     "libelle_etendu_liste": "VIVRE ENSEMBLE A GEVEZE"},
    {"id_election": "2022_pres_t1", "code_commune": "35120", "code_bv": "35120_0001",
     "voix": 400, "no_panneau": 1, "nuance": "LFI", "nom": "Mélenchon", "prenom": "Jean-Luc",
     "liste": None, "libelle_abrege_liste": None, "libelle_etendu_liste": None},
    {"id_election": "2026_muni_t1", "code_commune": "35238", "code_bv": "35238_0001",
     "voix": 1, "no_panneau": 1, "nuance": "XXX", "nom": None, "prenom": None,
     "liste": None, "libelle_abrege_liste": None, "libelle_etendu_liste": None},
]


_ENTETES_MUNICIPALES = (
    ["Code département", "Libellé département", "Code commune", "Libellé commune"]
    + [
        f"{prefixe} {i}"
        for i in (1, 2)
        for prefixe in (
            "Numéro de panneau", "Nuance liste", "Libellé abrégé de liste",
            "Libellé de liste", "Voix", "Elu", "Sièges au CM", "Sièges au CC",
        )
    ]
)

_LIGNE_MUNICIPALES_GEVEZE = {
    "Code département": "35", "Libellé département": "Ille-et-Vilaine",
    "Code commune": "35120", "Libellé commune": "Gévezé",
    "Numéro de panneau 1": "1", "Libellé de liste 1": "GEVEZE, L'AVENIR EN CONFIANCE",
    "Libellé abrégé de liste 1": "GEVEZE, L'AVENIR EN CONFIANCE", "Nuance liste 1": "LDVD",
    "Voix 1": "1361", "Elu 1": "", "Sièges au CM 1": "6", "Sièges au CC 1": "0",
    "Numéro de panneau 2": "2", "Libellé de liste 2": "VIVRE ENSEMBLE A GEVEZE",
    "Libellé abrégé de liste 2": "VIVRE ENSEMBLE A GEVEZE", "Nuance liste 2": "LDVG",
    "Voix 2": "1467", "Elu 2": "", "Sièges au CM 2": "22", "Sièges au CC 2": "2",
}


def _csv_municipales(lignes):
    import csv
    import io
    tampon = io.StringIO()
    writer = csv.DictWriter(tampon, fieldnames=_ENTETES_MUNICIPALES, delimiter=";")
    writer.writeheader()
    for ligne in lignes:
        writer.writerow({champ: ligne.get(champ, "") for champ in _ENTETES_MUNICIPALES})
    return tampon.getvalue().encode("utf-8")


def _reponse_metadata_municipales():
    r = mock.Mock()
    r.raise_for_status = mock.Mock()
    r.json.return_value = {
        "resources": [
            {"id": "1", "title": "Municipales 2026 - Résultats - Communes_2026-03-20.csv",
             "url": "https://static.data.gouv.fr/municipales-communes.csv",
             "last_modified": "2026-03-21T00:00:00Z"},
        ],
    }
    return r


def _reponses_avec_jointure_municipales(general_rows=_GENERAL_ROWS, candidats_rows=_CANDIDATS_ROWS,
                                         lignes_municipales=(_LIGNE_MUNICIPALES_GEVEZE,)):
    return _reponses_parquet(general_rows, candidats_rows) + [
        _reponse_metadata_municipales(),
        _reponse_telechargement(_csv_municipales(lignes_municipales)),
    ]


_NUANCES_CSV = (
    b"type_nuance;bloc;libelle_nuance;signification;commentaires\n"
    b"liste;DIV;LDVD;Divers droite;Listes de sensibilite diverse droite\n"
    b"liste;GAU;LDVG;Divers gauche;Listes de sensibilite diverse gauche\n"
    b"individuelle;GAU;LFI;La France insoumise;Candidats investis par La France insoumise\n"
)


def _reponse_nuances():
    r = mock.Mock()
    r.raise_for_status = mock.Mock()
    r.iter_content = mock.Mock(return_value=iter([_NUANCES_CSV]))
    r.close = mock.Mock()
    return r


def _reponses_completes(general_rows=_GENERAL_ROWS, candidats_rows=_CANDIDATS_ROWS,
                         lignes_municipales=(_LIGNE_MUNICIPALES_GEVEZE,)):
    return _reponses_avec_jointure_municipales(general_rows, candidats_rows, lignes_municipales) + [
        _reponse_nuances(),
    ]


def _parquet_bytes(lignes, colonnes):
    data = {c: [l.get(c) for l in lignes] for c in colonnes}
    table = pa.table(data)
    with tempfile.TemporaryDirectory() as tmp:
        chemin = os.path.join(tmp, "f.parquet")
        pq.write_table(table, chemin)
        with open(chemin, "rb") as f:
            return f.read()


def _reponse_metadata(license="lov2"):
    r = mock.Mock()
    r.raise_for_status = mock.Mock()
    base = "https://data-pipeline-open.s3.sbg.io.cloud.ovh.net/elections"
    r.json.return_value = {
        "license": license,
        "page": "https://www.data.gouv.fr/fr/datasets/donnees-des-elections-agregees/",
        "resources": [
            {"id": "1", "title": "Résultats généraux", "format": "csv",
             "url": f"{base}/general_results.csv", "last_modified": "2026-07-07T14:00:35+00:00"},
            {"id": "2", "title": "Résultats par candidat", "format": "csv",
             "url": f"{base}/candidats_results.csv", "last_modified": "2026-07-07T14:00:58+00:00"},
            {"id": "3", "title": "Résultats généraux", "format": "parquet",
             "url": f"{base}/general_results.parquet", "last_modified": "2026-07-07T14:00:39+00:00"},
            {"id": "4", "title": "Résultats par candidat", "format": "parquet",
             "url": f"{base}/candidats_results.parquet", "last_modified": "2026-07-07T14:01:07+00:00"},
            {"id": "5", "title": "Dictionnaire des nuances politiques (2025)", "format": "csv",
             "url": f"{base}/nuances-2025.csv", "last_modified": "2026-02-16T09:21:46+00:00"},
            {"id": "6", "title": "Dictionnaire des nuances politiques (circulaire INTP2602966C de février 2026)",
             "format": "csv", "url": f"{base}/nuances-2026.csv", "last_modified": "2026-03-24T13:20:10+00:00"},
        ],
    }
    return r


def _reponse_telechargement(contenu):
    r = mock.Mock()
    r.raise_for_status = mock.Mock()
    r.iter_content = mock.Mock(return_value=iter([contenu]))
    r.close = mock.Mock()
    return r


def _reponses_parquet(general_rows=_GENERAL_ROWS, candidats_rows=_CANDIDATS_ROWS, license="lov2"):
    colonnes_generales = [
        "id_election", "code_commune", "code_bv", "libelle_commune",
        "inscrits", "abstentions", "votants", "blancs", "nuls", "exprimes",
        "code_canton", "libelle_canton", "code_circonscription", "libelle_circonscription",
    ]
    colonnes_candidats = [
        "id_election", "code_commune", "code_bv", "voix",
        "no_panneau", "nuance", "nom", "prenom", "liste",
        "libelle_abrege_liste", "libelle_etendu_liste",
    ]
    return [
        _reponse_metadata(license=license),
        _reponse_telechargement(_parquet_bytes(general_rows, colonnes_generales)),
        _reponse_telechargement(_parquet_bytes(candidats_rows, colonnes_candidats)),
    ]


class TestMoissonnerElections(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.dossier = self._tmp.name

    def test_publiable_deux_elections(self):
        session = mock.Mock()
        session.get.side_effect = _reponses_parquet()
        resultat = elections.moissonner(
            "35120", _GEVEZE, dossier_sortie=self.dossier, session_http=session,
        )
        self.assertEqual(resultat.statut, StatutConnecteur.PUBLIABLE)
        import csv
        with open(resultat.fichiers_filtres[0], encoding="utf-8", newline="") as f:
            lignes = list(csv.DictReader(f, delimiter=";"))
        self.assertEqual({l["type_election"] for l in lignes}, {"Municipales", "Présidentielles"})

    def test_ignore_une_autre_commune(self):
        session = mock.Mock()
        session.get.side_effect = _reponses_parquet()
        resultat = elections.moissonner(
            "35120", _GEVEZE, dossier_sortie=self.dossier, session_http=session,
        )
        import csv
        with open(resultat.fichiers_filtres[0], encoding="utf-8", newline="") as f:
            lignes = list(csv.DictReader(f, delimiter=";"))
        self.assertNotIn("Rennes", {l["libelle_commune"] for l in lignes})

    def test_voix_sommees_sur_les_deux_bureaux(self):
        session = mock.Mock()
        session.get.side_effect = _reponses_parquet()
        resultat = elections.moissonner(
            "35120", _GEVEZE, dossier_sortie=self.dossier, session_http=session,
        )
        import csv
        with open(resultat.fichiers_filtres[0], encoding="utf-8", newline="") as f:
            lignes = list(csv.DictReader(f, delimiter=";"))
        muni = [l for l in lignes if l["type_election"] == "Municipales"]
        voix = {l["no_panneau"]: int(l["voix"]) for l in muni}
        self.assertEqual(voix, {"1": 1361, "2": 1467})

    def test_totaux_commune_sommes_sur_les_deux_bureaux(self):
        session = mock.Mock()
        session.get.side_effect = _reponses_parquet()
        resultat = elections.moissonner(
            "35120", _GEVEZE, dossier_sortie=self.dossier, session_http=session,
        )
        import csv
        with open(resultat.fichiers_filtres[0], encoding="utf-8", newline="") as f:
            lignes = list(csv.DictReader(f, delimiter=";"))
        muni = [l for l in lignes if l["type_election"] == "Municipales"]
        self.assertEqual(int(muni[0]["inscrits"]), 2243 + 2244)
        self.assertEqual(int(muni[0]["votants"]), 1345 + 1348)

    def test_canton_circonscription_joints_au_niveau_bureau(self):
        session = mock.Mock()
        session.get.side_effect = _reponses_parquet()
        resultat = elections.moissonner(
            "35120", _GEVEZE, dossier_sortie=self.dossier, session_http=session,
        )
        import csv
        with open(resultat.fichiers_filtres[0], encoding="utf-8", newline="") as f:
            lignes = list(csv.DictReader(f, delimiter=";"))
        for ligne in lignes:
            if ligne["type_election"] == "Municipales":
                self.assertEqual(ligne["code_canton"], "3512")
                self.assertEqual(ligne["libelle_circonscription"], "3e circonscription")

    def test_colonnes_en_tete(self):
        session = mock.Mock()
        session.get.side_effect = _reponses_parquet()
        resultat = elections.moissonner(
            "35120", _GEVEZE, dossier_sortie=self.dossier, session_http=session,
        )
        import csv
        with open(resultat.fichiers_filtres[0], encoding="utf-8", newline="") as f:
            reader = csv.reader(f, delimiter=";")
            entete = next(reader)
        self.assertEqual(entete[:3], ["annee", "type_election", "tour"])

    def test_selectionne_bien_les_ressources_parquet_pas_csv(self):
        session = mock.Mock()
        session.get.side_effect = _reponses_parquet()
        elections.moissonner("35120", _GEVEZE, dossier_sortie=self.dossier, session_http=session)
        urls_telechargees = [c.args[0] for c in session.get.call_args_list[1:3]]
        self.assertTrue(all(u.endswith(".parquet") for u in urls_telechargees))

    def test_vide_sans_ligne_pour_la_commune(self):
        session = mock.Mock()
        session.get.side_effect = _reponses_parquet(
            general_rows=[r for r in _GENERAL_ROWS if r["code_commune"] != "35120"],
            candidats_rows=[r for r in _CANDIDATS_ROWS if r["code_commune"] != "35120"],
        )
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

    def test_licence_dynamique_depuis_datagouv(self):
        session = mock.Mock()
        session.get.side_effect = _reponses_parquet(license="lov2")
        resultat = elections.moissonner(
            "35120", _GEVEZE, dossier_sortie=self.dossier, session_http=session,
        )
        self.assertEqual(resultat.statut, StatutConnecteur.PUBLIABLE)
        self.assertEqual(
            resultat.rudi_metadata["access_condition"]["licence"]["licence_label"], "etalab-2.0",
        )

    def test_licence_inconnue_est_un_echec_isole(self):
        session = mock.Mock()
        session.get.side_effect = _reponses_parquet(license=None)
        table_sans_elections = {k: v for k, v in licences.LICENCES_CUREES.items() if k != elections.CLE}
        with mock.patch.object(licences, "LICENCES_CUREES", table_sans_elections):
            resultat = elections.moissonner(
                "35120", _GEVEZE, dossier_sortie=self.dossier, session_http=session,
            )
        self.assertEqual(resultat.statut, StatutConnecteur.ECHEC)

    def test_titre_ne_contient_plus_municipales(self):
        session = mock.Mock()
        session.get.side_effect = _reponses_parquet()
        resultat = elections.moissonner(
            "35120", _GEVEZE, dossier_sortie=self.dossier, session_http=session,
        )
        self.assertNotIn("municipales", resultat.rudi_metadata["resource_title"].lower())

    def test_description_mentionne_types_trouves_et_limites(self):
        session = mock.Mock()
        session.get.side_effect = _reponses_parquet()
        resultat = elections.moissonner(
            "35120", _GEVEZE, dossier_sortie=self.dossier, session_http=session,
        )
        html = resultat.rudi_metadata["summary"][0]["html"]
        self.assertIn("Présidentielles", html)
        self.assertIn("Municipales", html)
        self.assertIn("Limites de couverture", html)
        self.assertIn("résultats électoraux", resultat.rudi_metadata["keywords"])

    def test_jointure_elu_sieges_sur_2026_muni_t1(self):
        session = mock.Mock()
        session.get.side_effect = _reponses_avec_jointure_municipales()
        resultat = elections.moissonner(
            "35120", _GEVEZE, dossier_sortie=self.dossier, session_http=session,
        )
        import csv
        with open(resultat.fichiers_filtres[0], encoding="utf-8", newline="") as f:
            lignes = list(csv.DictReader(f, delimiter=";"))
        muni = {l["no_panneau"]: l for l in lignes if l["type_election"] == "Municipales"}
        self.assertEqual(muni["1"]["sieges_conseil_municipal"], "6")
        self.assertEqual(muni["1"]["elu"], "True")
        self.assertEqual(muni["2"]["sieges_conseil_municipal"], "22")
        self.assertEqual(muni["2"]["sieges_conseil_communautaire"], "2")

    def test_pas_de_sieges_sur_un_autre_scrutin(self):
        session = mock.Mock()
        session.get.side_effect = _reponses_avec_jointure_municipales()
        resultat = elections.moissonner(
            "35120", _GEVEZE, dossier_sortie=self.dossier, session_http=session,
        )
        import csv
        with open(resultat.fichiers_filtres[0], encoding="utf-8", newline="") as f:
            lignes = list(csv.DictReader(f, delimiter=";"))
        pres = [l for l in lignes if l["type_election"] == "Présidentielles"]
        for ligne in pres:
            self.assertEqual(ligne["sieges_conseil_municipal"], "")

    def test_jointure_indisponible_ne_fait_pas_echouer_le_run(self):
        session = mock.Mock()
        # Source municipales 2026 absente (quota HTTP épuisé après les 3 appels
        # Parquet) — doit se dégrader proprement, pas planter tout le run.
        session.get.side_effect = _reponses_parquet()
        resultat = elections.moissonner(
            "35120", _GEVEZE, dossier_sortie=self.dossier, session_http=session,
        )
        self.assertEqual(resultat.statut, StatutConnecteur.PUBLIABLE)
        import csv
        with open(resultat.fichiers_filtres[0], encoding="utf-8", newline="") as f:
            lignes = list(csv.DictReader(f, delimiter=";"))
        for ligne in lignes:
            self.assertEqual(ligne["sieges_conseil_municipal"], "")

    def test_glossaire_nuances_rencontrees_dans_la_description(self):
        session = mock.Mock()
        session.get.side_effect = _reponses_completes()
        resultat = elections.moissonner(
            "35120", _GEVEZE, dossier_sortie=self.dossier, session_http=session,
        )
        html = resultat.rudi_metadata["summary"][0]["html"]
        self.assertIn("Codes et variables", html)
        self.assertIn("Divers droite", html)
        self.assertIn("Divers gauche", html)
        self.assertIn("La France insoumise", html)

    def test_glossaire_utilise_la_ressource_nuances_la_plus_recente(self):
        session = mock.Mock()
        session.get.side_effect = _reponses_completes()
        elections.moissonner("35120", _GEVEZE, dossier_sortie=self.dossier, session_http=session)
        url_nuances = session.get.call_args_list[5].args[0]
        self.assertTrue(url_nuances.endswith("nuances-2026.csv"))

    def test_glossaire_indisponible_ne_fait_pas_echouer_le_run(self):
        session = mock.Mock()
        session.get.side_effect = _reponses_avec_jointure_municipales()
        resultat = elections.moissonner(
            "35120", _GEVEZE, dossier_sortie=self.dossier, session_http=session,
        )
        self.assertEqual(resultat.statut, StatutConnecteur.PUBLIABLE)
        html = resultat.rudi_metadata["summary"][0]["html"]
        self.assertNotIn("Codes et variables", html)

    def test_sieges_disponibles_vrai_pour_les_lignes_jointes(self):
        session = mock.Mock()
        session.get.side_effect = _reponses_avec_jointure_municipales()
        resultat = elections.moissonner(
            "35120", _GEVEZE, dossier_sortie=self.dossier, session_http=session,
        )
        import csv
        with open(resultat.fichiers_filtres[0], encoding="utf-8", newline="") as f:
            lignes = list(csv.DictReader(f, delimiter=";"))
        muni = [l for l in lignes if l["type_election"] == "Municipales"]
        pres = [l for l in lignes if l["type_election"] == "Présidentielles"]
        self.assertTrue(all(l["sieges_disponibles"] == "True" for l in muni))
        self.assertTrue(all(l["sieges_disponibles"] == "False" for l in pres))

    def test_metadonnees_sans_em_dash(self):
        session = mock.Mock()
        session.get.side_effect = _reponses_parquet()
        resultat = elections.moissonner(
            "35120", _GEVEZE, dossier_sortie=self.dossier, session_http=session,
        )
        self.assertNotIn("—", resultat.rudi_metadata["resource_title"])
        self.assertNotIn("—", resultat.rudi_metadata["synopsis"][0]["text"])
        for media in resultat.rudi_metadata["available_formats"]:
            self.assertNotIn("—", media["media_caption"])


if __name__ == "__main__":
    unittest.main()
