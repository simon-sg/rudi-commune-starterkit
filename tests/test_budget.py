"""Tests de datasets/budget.py — union de 12 datasets DGFiP, harmonisation de schéma,
split dep/icom, Corse-safe."""
import csv
import tempfile
import unittest
from unittest import mock

from rudi_commune_starterkit.datasets import budget
from rudi_commune_starterkit.datasets.budget import (
    _DATASET_IDS,
    DepartementNonSupporte,
    _dep_icom,
    _entetes_harmonisees,
    _glossaire_colonnes,
)
from rudi_commune_starterkit.resultat import StatutConnecteur

_GEVEZE = {"nom": "Gévezé", "code_insee": "35120"}

_LIGNE_BASE = {"an": "2023", "dep": "035", "icom": "120", "inom": "GEVEZE", "prod": 5426.64}


def _reponse_records(resultats, total_count=None):
    r = mock.Mock()
    r.raise_for_status = mock.Mock()
    r.json.return_value = {
        "results": resultats,
        "total_count": total_count if total_count is not None else len(resultats),
    }
    return r


def _reponse_dataset_meta(modified="2026-09-24T10:00:00+00:00"):
    r = mock.Mock()
    r.raise_for_status = mock.Mock()
    r.json.return_value = {"metas": {"default": {"modified": modified}}}
    return r


def _side_effect(lignes_par_dataset=None, erreurs=None, dates_meta=None):
    """Construit la séquence session.get.side_effect dans l'ordre réel de
    moissonner() : une requête /records par dataset de _DATASET_IDS (ou une
    exception si le dataset est dans `erreurs`), puis une requête de métadonnées par
    dataset ayant contribué des lignes (dans le même ordre)."""
    lignes_par_dataset = lignes_par_dataset or {}
    erreurs = erreurs or set()
    effets = []
    contribues = []
    for dataset_id in _DATASET_IDS:
        if dataset_id in erreurs:
            effets.append(RuntimeError(f"erreur réseau {dataset_id}"))
            continue
        lignes = lignes_par_dataset.get(dataset_id, [])
        effets.append(_reponse_records(lignes))
        if lignes:
            contribues.append(dataset_id)
    dates_meta = dates_meta or {}
    for dataset_id in contribues:
        effets.append(_reponse_dataset_meta(dates_meta.get(dataset_id, "2026-09-24T10:00:00+00:00")))
    return effets


class TestDepIcom(unittest.TestCase):
    def test_metropole(self):
        self.assertEqual(_dep_icom("35120"), ("035", "120"))

    def test_corse_2a(self):
        self.assertEqual(_dep_icom("2A004"), ("02A", "004"))

    def test_corse_2b(self):
        self.assertEqual(_dep_icom("2B033"), ("02B", "033"))

    def test_dom_non_supporte(self):
        with self.assertRaises(DepartementNonSupporte):
            _dep_icom("97411")


class TestEntetesHarmonisees(unittest.TestCase):
    def test_priorite_puis_alphabetique(self):
        lignes = [
            {"an": "2020", "dep": "035", "icom": "120", "inom": "GEVEZE", "prod": 1, "zzz": 2},
            {"an": "2021", "dep": "035", "icom": "120", "inom": "GEVEZE", "aaa": 3},
        ]
        self.assertEqual(
            _entetes_harmonisees(lignes),
            ["an", "dep", "icom", "inom", "aaa", "prod", "zzz"],
        )

    def test_union_pas_intersection(self):
        lignes = [{"an": "2020", "solo_a": 1}, {"an": "2021", "solo_b": 2}]
        entetes = _entetes_harmonisees(lignes)
        self.assertIn("solo_a", entetes)
        self.assertIn("solo_b", entetes)


class TestGlossaireColonnes(unittest.TestCase):
    def test_restreint_aux_colonnes_presentes(self):
        g = _glossaire_colonnes(["an", "dep", "icom", "inom", "prod"])
        self.assertIn("prod", g)
        self.assertNotIn("impo1", g)
        self.assertNotIn("préfixes f/m/r/rm", g)

    def test_detecte_variante_prefixe_simple(self):
        g = _glossaire_colonnes(["an", "prod", "fprod"])
        self.assertIn("préfixes f/m/r/rm", g)

    def test_detecte_variante_prefixe_rm(self):
        g = _glossaire_colonnes(["an", "dgf", "rmdgf"])
        self.assertIn("préfixes f/m/r/rm", g)

    def test_sans_variante_pas_de_note(self):
        g = _glossaire_colonnes(["an", "dep", "icom"])
        self.assertNotIn("préfixes f/m/r/rm", g)


