"""Tests de datasets/_commun.py — local_id déterministe, pagination, simplification."""
import unittest
from unittest import mock

from rudi_commune_starterkit.datasets._commun import (
    RECHERCHE_ENTREPRISES_API,
    contacts_pour_producer,
    date_plus_recente_entreprises,
    geography_pour_commune,
    lignes_csv_entreprises,
    local_id_jdd,
    recherche_entreprises,
    simplifier_resultat_entreprise,
)

_CONTOUR_GEVEZE = {
    "type": "Polygon",
    "coordinates": [[
        [-1.75, 48.20], [-1.70, 48.20], [-1.70, 48.24], [-1.75, 48.24], [-1.75, 48.20],
    ]],
}


class TestGeographyPourCommune(unittest.TestCase):
    def test_contour_present_retourne_une_bounding_box(self):
        commune = {"nom": "Gévezé", "code_insee": "35120", "contour": _CONTOUR_GEVEZE}
        geography = geography_pour_commune(commune)
        self.assertEqual(geography, {"bounding_box": {
            "west_longitude": -1.75, "east_longitude": -1.70,
            "south_latitude": 48.20, "north_latitude": 48.24,
        }})

    def test_contour_absent_retourne_none(self):
        commune = {"nom": "Gévezé", "code_insee": "35120"}
        self.assertIsNone(geography_pour_commune(commune))

    def test_contour_none_retourne_none(self):
        commune = {"nom": "Gévezé", "code_insee": "35120", "contour": None}
        self.assertIsNone(geography_pour_commune(commune))

_RESULTAT_BRUT = {
    "siren": "775685506",
    "nom_complet": "GROUPE SOS JEUNESSE",
    "sigle": None,
    "activite_principale": "88.99B",
    "categorie_entreprise": "ETI",
    "tranche_effectif_salarie": "51",
    "date_creation": "1900-01-01",
    "etat_administratif": "A",
    "nature_juridique": "9220",
    "dirigeants": [{"nom": "Dupont", "date_de_naissance": "1970-01-01"}],
    "finances": {"ca": 1000000},
    "matching_etablissements": [
        {
            "siret": "35600000005434",
            "adresse": "2 RUE DE RENNES 35850 GEVEZE",
            "code_postal": "35850",
            "libelle_commune": "GEVEZE",
            "est_siege": False,
            "activite_principale": "53.10Z",
            "etat_administratif": "A",
        }
    ],
}


def _reponse_page(resultats, page, total_pages):
    r = mock.Mock()
    r.raise_for_status = mock.Mock()
    r.json.return_value = {"results": resultats, "page": page, "total_pages": total_pages}
    return r


class TestLocalIdJdd(unittest.TestCase):
    def test_deterministe(self):
        a = local_id_jdd("entreprises", "35120")
        b = local_id_jdd("entreprises", "35120")
        self.assertEqual(a, b)

    def test_independant_du_mode_producer(self):
        # Rappel du plan : local_id ne doit JAMAIS dépendre du mode producer — ce test
        # documente que la fonction ne prend même pas ce paramètre, par construction.
        a = local_id_jdd("entreprises", "35120")
        self.assertEqual(a, local_id_jdd("entreprises", "35120"))

    def test_differe_selon_cle_ou_code_insee(self):
        a = local_id_jdd("entreprises", "35120")
        b = local_id_jdd("associations", "35120")
        c = local_id_jdd("entreprises", "35238")
        self.assertNotEqual(a, b)
        self.assertNotEqual(a, c)


