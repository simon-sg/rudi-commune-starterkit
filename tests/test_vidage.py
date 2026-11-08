"""Tests de vidage.py — suppression de JDD/organisation, idempotence, fail-closed."""
import json
import os
import tempfile
import unittest
from unittest import mock

from rudi_commune_starterkit import vidage

_CONF = {"url": "https://noeud", "usr": "u", "pwd": "p", "url_portail": "https://portail"}
_GEVEZE = {"nom": "Gévezé", "code_insee": "35120"}


def _toujours_confirmer(*_a, **_k):
    return True


def _toujours_refuser(*_a, **_k):
    return False


class TestViderCommuneSansUrlPortail(unittest.TestCase):
    def test_refus_immediat_sans_mutation(self):
        with mock.patch("rudi_commune_starterkit.vidage.charger_etat") as m_etat:
            rapport = vidage.vider_commune({"url": "https://x", "usr": "u", "pwd": "p"}, "35120")
        self.assertIn("url_portail", rapport["message"])
        m_etat.assert_not_called()


class TestViderCommuneEtatAbsent(unittest.TestCase):
    def test_rien_a_faire(self):
        with mock.patch("rudi_commune_starterkit.vidage.charger_etat", return_value={}):
            rapport = vidage.vider_commune(_CONF, "35120")
        self.assertEqual(rapport["jdd_supprimes"], [])
        self.assertIn("Rien à supprimer", rapport["message"])


class TestViderCommuneConfirmation(unittest.TestCase):
    def test_annule_si_non_confirme(self):
        with mock.patch("rudi_commune_starterkit.vidage.charger_etat", return_value={"lid-1": {"hash": "x"}}), \
             mock.patch("rudi_commune_starterkit.vidage.sauvegarder_etat") as m_save:
            rapport = vidage.vider_commune(_CONF, "35120", confirmer_fn=_toujours_refuser)
        self.assertEqual(rapport["jdd_supprimes"], [])
        self.assertIn("Annulé", rapport["message"])
        m_save.assert_not_called()


class TestViderCommuneSuppressionJdd(unittest.TestCase):
    def setUp(self):
        self.etat = {"lid-1": {"hash": "a"}, "lid-2": {"hash": "b"}}

    def test_succes_noeud_et_portail(self):
        with mock.patch("rudi_commune_starterkit.vidage.charger_etat", return_value=dict(self.etat)), \
             mock.patch("rudi_commune_starterkit.vidage.sauvegarder_etat") as m_save, \
             mock.patch("rudi_commune_starterkit.vidage.global_id_pour_local_id",
                         side_effect=lambda conf, lid: f"g-{lid}"), \
             mock.patch("rudi_commune_starterkit.vidage.supprimer_dataset", return_value=True), \
             mock.patch("rudi_commune_starterkit.vidage.supprimer_dataset_portail", return_value=True):
            rapport = vidage.vider_commune(_CONF, "35120", confirmer_fn=_toujours_confirmer)
        self.assertEqual(set(rapport["jdd_supprimes"]), {"lid-1", "lid-2"})
        self.assertEqual(rapport["jdd_echecs"], [])
        m_save.assert_called_once()
        etat_sauve = m_save.call_args[0][1]
        self.assertEqual(etat_sauve, {})

    def test_deja_absent_du_noeud_traite_comme_succes(self):
        with mock.patch("rudi_commune_starterkit.vidage.charger_etat", return_value=dict(self.etat)), \
             mock.patch("rudi_commune_starterkit.vidage.sauvegarder_etat"), \
             mock.patch("rudi_commune_starterkit.vidage.global_id_pour_local_id", return_value=None), \
             mock.patch("rudi_commune_starterkit.vidage.supprimer_dataset") as m_sup, \
             mock.patch("rudi_commune_starterkit.vidage.supprimer_dataset_portail") as m_sup_p:
            rapport = vidage.vider_commune(_CONF, "35120", confirmer_fn=_toujours_confirmer)
        self.assertEqual(set(rapport["jdd_supprimes"]), {"lid-1", "lid-2"})
        m_sup.assert_not_called()
        m_sup_p.assert_not_called()

    def test_echec_noeud_rapporte_et_garde_en_etat(self):
        with mock.patch("rudi_commune_starterkit.vidage.charger_etat", return_value=dict(self.etat)), \
             mock.patch("rudi_commune_starterkit.vidage.sauvegarder_etat") as m_save, \
             mock.patch("rudi_commune_starterkit.vidage.global_id_pour_local_id",
                         side_effect=lambda conf, lid: f"g-{lid}"), \
             mock.patch("rudi_commune_starterkit.vidage.supprimer_dataset",
                         side_effect=lambda conf, gid: gid != "g-lid-1"), \
             mock.patch("rudi_commune_starterkit.vidage.supprimer_dataset_portail", return_value=True):
            rapport = vidage.vider_commune(_CONF, "35120", confirmer_fn=_toujours_confirmer)
        self.assertEqual(rapport["jdd_echecs"], ["lid-1"])
        self.assertEqual(rapport["jdd_supprimes"], ["lid-2"])
        etat_sauve = m_save.call_args[0][1]
        self.assertIn("lid-1", etat_sauve)
        self.assertNotIn("lid-2", etat_sauve)

    def test_portail_echec_bloque_meme_si_noeud_ok(self):
        with mock.patch("rudi_commune_starterkit.vidage.charger_etat", return_value={"lid-1": {"hash": "a"}}), \
             mock.patch("rudi_commune_starterkit.vidage.sauvegarder_etat"), \
             mock.patch("rudi_commune_starterkit.vidage.global_id_pour_local_id", return_value="g-1"), \
             mock.patch("rudi_commune_starterkit.vidage.supprimer_dataset", return_value=True), \
             mock.patch("rudi_commune_starterkit.vidage.supprimer_dataset_portail", return_value=False):
            rapport = vidage.vider_commune(_CONF, "35120", confirmer_fn=_toujours_confirmer)
        self.assertEqual(rapport["jdd_echecs"], ["lid-1"])