class TestMoissonnerBudget(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.dossier = self._tmp.name

    def test_publiable_plusieurs_exercices_harmonises(self):
        lignes_par_dataset = {
            "comptes-individuels-des-communes-fichier-global-2023-2024": [
                {**_LIGNE_BASE, "an": "2023"},
                {**_LIGNE_BASE, "an": "2024", "impo1": 2757.58},
            ],
            "comptes-individuels-des-communes-fichier-global-2025": [
                {**_LIGNE_BASE, "an": "2025", "nouveaute_2025": 42},
            ],
        }
        session = mock.Mock()
        session.get.side_effect = _side_effect(lignes_par_dataset)

        resultat = budget.moissonner(
            "35120", _GEVEZE, dossier_sortie=self.dossier, session_http=session,
        )

        self.assertEqual(resultat.statut, StatutConnecteur.PUBLIABLE)
        with open(resultat.fichiers_filtres[0], encoding="utf-8", newline="") as f:
            lignes = list(csv.DictReader(f, delimiter=";"))
        self.assertEqual([l["an"] for l in lignes], ["2023", "2024", "2025"])
        # colonne apparue seulement en 2025 : présente (union), vide ailleurs.
        self.assertEqual(lignes[0]["nouveaute_2025"], "")
        self.assertEqual(lignes[2]["nouveaute_2025"], "42")
        # colonne absente en 2023 (impo1 ajouté en 2024 dans la fixture) : harmonisée.
        self.assertEqual(lignes[0]["impo1"], "")
        self.assertEqual(lignes[1]["impo1"], "2757.58")

    def test_licence_etalab(self):
        session = mock.Mock()
        session.get.side_effect = _side_effect({
            "comptes-individuels-des-communes-fichier-global-2025": [{**_LIGNE_BASE, "an": "2025"}],
        })
        resultat = budget.moissonner(
            "35120", _GEVEZE, dossier_sortie=self.dossier, session_http=session,
        )
        licence = resultat.rudi_metadata["access_condition"]["licence"]
        self.assertEqual(licence["licence_type"], "STANDARD")
        self.assertEqual(licence["licence_label"], "etalab-2.0")

    def test_vide_si_aucune_ligne_dans_aucun_dataset(self):
        session = mock.Mock()
        session.get.side_effect = _side_effect({})
        resultat = budget.moissonner(
            "35120", _GEVEZE, dossier_sortie=self.dossier, session_http=session,
        )
        self.assertEqual(resultat.statut, StatutConnecteur.VIDE)

    def test_echec_si_tous_les_datasets_indisponibles(self):
        session = mock.Mock()
        session.get.side_effect = _side_effect({}, erreurs=set(_DATASET_IDS))
        resultat = budget.moissonner(
            "35120", _GEVEZE, dossier_sortie=self.dossier, session_http=session,
        )
        self.assertEqual(resultat.statut, StatutConnecteur.ECHEC)

    def test_degrade_si_un_seul_dataset_echoue(self):
        session = mock.Mock()
        session.get.side_effect = _side_effect(
            {"comptes-individuels-des-communes-fichier-global-2025": [{**_LIGNE_BASE, "an": "2025"}]},
            erreurs={"comptes-individuels-des-communes-fichier-global-2008"},
        )
        resultat = budget.moissonner(
            "35120", _GEVEZE, dossier_sortie=self.dossier, session_http=session,
        )
        self.assertEqual(resultat.statut, StatutConnecteur.PUBLIABLE)
        html = resultat.rudi_metadata["summary"][0]["html"]
        self.assertIn("non interrogeable", html)

    def test_echec_outre_mer(self):
        session = mock.Mock()
        resultat = budget.moissonner(
            "97411", {"nom": "Saint-Denis", "code_insee": "97411"},
            dossier_sortie=self.dossier, session_http=session,
        )
        self.assertEqual(resultat.statut, StatutConnecteur.ECHEC)
        session.get.assert_not_called()

    def test_where_clause_utilise_dep_icom(self):
        session = mock.Mock()
        session.get.side_effect = _side_effect({})
        budget.moissonner("35120", _GEVEZE, dossier_sortie=self.dossier, session_http=session)
        premier_appel = session.get.call_args_list[0]
        self.assertEqual(premier_appel.kwargs["params"]["where"], "dep='035' AND icom='120'")

    def test_pagination_complete_sur_un_dataset(self):
        page1 = [{**_LIGNE_BASE, "an": str(1900 + i)} for i in range(100)]
        page2 = [{**_LIGNE_BASE, "an": str(2000 + i)} for i in range(50)]
        effets = []
        for dataset_id in _DATASET_IDS:
            if dataset_id == "comptes-individuels-des-communes-fichier-global-2008":
                effets.append(_reponse_records(page1, total_count=150))
                effets.append(_reponse_records(page2, total_count=150))
            else:
                effets.append(_reponse_records([]))
        effets.append(_reponse_dataset_meta())

        session = mock.Mock()
        session.get.side_effect = effets
        resultat = budget.moissonner(
            "35120", _GEVEZE, dossier_sortie=self.dossier, session_http=session,
        )
        self.assertEqual(resultat.statut, StatutConnecteur.PUBLIABLE)
        with open(resultat.fichiers_filtres[0], encoding="utf-8", newline="") as f:
            lignes = list(csv.DictReader(f, delimiter=";"))
        self.assertEqual(len(lignes), 150)

    def test_doublon_exercice_entre_datasets_dernier_conserve(self):
        session = mock.Mock()
        session.get.side_effect = _side_effect({
            "comptes-individuels-des-communes-fichier-global-2021": [{**_LIGNE_BASE, "an": "2021", "prod": 1.0}],
            "comptes-individuels-des-communes-fichier-global-2022": [{**_LIGNE_BASE, "an": "2021", "prod": 2.0}],
        })
        resultat = budget.moissonner(
            "35120", _GEVEZE, dossier_sortie=self.dossier, session_http=session,
        )
        self.assertEqual(resultat.statut, StatutConnecteur.PUBLIABLE)
        with open(resultat.fichiers_filtres[0], encoding="utf-8", newline="") as f:
            lignes = list(csv.DictReader(f, delimiter=";"))
        self.assertEqual(len(lignes), 1)
        self.assertEqual(lignes[0]["prod"], "2.0")

    def test_date_source_max_des_datasets_contribues(self):
        session = mock.Mock()
        session.get.side_effect = _side_effect(
            {
                "comptes-individuels-des-communes-fichier-global-2021": [{**_LIGNE_BASE, "an": "2021"}],
                "comptes-individuels-des-communes-fichier-global-2022": [{**_LIGNE_BASE, "an": "2022"}],
            },
            dates_meta={
                "comptes-individuels-des-communes-fichier-global-2021": "2025-01-01T00:00:00+00:00",
                "comptes-individuels-des-communes-fichier-global-2022": "2026-06-15T00:00:00+00:00",
            },
        )
        resultat = budget.moissonner(
            "35120", _GEVEZE, dossier_sortie=self.dossier, session_http=session,
        )
        self.assertEqual(
            resultat.rudi_metadata["dataset_dates"]["updated"], "2026-06-15T00:00:00Z",
        )

    def test_description_riche_glossaire_et_limites(self):
        session = mock.Mock()
        session.get.side_effect = _side_effect({
            "comptes-individuels-des-communes-fichier-global-2025": [{**_LIGNE_BASE, "an": "2025"}],
        })
        resultat = budget.moissonner(
            "35120", _GEVEZE, dossier_sortie=self.dossier, session_http=session,
        )
        html = resultat.rudi_metadata["summary"][0]["html"]
        self.assertIn("<ul>", html)
        self.assertIn("DGFiP", html)
        self.assertIn("Total des produits de fonctionnement", html)
        self.assertIn("Limites de couverture", html)
        self.assertIn("comptes communaux", resultat.rudi_metadata["keywords"])

    def test_metadonnees_sans_em_dash(self):
        session = mock.Mock()
        session.get.side_effect = _side_effect({
            "comptes-individuels-des-communes-fichier-global-2025": [{**_LIGNE_BASE, "an": "2025"}],
        })
        resultat = budget.moissonner(
            "35120", _GEVEZE, dossier_sortie=self.dossier, session_http=session,
        )
        self.assertNotIn("—", resultat.rudi_metadata["resource_title"])
        self.assertNotIn("—", resultat.rudi_metadata["synopsis"][0]["text"])
        self.assertNotIn("—", resultat.rudi_metadata["summary"][0]["text"])
        for media in resultat.rudi_metadata["available_formats"]:
            self.assertNotIn("—", media["media_caption"])


if __name__ == "__main__":
    unittest.main()
