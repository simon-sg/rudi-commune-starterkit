"""Tests de agregation_scrutin.py — unpivot + padding + agrégation bureau→commune."""
import unittest

from rudi_commune_starterkit.agregation_scrutin import (
    TYPES_ELECTION,
    CodeCommuneInvalide,
    TypeElectionInconnu,
    agreger_bureau_vers_commune,
    agreger_long_vers_commune,
    decomposer_id_election,
    normaliser_code_commune,
    recalculer_ratios,
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


class TestDecomposerIdElection(unittest.TestCase):
    def test_decompose_un_id_election_valide(self):
        self.assertEqual(
            decomposer_id_election("2026_muni_t2"),
            {"annee": "2026", "type_election": "Municipales", "tour": 2},
        )

    def test_tous_les_types_connus_sont_couverts(self):
        for code, libelle in TYPES_ELECTION.items():
            self.assertEqual(
                decomposer_id_election(f"2020_{code}_t1")["type_election"], libelle,
            )

    def test_type_inconnu_leve(self):
        with self.assertRaises(TypeElectionInconnu):
            decomposer_id_election("2026_inconnu_t1")

    def test_format_mal_forme_leve(self):
        with self.assertRaises(TypeElectionInconnu):
            decomposer_id_election("pas-un-id-election")

    def test_none_leve(self):
        with self.assertRaises(TypeElectionInconnu):
            decomposer_id_election(None)


class TestRecalculerRatios(unittest.TestCase):
    def test_ratios_corrects(self):
        totaux = {
            "inscrits": 4487, "abstentions": 1591, "votants": 2896,
            "blancs": 42, "nuls": 26, "exprimes": 2828,
        }
        ratios = recalculer_ratios(totaux)
        self.assertAlmostEqual(ratios["ratio_votants_inscrits"], 2896 / 4487, places=4)
        self.assertAlmostEqual(ratios["ratio_exprimes_votants"], 2828 / 2896, places=4)

    def test_division_par_zero_inscrits_retourne_none(self):
        ratios = recalculer_ratios({"inscrits": 0, "votants": 0, "abstentions": 0,
                                     "blancs": 0, "nuls": 0, "exprimes": 0})
        self.assertIsNone(ratios["ratio_votants_inscrits"])
        self.assertIsNone(ratios["ratio_abstentions_inscrits"])

    def test_division_par_zero_votants_mais_pas_inscrits(self):
        ratios = recalculer_ratios({"inscrits": 100, "votants": 0, "blancs": 0,
                                     "nuls": 0, "exprimes": 0, "abstentions": 100})
        self.assertIsNone(ratios["ratio_blancs_votants"])
        self.assertEqual(ratios["ratio_abstentions_inscrits"], 1.0)

    def test_champs_absents_traites_comme_zero(self):
        ratios = recalculer_ratios({"inscrits": 100, "votants": 50})
        self.assertEqual(ratios["ratio_blancs_inscrits"], 0.0)


_LIGNES_GENERAL = [
    {"id_election": "2022_pres_t1", "code_commune": "35120", "inscrits": "600",
     "abstentions": "200", "votants": "400", "blancs": "10", "nuls": "5", "exprimes": "385"},
    {"id_election": "2022_pres_t1", "code_commune": "35120", "inscrits": "400",
     "abstentions": "100", "votants": "300", "blancs": "5", "nuls": "2", "exprimes": "293"},
    {"id_election": "2026_muni_t1", "code_commune": "35120", "inscrits": "1000",
     "abstentions": "300", "votants": "700", "blancs": "15", "nuls": "7", "exprimes": "678"},
    {"id_election": "2022_pres_t1", "code_commune": "35238", "inscrits": "9999",
     "abstentions": "0", "votants": "0", "blancs": "0", "nuls": "0", "exprimes": "0"},
]

_LIGNES_CANDIDATS = [
    {"id_election": "2022_pres_t1", "code_commune": "35120", "no_panneau": "1",
     "nuance": "LFI", "voix": "100"},
    {"id_election": "2022_pres_t1", "code_commune": "35120", "no_panneau": "1",
     "nuance": "LFI", "voix": "80"},
    {"id_election": "2022_pres_t1", "code_commune": "35120", "no_panneau": "2",
     "nuance": "LR", "voix": "200"},
]


class TestAgregerLongVersCommune(unittest.TestCase):
    def test_totaux_une_entree_par_election_triee(self):
        resultat = agreger_long_vers_commune(
            _LIGNES_GENERAL, "35120",
            champs_totaux=("inscrits", "abstentions", "votants", "blancs", "nuls", "exprimes"),
        )
        self.assertEqual([r["id_election"] for r in resultat], ["2022_pres_t1", "2026_muni_t1"])
        pres = resultat[0]
        self.assertEqual(pres["inscrits"], 1000)
        self.assertEqual(pres["votants"], 700)

    def test_totaux_ignore_une_autre_commune(self):
        resultat = agreger_long_vers_commune(
            _LIGNES_GENERAL, "35120",
            champs_totaux=("inscrits",),
        )
        # 600+400 (pres t1, 2 bureaux) + 1000 (muni t1) — exclut la ligne 35238 (9999).
        self.assertEqual(sum(r["inscrits"] for r in resultat), 600 + 400 + 1000)

    def test_candidats_fusionne_meme_identite_sur_plusieurs_bureaux(self):
        resultat = agreger_long_vers_commune(
            _LIGNES_CANDIDATS, "35120",
            champs_identite_candidat=("no_panneau", "nuance"),
        )
        self.assertEqual(len(resultat), 2)
        candidat_1 = next(r for r in resultat if r["no_panneau"] == "1")
        self.assertEqual(candidat_1["voix"], 180)

    def test_candidats_avec_identites_differentes_ne_fusionnent_jamais(self):
        resultat = agreger_long_vers_commune(
            _LIGNES_CANDIDATS, "35120",
            champs_identite_candidat=("no_panneau", "nuance"),
        )
        candidat_2 = next(r for r in resultat if r["no_panneau"] == "2")
        self.assertEqual(candidat_2["voix"], 200)

    def test_aucune_ligne_pour_la_commune_leve(self):
        with self.assertRaises(CodeCommuneInvalide):
            agreger_long_vers_commune(_LIGNES_GENERAL, "99999", champs_totaux=("inscrits",))

    def test_id_election_inconnu_leve(self):
        lignes = [{"id_election": "2026_inconnu_t1", "code_commune": "35120", "inscrits": "1"}]
        with self.assertRaises(TypeElectionInconnu):
            agreger_long_vers_commune(lignes, "35120", champs_totaux=("inscrits",))

    def test_champs_totaux_et_identite_candidat_mutuellement_exclusifs(self):
        with self.assertRaises(ValueError):
            agreger_long_vers_commune(
                _LIGNES_GENERAL, "35120",
                champs_totaux=("inscrits",), champs_identite_candidat=("no_panneau",),
            )

    def test_tri_par_id_election_puis_code_insee(self):
        lignes = [
            {"id_election": "2026_muni_t1", "code_commune": "35120", "inscrits": "1"},
            {"id_election": "2001_cant_t1", "code_commune": "35120", "inscrits": "1"},
        ]
        resultat = agreger_long_vers_commune(lignes, "35120", champs_totaux=("inscrits",))
        self.assertEqual([r["id_election"] for r in resultat], ["2001_cant_t1", "2026_muni_t1"])


if __name__ == "__main__":
    unittest.main()
