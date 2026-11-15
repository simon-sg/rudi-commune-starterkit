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


class TestViderCommuneEtatAbsentMaisOrganisationDemandee(unittest.TestCase):
    """Bug réel (2026-11-08) : un 1er appel qui supprime tous les JDD vide l'état local
    — un 2e appel avec supprimer_organisation=True (ex. pour réessayer l'organisation
    une fois le JDD tiers bloquant traité) ne doit plus court-circuiter avant d'avoir
    essayé quoi que ce soit côté organisation."""

    def test_etat_absent_et_organisation_demandee_continue(self):
        org = {"organization_id": "org-1", "linked_producer_status": "DETACHED"}
        with mock.patch("rudi_commune_starterkit.vidage.charger_etat", return_value={}), \
             mock.patch("rudi_commune_starterkit.vidage.sauvegarder_etat") as m_save, \
             mock.patch("rudi_commune_starterkit.vidage.resoudre_commune", return_value=_GEVEZE), \
             mock.patch("rudi_commune_starterkit.vidage.toutes_metadonnees_rudi", return_value=[]), \
             mock.patch("rudi_commune_starterkit.vidage.organisation_existante", return_value=org), \
             mock.patch("rudi_commune_starterkit.vidage.supprimer_organisation_noeud", return_value=True):
            rapport = vidage.vider_commune(
                _CONF, "35120", supprimer_organisation=True, confirmer_fn=_toujours_confirmer,
            )
        self.assertEqual(rapport["organisation"], "supprimee")
        self.assertEqual(rapport["jdd_supprimes"], [])
        m_save.assert_not_called()

    def test_etat_absent_et_organisation_non_demandee_court_circuite_toujours(self):
        with mock.patch("rudi_commune_starterkit.vidage.charger_etat", return_value={}):
            rapport = vidage.vider_commune(_CONF, "35120", confirmer_fn=_toujours_confirmer)
        self.assertIn("Rien à supprimer", rapport["message"])
        self.assertIsNone(rapport["organisation"])

    def test_etat_absent_et_organisation_demandee_respecte_le_refus_de_confirmation(self):
        with mock.patch("rudi_commune_starterkit.vidage.charger_etat", return_value={}), \
             mock.patch("rudi_commune_starterkit.vidage.resoudre_commune") as m_resoudre:
            rapport = vidage.vider_commune(
                _CONF, "35120", supprimer_organisation=True, confirmer_fn=_toujours_refuser,
            )
        self.assertIn("Annulé", rapport["message"])
        m_resoudre.assert_not_called()


class TestViderCommuneSuppressionJdd(unittest.TestCase):
    def setUp(self):
        self.etat = {"lid-1": {"hash": "a"}, "lid-2": {"hash": "b"}}

    def test_succes_suppression_noeud(self):
        with mock.patch("rudi_commune_starterkit.vidage.charger_etat", return_value=dict(self.etat)), \
             mock.patch("rudi_commune_starterkit.vidage.sauvegarder_etat") as m_save, \
             mock.patch("rudi_commune_starterkit.vidage.global_id_pour_local_id",
                         side_effect=lambda conf, lid: f"g-{lid}"), \
             mock.patch("rudi_commune_starterkit.vidage.supprimer_dataset", return_value=True):
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
             mock.patch("rudi_commune_starterkit.vidage.supprimer_dataset") as m_sup:
            rapport = vidage.vider_commune(_CONF, "35120", confirmer_fn=_toujours_confirmer)
        self.assertEqual(set(rapport["jdd_supprimes"]), {"lid-1", "lid-2"})
        m_sup.assert_not_called()

    def test_echec_noeud_rapporte_et_garde_en_etat(self):
        with mock.patch("rudi_commune_starterkit.vidage.charger_etat", return_value=dict(self.etat)), \
             mock.patch("rudi_commune_starterkit.vidage.sauvegarder_etat") as m_save, \
             mock.patch("rudi_commune_starterkit.vidage.global_id_pour_local_id",
                         side_effect=lambda conf, lid: f"g-{lid}"), \
             mock.patch("rudi_commune_starterkit.vidage.supprimer_dataset",
                         side_effect=lambda conf, gid: gid != "g-lid-1"):
            rapport = vidage.vider_commune(_CONF, "35120", confirmer_fn=_toujours_confirmer)
        self.assertEqual(rapport["jdd_echecs"], ["lid-1"])
        self.assertEqual(rapport["jdd_supprimes"], ["lid-2"])
        etat_sauve = m_save.call_args[0][1]
        self.assertIn("lid-1", etat_sauve)
        self.assertNotIn("lid-2", etat_sauve)