class TestContactsPourProducer(unittest.TestCase):
    _COMMUNE = {"nom": "Gévezé"}

    def test_mode_source_donne_seulement_le_contact_source(self):
        # entreprises.py -> contact curé confirmé (v3, Axe 2) : Support APIM / INSEE.
        producer = {"organization_name": "INSEE"}
        contacts = contacts_pour_producer("entreprises", producer, self._COMMUNE)
        self.assertEqual(len(contacts), 1)
        self.assertEqual(contacts[0]["contact_name"], "Support APIM")
        self.assertTrue(contacts[0]["email"])

    def test_mode_commune_contient_aussi_le_contact_source(self):
        producer = {"organization_name": "Commune de Gévezé"}
        contacts = contacts_pour_producer(
            "entreprises", producer, self._COMMUNE, email_commune="mairie@geveze.fr",
        )
        self.assertEqual(
            contacts[0], {"contact_name": "Commune de Gévezé", "email": "mairie@geveze.fr"},
        )
        self.assertEqual(len(contacts), 2)
        self.assertEqual(contacts[1]["contact_name"], "Support APIM")

    def test_mode_commune_sans_email_commune_retombe_sur_la_source(self):
        # Pas d'email_commune (ex. deliberations.py, producteur toujours la commune) :
        # pas de contact commune explicite ici, publier_dataset() gère son repli
        # générique ; seul le contact source apparaît s'il y en a un.
        producer = {"organization_name": "Commune de Gévezé"}
        contacts = contacts_pour_producer("entreprises", producer, self._COMMUNE)
        self.assertEqual(
            contacts, [{"contact_name": "Support APIM", "email": "support-apim@insee.fr"}],
        )

    def test_deliberations_mode_commune_pas_de_contact_source(self):
        # DELIBERATIONS n'a pas d'entrée dans organisations.ORGANISATIONS (producteur
        # toujours la commune) -> producteur_reel() lève KeyError -> pas de 2e contact.
        producer = {"organization_name": "Commune de Gévezé"}
        contacts = contacts_pour_producer(
            "deliberations", producer, self._COMMUNE, email_commune="mairie@geveze.fr",
        )
        self.assertEqual(
            contacts, [{"contact_name": "Commune de Gévezé", "email": "mairie@geveze.fr"}],
        )

    def test_mode_par_jdd_jdd_source_ignore_email_commune_dun_autre_jdd(self):
        # Bug latent corrigé : un JDD resté en mode source ne doit PAS récupérer le
        # contact commune simplement parce qu'un email_commune est fourni au run (cas
        # d'un run --organisation-par-jdd mixte).
        producer = {"organization_name": "INSEE"}
        contacts = contacts_pour_producer(
            "entreprises", producer, self._COMMUNE, email_commune="mairie@geveze.fr",
        )
        self.assertEqual(len(contacts), 1)
        self.assertEqual(contacts[0]["contact_name"], "Support APIM")

    def test_contact_curate_confirme_remplace_le_repli_generique(self):
        # v3, Axe 2 : adresses -> contact curé confirmé (Équipe BAN).
        producer = {"organization_name": "DINUM / ANCT / IGN"}
        contacts = contacts_pour_producer("adresses", producer, self._COMMUNE)
        self.assertEqual(
            contacts, [{"contact_name": "Équipe BAN", "email": "adresse@data.gouv.fr"}],
        )

    def test_contact_curate_a_confirmer_retombe_sur_le_repli_generique(self):
        # eau_potable : contact_statut="a_confirmer" (introuvable malgré recherche) ->
        # jamais traité comme confirmé, repli générique habituel (nom du producteur réel
        # curé, organisations.ORGANISATIONS[EAU_POTABLE] -> ARS).
        producer = {"organization_name": "ARS"}
        contacts = contacts_pour_producer("eau_potable", producer, self._COMMUNE)
        self.assertEqual(len(contacts), 1)
        self.assertTrue(contacts[0]["email"].endswith("@example.org"))

    def test_contact_curate_absent_retombe_sur_le_repli_generique(self):
        # marches_publics n'a pas d'entrée curée (contact dynamique via contact_points,
        # résolu ailleurs) -> contacts_pour_producer() retombe sur le repli générique.
        producer = {"organization_name": "Ministère de l'Économie et des Finances"}
        contacts = contacts_pour_producer("marches_publics", producer, self._COMMUNE)
        self.assertEqual(contacts[0]["contact_name"], "Ministère de l'Économie et des Finances")


class TestRechercheEntreprises(unittest.TestCase):
    def test_une_seule_page(self):
        session = mock.Mock()
        session.get.return_value = _reponse_page([_RESULTAT_BRUT], 1, 1)
        resultats = recherche_entreprises("35120", session_http=session)
        self.assertEqual(len(resultats), 1)
        session.get.assert_called_once()
        args, kwargs = session.get.call_args
        self.assertEqual(args[0], f"{RECHERCHE_ENTREPRISES_API}/search")
        self.assertEqual(kwargs["params"]["code_commune"], "35120")
        self.assertEqual(kwargs["params"]["page"], 1)

    def test_pagine_jusqu_a_total_pages(self):
        session = mock.Mock()
        session.get.side_effect = [
            _reponse_page([_RESULTAT_BRUT], 1, 3),
            _reponse_page([_RESULTAT_BRUT], 2, 3),
            _reponse_page([_RESULTAT_BRUT], 3, 3),
        ]
        resultats = recherche_entreprises("35120", session_http=session)
        self.assertEqual(len(resultats), 3)
        self.assertEqual(session.get.call_count, 3)

    def test_plafond_pages_arrete_la_pagination(self):
        session = mock.Mock()
        session.get.return_value = _reponse_page([_RESULTAT_BRUT], 1, 1000)
        resultats = recherche_entreprises("35120", session_http=session, plafond_pages=2)
        self.assertEqual(session.get.call_count, 2)

    def test_transmet_nature_juridique_et_etat_administratif(self):
        session = mock.Mock()
        session.get.return_value = _reponse_page([], 1, 1)
        recherche_entreprises(
            "35120", nature_juridique="9220", etat_administratif="A", session_http=session,
        )
        _, kwargs = session.get.call_args
        self.assertEqual(kwargs["params"]["nature_juridique"], "9220")
        self.assertEqual(kwargs["params"]["etat_administratif"], "A")

    def test_echec_reseau_propage(self):
        session = mock.Mock()
        session.get.side_effect = RuntimeError("DNS")
        with self.assertRaises(RuntimeError):
            recherche_entreprises("35120", session_http=session)