class TestViderCommuneSuppressionOrganisation(unittest.TestCase):
    def setUp(self):
        self._base_patches = [
            mock.patch("rudi_commune_starterkit.vidage.charger_etat", return_value={"lid-1": {"hash": "a"}}),
            mock.patch("rudi_commune_starterkit.vidage.sauvegarder_etat"),
            mock.patch("rudi_commune_starterkit.vidage.global_id_pour_local_id", return_value="g-1"),
            mock.patch("rudi_commune_starterkit.vidage.supprimer_dataset", return_value=True),
            mock.patch("rudi_commune_starterkit.vidage.supprimer_dataset_portail", return_value=True),
            mock.patch("rudi_commune_starterkit.vidage.resoudre_commune", return_value=_GEVEZE),
        ]
        for p in self._base_patches:
            p.start()
            self.addCleanup(p.stop)

    def test_refus_si_jdd_restants_sur_le_noeud(self):
        with mock.patch(
            "rudi_commune_starterkit.vidage.toutes_metadonnees_rudi",
            return_value=[{"local_id": "autre-lid", "producer": {"organization_name": "Commune de Gévezé"}}],
        ), mock.patch("rudi_commune_starterkit.vidage.organisation_existante") as m_org:
            rapport = vidage.vider_commune(
                _CONF, "35120", supprimer_organisation=True, confirmer_fn=_toujours_confirmer,
            )
        self.assertEqual(rapport["organisation"], "refus_jdd_restants")
        m_org.assert_not_called()

    def test_refus_si_jdd_restant_sans_local_id(self):
        """Bug réel (2026-11-08, nœud source partagé) : un JDD référençant encore
        l'organisation mais publié par un autre outil (ex. moissonneuse-batteuse, même
        nœud local) peut n'avoir aucun local_id (champ optionnel du schéma RUDI, pas
        garanti côté nœud) — ne doit plus planter, repli sur global_id (toujours
        présent) pour que le message reste identifiant."""
        with mock.patch(
            "rudi_commune_starterkit.vidage.toutes_metadonnees_rudi",
            return_value=[{
                "global_id": "g-sans-local-id",
                "producer": {"organization_name": "Commune de Gévezé"},
            }],
        ), mock.patch("rudi_commune_starterkit.vidage.organisation_existante") as m_org:
            rapport = vidage.vider_commune(
                _CONF, "35120", supprimer_organisation=True, confirmer_fn=_toujours_confirmer,
            )
        self.assertEqual(rapport["organisation"], "refus_jdd_restants")
        self.assertIn("g-sans-local-id", rapport["message"])
        m_org.assert_not_called()

    def test_organisation_deja_absente(self):
        with mock.patch("rudi_commune_starterkit.vidage.toutes_metadonnees_rudi", return_value=[]), \
             mock.patch("rudi_commune_starterkit.vidage.organisation_existante", return_value=None):
            rapport = vidage.vider_commune(
                _CONF, "35120", supprimer_organisation=True, confirmer_fn=_toujours_confirmer,
            )
        self.assertEqual(rapport["organisation"], "deja_absente")

    def test_linked_producer_valide_demande_detachement_et_sarrete(self):
        org = {"organization_id": "org-1", "linked_producer_status": "VALIDATED"}
        with mock.patch("rudi_commune_starterkit.vidage.toutes_metadonnees_rudi", return_value=[]), \
             mock.patch("rudi_commune_starterkit.vidage.organisation_existante", return_value=org), \
             mock.patch("rudi_commune_starterkit.vidage.demander_detachement_producteur") as m_det, \
             mock.patch("rudi_commune_starterkit.vidage.demander_suppression_organisation") as m_sup_org, \
             mock.patch("rudi_commune_starterkit.vidage.supprimer_organisation_noeud") as m_sup_noeud:
            rapport = vidage.vider_commune(
                _CONF, "35120", supprimer_organisation=True, confirmer_fn=_toujours_confirmer,
            )
        self.assertEqual(rapport["organisation"], "detachement_demande")
        m_det.assert_called_once_with(_CONF, "org-1")
        m_sup_org.assert_not_called()
        m_sup_noeud.assert_not_called()

    def test_detachee_supprime_portail_puis_noeud(self):
        org = {"organization_id": "org-1", "linked_producer_status": "DETACHED"}
        with mock.patch("rudi_commune_starterkit.vidage.toutes_metadonnees_rudi", return_value=[]), \
             mock.patch("rudi_commune_starterkit.vidage.organisation_existante", return_value=org), \
             mock.patch("rudi_commune_starterkit.vidage.demander_suppression_organisation", return_value=True) as m_sup_org, \
             mock.patch("rudi_commune_starterkit.vidage.supprimer_organisation_noeud", return_value=True) as m_sup_noeud:
            rapport = vidage.vider_commune(
                _CONF, "35120", supprimer_organisation=True, confirmer_fn=_toujours_confirmer,
            )
        self.assertEqual(rapport["organisation"], "supprimee")
        m_sup_org.assert_called_once_with(_CONF, "org-1")
        m_sup_noeud.assert_called_once_with(_CONF, "org-1")

    def test_echec_suppression_portail_narrete_avant_noeud(self):
        org = {"organization_id": "org-1", "linked_producer_status": "DETACHED"}
        with mock.patch("rudi_commune_starterkit.vidage.toutes_metadonnees_rudi", return_value=[]), \
             mock.patch("rudi_commune_starterkit.vidage.organisation_existante", return_value=org), \
             mock.patch("rudi_commune_starterkit.vidage.demander_suppression_organisation", return_value=False), \
             mock.patch("rudi_commune_starterkit.vidage.supprimer_organisation_noeud") as m_sup_noeud:
            rapport = vidage.vider_commune(
                _CONF, "35120", supprimer_organisation=True, confirmer_fn=_toujours_confirmer,
            )
        self.assertEqual(rapport["organisation"], "echec_suppression_portail")
        m_sup_noeud.assert_not_called()

    def test_statut_linked_producer_manquant_traite_comme_detache(self):
        # Pas VALIDATED -> on tente la suppression (toute valeur autre que VALIDATED,
        # y compris absente, est traitée comme « pas/plus rattaché »).
        org = {"organization_id": "org-1"}
        with mock.patch("rudi_commune_starterkit.vidage.toutes_metadonnees_rudi", return_value=[]), \
             mock.patch("rudi_commune_starterkit.vidage.organisation_existante", return_value=org), \
             mock.patch("rudi_commune_starterkit.vidage.demander_suppression_organisation", return_value=True), \
             mock.patch("rudi_commune_starterkit.vidage.supprimer_organisation_noeud", return_value=True):
            rapport = vidage.vider_commune(
                _CONF, "35120", supprimer_organisation=True, confirmer_fn=_toujours_confirmer,
            )
        self.assertEqual(rapport["organisation"], "supprimee")


if __name__ == "__main__":
    unittest.main()