class TestViderCommuneSuppressionOrganisation(unittest.TestCase):
    def setUp(self):
        self._base_patches = [
            mock.patch("rudi_commune_starterkit.vidage.charger_etat", return_value={"lid-1": {"hash": "a"}}),
            mock.patch("rudi_commune_starterkit.vidage.sauvegarder_etat"),
            mock.patch("rudi_commune_starterkit.vidage.global_id_pour_local_id", return_value="g-1"),
            mock.patch("rudi_commune_starterkit.vidage.supprimer_dataset", return_value=True),
            mock.patch("rudi_commune_starterkit.vidage.resoudre_commune", return_value=_GEVEZE),
        ]
        for p in self._base_patches:
            p.start()
            self.addCleanup(p.stop)

    @staticmethod
    def _confirmer_sauf_non_suivis(message: str, *, mot_attendu: str) -> bool:
        """Confirme tout sauf la proposition de suppression des JDD non suivis — pour
        tester le cas où l'utilisateur la refuse explicitement."""
        return "non suivis" not in message

    def test_refus_si_jdd_restants_sans_global_id_ni_local_id(self):
        """Un JDD restant sans global_id (jamais censé arriver, mais le nœud est une
        source externe) ne peut pas être proposé à la suppression — refusé directement,
        jamais de plantage."""
        with mock.patch(
            "rudi_commune_starterkit.vidage.toutes_metadonnees_rudi",
            return_value=[{"producer": {"organization_name": "Commune de Gévezé"}}],
        ), mock.patch("rudi_commune_starterkit.vidage.organisation_existante") as m_org:
            rapport = vidage.vider_commune(
                _CONF, "35120", supprimer_organisation=True, confirmer_fn=_toujours_confirmer,
            )
        self.assertEqual(rapport["organisation"], "refus_jdd_restants")
        self.assertEqual(rapport["jdd_tiers_echecs"], ["?"])
        m_org.assert_not_called()

    def test_jdd_restant_propose_puis_refuse_par_lutilisateur(self):
        """Bug réel (2026-11-08, nœud source partagé) : un JDD référençant encore
        l'organisation mais publié par un autre outil (ex. moissonneuse-batteuse, même
        nœud local, ou un test manuel) peut n'avoir aucun local_id (champ optionnel du
        schéma RUDI) — ne doit plus planter (repli sur global_id), et sa suppression est
        désormais proposée plutôt que de bloquer sans recours. Ici l'utilisateur refuse
        cette proposition spécifique : toujours refusé, comme avant."""
        with mock.patch(
            "rudi_commune_starterkit.vidage.toutes_metadonnees_rudi",
            return_value=[{
                "global_id": "g-sans-local-id",
                "producer": {"organization_name": "Commune de Gévezé"},
            }],
        ), mock.patch("rudi_commune_starterkit.vidage.organisation_existante") as m_org, \
             mock.patch("rudi_commune_starterkit.vidage.supprimer_dataset") as m_sup_noeud:
            rapport = vidage.vider_commune(
                _CONF, "35120", supprimer_organisation=True,
                confirmer_fn=self._confirmer_sauf_non_suivis,
            )
        self.assertEqual(rapport["organisation"], "refus_jdd_restants")
        self.assertIn("g-sans-local-id", rapport["message"])
        # supprimer_dataset est bien appelé une fois pour le JDD suivi (lid-1 -> g-1,
        # boucle principale) mais jamais pour l'orphelin refusé.
        self.assertNotIn(mock.call(_CONF, "g-sans-local-id"), m_sup_noeud.call_args_list)
        m_org.assert_not_called()

    def test_jdd_restant_propose_et_supprime_avec_succes_puis_continue(self):
        """L'utilisateur accepte la proposition : le JDD non suivi est supprimé (le
        relais portail suit automatiquement) et le traitement de l'organisation
        continue normalement."""
        with mock.patch(
            "rudi_commune_starterkit.vidage.toutes_metadonnees_rudi",
            return_value=[{
                "global_id": "g-sans-local-id", "resource_title": "Test manuel",
                "producer": {"organization_name": "Commune de Gévezé"},
            }],
        ), mock.patch("rudi_commune_starterkit.vidage.organisation_existante", return_value=None), \
             mock.patch("rudi_commune_starterkit.vidage.supprimer_dataset", return_value=True) as m_sup_noeud:
            rapport = vidage.vider_commune(
                _CONF, "35120", supprimer_organisation=True, confirmer_fn=_toujours_confirmer,
            )
        self.assertEqual(rapport["organisation"], "deja_absente")
        self.assertEqual(rapport["jdd_tiers_supprimes"], ["g-sans-local-id"])
        self.assertEqual(rapport["jdd_tiers_echecs"], [])
        m_sup_noeud.assert_any_call(_CONF, "g-sans-local-id")

    def test_jdd_restant_propose_et_echec_de_suppression_refuse(self):
        """L'utilisateur accepte, mais la suppression échoue réellement (ex. réseau) :
        refus de toucher l'organisation, message distinct de la simple détection."""
        with mock.patch(
            "rudi_commune_starterkit.vidage.toutes_metadonnees_rudi",
            return_value=[{
                "global_id": "g-sans-local-id",
                "producer": {"organization_name": "Commune de Gévezé"},
            }],
        ), mock.patch("rudi_commune_starterkit.vidage.organisation_existante") as m_org, \
             mock.patch("rudi_commune_starterkit.vidage.supprimer_dataset", return_value=False):
            rapport = vidage.vider_commune(
                _CONF, "35120", supprimer_organisation=True, confirmer_fn=_toujours_confirmer,
            )
        self.assertEqual(rapport["organisation"], "refus_jdd_restants")
        self.assertEqual(rapport["jdd_tiers_echecs"], ["g-sans-local-id"])
        self.assertIn("échec", rapport["message"])
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
             mock.patch("rudi_commune_starterkit.vidage.supprimer_organisation_noeud") as m_sup_noeud:
            rapport = vidage.vider_commune(
                _CONF, "35120", supprimer_organisation=True, confirmer_fn=_toujours_confirmer,
            )
        self.assertEqual(rapport["organisation"], "detachement_demande")
        m_det.assert_called_once_with(_CONF, "org-1")
        m_sup_noeud.assert_not_called()

    def test_linked_producer_valide_echec_demande_detachement_rapporte_lechec(self):
        """Bug réel corrigé le 2026-11-14 : le retour de demander_detachement_producteur()
        était ignoré — un échec (nœud injoignable, etc.) était rapporté comme un succès
        ("detachement_demande") alors que rien n'avait été demandé."""
        org = {"organization_id": "org-1", "linked_producer_status": "VALIDATED"}
        with mock.patch("rudi_commune_starterkit.vidage.toutes_metadonnees_rudi", return_value=[]), \
             mock.patch("rudi_commune_starterkit.vidage.organisation_existante", return_value=org), \
             mock.patch("rudi_commune_starterkit.vidage.demander_detachement_producteur",
                        return_value=False), \
             mock.patch("rudi_commune_starterkit.vidage.supprimer_organisation_noeud") as m_sup_noeud:
            rapport = vidage.vider_commune(
                _CONF, "35120", supprimer_organisation=True, confirmer_fn=_toujours_confirmer,
            )
        self.assertEqual(rapport["organisation"], "echec_demande_detachement")
        m_sup_noeud.assert_not_called()

    def test_detachement_en_cours_narrete_avant_de_toucher_au_noeud(self):
        """Bug réel rencontré le 2026-11-14 (test E2E automatisé, cf.
        NodeLinkedProducerStatus côté Java) : ``IN_PROGRESS``/``DETACH_IN_PROGRESS``
        (détachement demandé mais pas encore validé) n'est pas la même chose que
        ``DISENGAGED`` (détachement validé) — ne jamais nettoyer la copie nœud tant
        que ce détachement n'est pas validé."""
        for statut in ("IN_PROGRESS", "DETACH_IN_PROGRESS"):
            with self.subTest(statut=statut):
                org = {"organization_id": "org-1", "linked_producer_status": statut}
                with mock.patch("rudi_commune_starterkit.vidage.toutes_metadonnees_rudi", return_value=[]), \
                     mock.patch("rudi_commune_starterkit.vidage.organisation_existante", return_value=org), \
                     mock.patch("rudi_commune_starterkit.vidage.supprimer_organisation_noeud") as m_sup_noeud:
                    rapport = vidage.vider_commune(
                        _CONF, "35120", supprimer_organisation=True, confirmer_fn=_toujours_confirmer,
                    )
                self.assertEqual(rapport["organisation"], "attente_validation_detachement")
                m_sup_noeud.assert_not_called()

    def test_detachee_nettoie_directement_le_noeud(self):
        """Correction du 2026-11-15 : une fois le producteur détaché (ou jamais
        rattaché), ce socle ne demande plus l'archivage portail (identifiants PROVIDER
        du raccordement nœud↔portail qu'un agent municipal n'a jamais, voir la
        docstring de vider_commune()) — il nettoie directement la copie locale du
        nœud, sans étape intermédiaire ni appel portail."""
        org = {"organization_id": "org-1", "linked_producer_status": "DETACHED"}
        with mock.patch("rudi_commune_starterkit.vidage.toutes_metadonnees_rudi", return_value=[]), \
             mock.patch("rudi_commune_starterkit.vidage.organisation_existante", return_value=org), \
             mock.patch("rudi_commune_starterkit.vidage.supprimer_organisation_noeud", return_value=True) as m_sup_noeud:
            rapport = vidage.vider_commune(
                _CONF, "35120", supprimer_organisation=True, confirmer_fn=_toujours_confirmer,
            )
        self.assertEqual(rapport["organisation"], "supprimee")
        m_sup_noeud.assert_called_once_with(_CONF, "org-1")

    def test_detachee_echec_suppression_noeud_rapporte_lechec(self):
        org = {"organization_id": "org-1", "linked_producer_status": "DETACHED"}
        with mock.patch("rudi_commune_starterkit.vidage.toutes_metadonnees_rudi", return_value=[]), \
             mock.patch("rudi_commune_starterkit.vidage.organisation_existante", return_value=org), \
             mock.patch("rudi_commune_starterkit.vidage.supprimer_organisation_noeud", return_value=False):
            rapport = vidage.vider_commune(
                _CONF, "35120", supprimer_organisation=True, confirmer_fn=_toujours_confirmer,
            )
        self.assertEqual(rapport["organisation"], "echec_suppression_noeud")

    def test_statut_linked_producer_manquant_traite_comme_detache(self):
        # Pas VALIDATED -> on tente la suite (toute valeur autre que VALIDATED, y compris
        # absente, est traitée comme « pas/plus rattaché »).
        org = {"organization_id": "org-1"}
        with mock.patch("rudi_commune_starterkit.vidage.toutes_metadonnees_rudi", return_value=[]), \
             mock.patch("rudi_commune_starterkit.vidage.organisation_existante", return_value=org), \
             mock.patch("rudi_commune_starterkit.vidage.supprimer_organisation_noeud", return_value=True):
            rapport = vidage.vider_commune(
                _CONF, "35120", supprimer_organisation=True, confirmer_fn=_toujours_confirmer,
            )
        self.assertEqual(rapport["organisation"], "supprimee")


if __name__ == "__main__":
    unittest.main()