class TestDatePlusRecenteEntreprises(unittest.TestCase):
    def test_prend_le_max_entre_plusieurs_resultats(self):
        resultats = [
            {"date_mise_a_jour": "2025-01-01T00:00:00"},
            {"date_mise_a_jour": "2026-10-01T09:00:00"},
        ]
        self.assertEqual(date_plus_recente_entreprises(resultats), "2026-10-01T09:00:00Z")

    def test_priorite_date_mise_a_jour_sur_les_champs_de_repli(self):
        resultat = {
            "date_mise_a_jour": "2026-11-10T06:00:00",
            "date_mise_a_jour_insee": "2099-01-01T00:00:00",
        }
        self.assertEqual(date_plus_recente_entreprises([resultat]), "2026-11-10T06:00:00Z")

    def test_repli_sur_date_mise_a_jour_insee_si_absente(self):
        resultat = {"date_mise_a_jour": None, "date_mise_a_jour_insee": "2025-12-05T15:39:38"}
        self.assertEqual(date_plus_recente_entreprises([resultat]), "2025-12-05T15:39:38Z")

    def test_repli_sur_date_mise_a_jour_rne_si_les_deux_premieres_absentes(self):
        resultat = {"date_mise_a_jour": None, "date_mise_a_jour_rne": "2026-03-04T16:22:49"}
        self.assertEqual(date_plus_recente_entreprises([resultat]), "2026-03-04T16:22:49Z")

    def test_none_si_aucune_date_exploitable(self):
        self.assertIsNone(date_plus_recente_entreprises([{"siren": "123"}]))

    def test_none_sur_liste_vide(self):
        self.assertIsNone(date_plus_recente_entreprises([]))


class TestSimplifierResultatEntreprise(unittest.TestCase):
    def test_ne_contient_aucune_donnee_personnelle(self):
        simplifie = simplifier_resultat_entreprise(_RESULTAT_BRUT)
        self.assertNotIn("dirigeants", simplifie)
        self.assertNotIn("finances", simplifie)

    def test_conserve_les_champs_utiles(self):
        simplifie = simplifier_resultat_entreprise(_RESULTAT_BRUT)
        self.assertEqual(simplifie["siren"], "775685506")
        self.assertEqual(simplifie["nom_complet"], "GROUPE SOS JEUNESSE")

    def test_aplati_l_etablissement_correspondant(self):
        simplifie = simplifier_resultat_entreprise(_RESULTAT_BRUT)
        self.assertEqual(len(simplifie["etablissements"]), 1)
        self.assertEqual(simplifie["etablissements"][0]["siret"], "35600000005434")

    def test_sans_etablissement_correspondant(self):
        simplifie = simplifier_resultat_entreprise({"siren": "123"})
        self.assertEqual(simplifie["etablissements"], [])


class TestLignesCsvEntreprises(unittest.TestCase):
    def test_une_ligne_par_etablissement_champs_entreprise_repetes(self):
        simplifie = simplifier_resultat_entreprise(_RESULTAT_BRUT)
        lignes = lignes_csv_entreprises([simplifie])
        self.assertEqual(len(lignes), 1)
        self.assertEqual(lignes[0]["siren"], "775685506")
        self.assertEqual(lignes[0]["etablissement_siret"], "35600000005434")

    def test_prefixe_evite_collision_de_noms_de_champs(self):
        # activite_principale/etat_administratif existent aux deux niveaux : le
        # préfixe etablissement_* doit garder les deux valeurs distinctes.
        simplifie = simplifier_resultat_entreprise(_RESULTAT_BRUT)
        lignes = lignes_csv_entreprises([simplifie])
        self.assertEqual(lignes[0]["activite_principale"], "88.99B")
        self.assertEqual(lignes[0]["etablissement_activite_principale"], "53.10Z")

    def test_sans_etablissement_une_seule_ligne_vide(self):
        simplifie = simplifier_resultat_entreprise({"siren": "123"})
        lignes = lignes_csv_entreprises([simplifie])
        self.assertEqual(len(lignes), 1)
        self.assertIsNone(lignes[0]["etablissement_siret"])

    def test_plusieurs_entreprises_plusieurs_etablissements(self):
        deux = simplifier_resultat_entreprise({
            **_RESULTAT_BRUT,
            "matching_etablissements": _RESULTAT_BRUT["matching_etablissements"] * 2,
        })
        lignes = lignes_csv_entreprises([deux])
        self.assertEqual(len(lignes), 2)


if __name__ == "__main__":
    unittest.main()
