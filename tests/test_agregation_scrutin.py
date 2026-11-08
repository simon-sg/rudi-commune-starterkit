"""Tests de agregation_scrutin.py — unpivot + padding + agrégation bureau→commune."""
import unittest

from rudi_commune_starterkit.agregation_scrutin import (
    CodeCommuneInvalide,
    agreger_bureau_vers_commune,
    normaliser_code_commune,
    unpivot_candidats,
)

_BUREAUX_GEVEZE = [
    {
        "Code commune": "35120",
        "Inscrits": "1000",
        "Votants": "700",
        "Exprimés": "650",
        "Voix CandidatA": "400",
        "Voix CandidatB": "250",
    },
    {
        "Code commune": "35120",
        "Inscrits": "500",
        "Votants": "300",
        "Exprimés": "280",
        "Voix CandidatA": "180",
        "Voix CandidatB": "100",
    },
]

_BUREAUX_AUTRE_COMMUNE = [
    {"Code commune": "35238", "Inscrits": "200", "Votants": "100", "Exprimés": "90",
     "Voix CandidatA": "50", "Voix CandidatB": "40"},
]


class TestNormaliserCodeCommune(unittest.TestCase):
    def test_zero_pad(self):
        self.assertEqual(normaliser_code_commune("120"), "00120")
        self.assertEqual(normaliser_code_commune(35120), "35120")

    def test_corse_inchangee(self):
        self.assertEqual(normaliser_code_commune("2A004"), "2A004")
        self.assertEqual(normaliser_code_commune("2b004"), "2B004")

    def test_corse_mal_formee_leve(self):
        with self.assertRaises(CodeCommuneInvalide):
            normaliser_code_commune("2A4")

    def test_code_vide_leve(self):
        with self.assertRaises(CodeCommuneInvalide):
            normaliser_code_commune("")

    def test_code_none_leve(self):
        with self.assertRaises(CodeCommuneInvalide):
            normaliser_code_commune(None)

    def test_code_non_numerique_leve(self):
        with self.assertRaises(CodeCommuneInvalide):
            normaliser_code_commune("ABCDE")


class TestUnpivotCandidats(unittest.TestCase):
    def test_unpivot_une_ligne(self):
        colonnes = {"Candidat A": "Voix CandidatA", "Candidat B": "Voix CandidatB"}
        lignes = unpivot_candidats(_BUREAUX_GEVEZE[0], colonnes)
        self.assertEqual(
            lignes,
            [{"candidat": "Candidat A", "voix": 400}, {"candidat": "Candidat B", "voix": 250}],
        )

    def test_colonne_absente_vaut_zero(self):
        lignes = unpivot_candidats({}, {"Candidat A": "Voix CandidatA"})
        self.assertEqual(lignes, [{"candidat": "Candidat A", "voix": 0}])


class TestAgregerBureauVersCommune(unittest.TestCase):
    def test_agrege_deux_bureaux(self):
        resultat = agreger_bureau_vers_commune(
            _BUREAUX_GEVEZE + _BUREAUX_AUTRE_COMMUNE,
            "35120",
            champ_code_commune="Code commune",
            colonnes_candidats={"Candidat A": "Voix CandidatA", "Candidat B": "Voix CandidatB"},
            champs_totaux={"inscrits": "Inscrits", "votants": "Votants", "exprimes": "Exprimés"},
        )
        self.assertEqual(resultat["code_insee"], "35120")
        self.assertEqual(resultat["nb_bureaux"], 2)
        self.assertEqual(resultat["candidats"], {"Candidat A": 580, "Candidat B": 350})
        self.assertEqual(resultat["inscrits"], 1500)
        self.assertEqual(resultat["votants"], 1000)
        self.assertEqual(resultat["exprimes"], 930)

    def test_ignore_les_bureaux_d_une_autre_commune(self):
        resultat = agreger_bureau_vers_commune(
            _BUREAUX_GEVEZE + _BUREAUX_AUTRE_COMMUNE,
            "35238",
            champ_code_commune="Code commune",
            colonnes_candidats={"Candidat A": "Voix CandidatA"},
        )
        self.assertEqual(resultat["nb_bureaux"], 1)
        self.assertEqual(resultat["candidats"], {"Candidat A": 50})

    def test_padding_absorbe(self):
        # Fichier d'un autre millésime : code commune sans le département en tête.
        bureaux = [{"Code commune": "120", "Voix CandidatA": "10"}]
        resultat = agreger_bureau_vers_commune(
            bureaux, "00120", champ_code_commune="Code commune",
            colonnes_candidats={"Candidat A": "Voix CandidatA"},
        )
        self.assertEqual(resultat["nb_bureaux"], 1)

    def test_aucun_bureau_trouve_leve(self):
        with self.assertRaises(CodeCommuneInvalide):
            agreger_bureau_vers_commune(
                _BUREAUX_AUTRE_COMMUNE, "99999", champ_code_commune="Code commune",
                colonnes_candidats={"Candidat A": "Voix CandidatA"},
            )

    def test_totaux_optionnels_absents_par_defaut(self):
        resultat = agreger_bureau_vers_commune(
            _BUREAUX_GEVEZE, "35120", champ_code_commune="Code commune",
            colonnes_candidats={"Candidat A": "Voix CandidatA"},
        )
        self.assertNotIn("inscrits", resultat)


if __name__ == "__main__":
    unittest.main()
