"""Tests de profils_communes.py — upsert composite, écriture atomique, oubli de profil."""
import json
import os
import tempfile
import unittest

from rudi_commune_starterkit.profils_communes import (
    charger_profils,
    enregistrer_profil,
    oublier_profil,
)

_PROFIL_GEVEZE = {
    "code_insee": "35120", "nom": "Gévezé", "url_noeud": "https://noeud.fr",
    "usr": "alice", "mode_producteur": "commune", "organisation_par_jdd": None,
    "contact_email_commune": "mairie@geveze.fr", "url_portail": "https://portail.fr",
}


class TestChargerProfils(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.chemin = os.path.join(self._tmp.name, "profils.json")

    def test_fichier_absent_retourne_liste_vide(self):
        self.assertEqual(charger_profils(self.chemin), [])

    def test_json_corrompu_leve(self):
        with open(self.chemin, "w", encoding="utf-8") as f:
            f.write("{ceci n'est pas du json")
        with self.assertRaises(ValueError):
            charger_profils(self.chemin)

    def test_contenu_non_liste_leve(self):
        with open(self.chemin, "w", encoding="utf-8") as f:
            json.dump({"pas": "une liste"}, f)
        with self.assertRaises(ValueError):
            charger_profils(self.chemin)


class TestEnregistrerProfil(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.chemin = os.path.join(self._tmp.name, "sous_dossier", "profils.json")

    def test_premier_enregistrement(self):
        enregistrer_profil(_PROFIL_GEVEZE, self.chemin)
        self.assertEqual(charger_profils(self.chemin), [_PROFIL_GEVEZE])

    def test_upsert_meme_commune_meme_noeud_remplace(self):
        enregistrer_profil(_PROFIL_GEVEZE, self.chemin)
        maj = {**_PROFIL_GEVEZE, "contact_email_commune": "nouveau@geveze.fr"}
        enregistrer_profil(maj, self.chemin)
        profils = charger_profils(self.chemin)
        self.assertEqual(len(profils), 1)
        self.assertEqual(profils[0]["contact_email_commune"], "nouveau@geveze.fr")

    def test_upsert_insensible_casse_et_slash_final_url(self):
        enregistrer_profil(_PROFIL_GEVEZE, self.chemin)
        variante = {**_PROFIL_GEVEZE, "url_noeud": "HTTPS://NOEUD.FR/"}
        enregistrer_profil(variante, self.chemin)
        self.assertEqual(len(charger_profils(self.chemin)), 1)

    def test_meme_commune_noeud_different_cree_un_second_profil(self):
        enregistrer_profil(_PROFIL_GEVEZE, self.chemin)
        autre_noeud = {**_PROFIL_GEVEZE, "url_noeud": "https://autre-noeud.fr"}
        enregistrer_profil(autre_noeud, self.chemin)
        self.assertEqual(len(charger_profils(self.chemin)), 2)

    def test_communes_differentes_coexistent(self):
        enregistrer_profil(_PROFIL_GEVEZE, self.chemin)
        autre_commune = {**_PROFIL_GEVEZE, "code_insee": "35238", "nom": "Rennes"}
        enregistrer_profil(autre_commune, self.chemin)
        self.assertEqual(len(charger_profils(self.chemin)), 2)

    def test_ecriture_atomique_pas_de_fichier_temporaire_residuel(self):
        enregistrer_profil(_PROFIL_GEVEZE, self.chemin)
        self.assertFalse(os.path.exists(f"{self.chemin}.tmp"))


class TestOublierProfil(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.chemin = os.path.join(self._tmp.name, "profils.json")

    def test_oubli_retire_le_profil(self):
        enregistrer_profil(_PROFIL_GEVEZE, self.chemin)
        trouve = oublier_profil("35120", "https://noeud.fr", self.chemin)
        self.assertTrue(trouve)
        self.assertEqual(charger_profils(self.chemin), [])

    def test_oubli_profil_absent_est_idempotent(self):
        self.assertFalse(oublier_profil("00000", "https://x.fr", self.chemin))

    def test_oubli_ne_touche_pas_les_autres_profils(self):
        enregistrer_profil(_PROFIL_GEVEZE, self.chemin)
        autre_commune = {**_PROFIL_GEVEZE, "code_insee": "35238", "nom": "Rennes"}
        enregistrer_profil(autre_commune, self.chemin)
        oublier_profil("35120", "https://noeud.fr", self.chemin)
        profils = charger_profils(self.chemin)
        self.assertEqual(len(profils), 1)
        self.assertEqual(profils[0]["code_insee"], "35238")


if __name__ == "__main__":
    unittest.main()
