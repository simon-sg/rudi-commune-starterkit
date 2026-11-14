"""« Vider une commune » — supprime les JDD publiés par ce socle (nœud + portail), avec
suppression de l'organisation de la commune en option.

**Un seul appel par JDD, pas deux** : ``supprimer_dataset()`` (nœud) suffit — confirmé
par le code source du nœud (2026-11-08,
``rudi-catalog/genericController.js::deleteSingleObject``) que la suppression nœud
déclenche déjà, automatiquement et avec sa propre identité, le relais de suppression
portail (Kalim) — exactement le même principe que le relais de
``demander_creation_organisation()``/``demander_detachement_producteur()``. Un appel
direct au portail (``supprimer_dataset_portail()``, écarté ici) nécessiterait un vrai
compte ROBOT enregistré côté ACL du portail, que ce socle n'a jamais eu besoin d'avoir.

**Pas de journal persistant** : le nœud/portail est la source de vérité, la reprise se
fait en redemandant simplement l'état courant à chaque appel — une suppression déjà
faite répond ``404`` côté nœud, traité comme un succès par
``rudi_harvest_toolkit.rudi_client.supprimer_dataset()``/``supprimer_organisation()``,
pas besoin d'un fichier séparé pour savoir où on en est.

**Source de la liste à supprimer** : le fichier d'état local de ce socle
(``.etat_rudi_commune_starterkit/<code_insee>.json``), pas une liste reconstruite depuis
le nœud — si l'état est absent *et* que l'organisation n'est pas demandée, il n'y a rien
à faire ici (republier normalement reconstituera l'état si besoin, pas de mode de
reconstruction spécial). Avec ``supprimer_organisation=True``, un état absent ne
raccourcit **pas** l'appel : l'organisation peut légitimement être la seule chose encore
à traiter (ex. tous les JDD déjà supprimés lors d'un appel précédent, suppression
d'organisation elle-même refusée à ce moment-là par un JDD tiers encore présent sur le
nœud — un second appel, une fois ce JDD traité, doit pouvoir réessayer l'organisation
seule).

Zéro dépendance vers ``cli.py`` : ``cli.py`` importe ce module, jamais l'inverse.
"""

from __future__ import annotations

from rudi_harvest_toolkit.commune import (
    ArrondissementMunicipalError,
    CodeInseeInvalide,
    CommuneIntrouvableError,
    ErreurReseauCommune,
    resoudre_commune,
)
from rudi_harvest_toolkit.rudi_client import (
    EtatPortailIndisponibleError,
    demander_archivage_organisation,
    demander_detachement_producteur,
    etat_tache_organisation_portail,
    global_id_pour_local_id,
    supprimer_dataset,
    supprimer_organisation as supprimer_organisation_noeud,
    toutes_metadonnees_rudi,
)
from rudi_harvest_toolkit.state import charger_etat, sauvegarder_etat

from . import organisations
from .interaction import confirmer
from .resolution_noeud import organisation_existante


def vider_commune(
    conf: dict,
    code_insee: str,
    *,
    nom_commune: str | None = None,
    chemin_etat: str | None = None,
    supprimer_organisation: bool = False,
    confirmer_fn=confirmer,
) -> dict:
    """Supprime les JDD de ``code_insee`` connus de l'état local (nœud + portail), puis
    l'organisation de la commune si ``supprimer_organisation`` et que plus aucun JDD du
    nœud ne la référence.

    ``nom_commune`` (optionnel) : évite l'appel réseau à ``geo.api.gouv.fr`` pour
    déterminer le nom de l'organisation quand l'appelant le connaît déjà (ex. profil du
    registre local, qui stocke ``nom`` depuis sa résolution initiale) — le nom de
    l'organisation ne dépend que du nom de la commune, jamais du reste de la fiche
    ``geo.api.gouv.fr`` (voir :func:`organisations.organisation_commune`). Bug réel
    (2026-11-14) : sans ce paramètre, une coupure réseau transitoire bloquait tout le
    traitement de l'organisation d'une commune déjà connue localement, alors qu'aucun
    appel réseau n'était en réalité nécessaire pour cette partie. Sans lui, retombe sur
    :func:`resoudre_commune` comme avant (seul cas où il manque vraiment : mode
    scriptable sans profil enregistré).

    Retourne un rapport ``dict`` : ``jdd_supprimes``/``jdd_echecs`` (listes de
    ``local_id``, les JDD connus de l'état local), ``jdd_tiers_supprimes``/
    ``jdd_tiers_echecs`` (listes de ``local_id``/``global_id``, les JDD **non suivis**
    par ce socle mais référençant l'organisation — proposés à la suppression
    séparément, uniquement si ``supprimer_organisation``), ``organisation`` (``None`` si
    non demandé, sinon un statut parmi ``"supprimee"``/``"deja_absente"``/
    ``"detachement_demande"``/``"echec_demande_detachement"``/
    ``"attente_validation_detachement"``/``"refus_jdd_restants"``/``"archivage_demande"``/
    ``"attente_validation_archivage"``/``"echec_demande_archivage"``/
    ``"echec_suppression_noeud"``/``"etat_portail_indisponible"``) et ``message`` (texte
    explicatif, toujours renseigné sauf succès silencieux).

    La suppression d'organisation est désormais **entièrement automatisable**
    (confirmé de bout en bout le 2026-11-14) : détachement du producteur → validation
    animateur → demande d'archivage → validation animateur → nettoyage de la copie
    locale du nœud. Chaque étape nécessite un nouvel appel à cette fonction une fois
    l'étape précédente validée côté portail (pas de boucle d'attente ici — le plan
    d'ensemble, pas cette fonction, décide quand relancer).
    """
    chemin_etat = chemin_etat or f".etat_rudi_commune_starterkit/{code_insee}.json"
    rapport: dict = {
        "code_insee": code_insee, "jdd_supprimes": [], "jdd_echecs": [],
        "jdd_tiers_supprimes": [], "jdd_tiers_echecs": [],
        "organisation": None, "message": None,
    }

    # Refus explicite et immédiat, avant toute mutation — jamais de suppression
    # partielle silencieuse côté nœud seul (voir le plan, § 6).
    if not conf.get("url_portail"):
        rapport["message"] = (
            "conf['url_portail'] requis pour vider une commune (suppression côté "
            "portail nécessaire pour chaque JDD) — aucune suppression effectuée."
        )
        return rapport

    etat = charger_etat(chemin_etat)
    local_ids = list(etat.keys()) if etat else []
    if not local_ids and not supprimer_organisation:
        rapport["message"] = f"Rien à supprimer : aucun état local pour {code_insee} ({chemin_etat})."
        return rapport

    if local_ids:
        print(f"[vidage] {len(local_ids)} JDD trouvés dans l'état local pour {code_insee} :")
        for local_id in local_ids:
            print(f"  - {local_id}")
        message_confirmation = f"Supprimer {len(local_ids)} JDD de la commune {code_insee} (nœud + portail)."
    else:
        # État local déjà vide (ex. tout supprimé lors d'un appel précédent) mais
        # supprimer_organisation=True : l'organisation peut légitimement être la seule
        # chose qui reste à traiter — ne pas sauter la confirmation pour autant.
        message_confirmation = (
            f"Aucun JDD local pour {code_insee} — traiter uniquement l'organisation."
        )

    if not confirmer_fn(message_confirmation, mot_attendu="SUPPRIMER"):
        rapport["message"] = "Annulé (confirmation non obtenue)."
        return rapport

    for local_id in local_ids:
        global_id = global_id_pour_local_id(conf, local_id)
        if global_id is None:
            # Déjà absent du nœud (suppression précédente, ou jamais vraiment publié
            # malgré l'entrée locale) — rien à faire, traité comme un succès idempotent.
            rapport["jdd_supprimes"].append(local_id)
            etat.pop(local_id, None)
            continue

        if supprimer_dataset(conf, global_id):
            # Pas d'appel séparé au portail : confirmé par le code source du nœud
            # (rudi-catalog/genericController.js::deleteSingleObject) que cette
            # suppression déclenche déjà le relais portail automatiquement, avec
            # l'identité propre du nœud — supprimer_dataset_portail() (OAuth2 direct,
            # nécessite un vrai compte ROBOT portail) est redondante ici.
            rapport["jdd_supprimes"].append(local_id)
            etat.pop(local_id, None)
        else:
            rapport["jdd_echecs"].append(local_id)

    if local_ids:
        sauvegarder_etat(chemin_etat, etat)

    if not supprimer_organisation:
        return rapport

    if nom_commune is not None:
        commune = {"nom": nom_commune, "code_insee": code_insee}
    else:
        try:
            commune = resoudre_commune(code_insee)
        except (CodeInseeInvalide, ArrondissementMunicipalError, CommuneIntrouvableError,
                ErreurReseauCommune) as e:
            rapport["message"] = f"Organisation non traitée : impossible de résoudre la commune ({e})."
            return rapport

    nom_org_commune = organisations.organisation_commune(commune)["organization_name"]

    # .get("local_id") plutôt que d["local_id"] : le nœud héberge aussi des JDD d'autres
    # outils (ex. moissonneuse-batteuse, même nœud local partagé, ou un test manuel) qui
    # n'ont pas forcément ce champ — optionnel dans le schéma RUDI, contrairement à
    # global_id (toujours présent), seul identifiant garanti pour les supprimer.
    restants = [
        d for d in toutes_metadonnees_rudi(conf)
        if (d.get("producer") or {}).get("organization_name") == nom_org_commune
    ]
    if restants:
        print(f"[vidage] {len(restants)} JDD non suivis par ce socle référencent encore "
              f"« {nom_org_commune} » sur le nœud :")
        for d in restants:
            identifiant = d.get("local_id") or d.get("global_id", "?")
            titre = d.get("resource_title") or "(titre inconnu)"
            print(f"  - {identifiant} — {titre}")

        if not confirmer_fn(
            f"Supprimer ces {len(restants)} JDD non suivis (nœud + portail) pour "
            f"pouvoir traiter l'organisation « {nom_org_commune} ».",
            mot_attendu="SUPPRIMER",
        ):
            rapport["organisation"] = "refus_jdd_restants"
            rapport["message"] = (
                f"Suppression d'organisation refusée : {len(restants)} JDD non suivis "
                f"référencent encore « {nom_org_commune} » sur le nœud : " + ", ".join(
                    d.get("local_id") or d.get("global_id", "?") for d in restants
                ) + "."
            )
            return rapport

        for d in restants:
            global_id = d.get("global_id")
            identifiant = d.get("local_id") or global_id or "?"
            if not global_id:
                rapport["jdd_tiers_echecs"].append(identifiant)
                continue
            if supprimer_dataset(conf, global_id):
                rapport["jdd_tiers_supprimes"].append(identifiant)
            else:
                rapport["jdd_tiers_echecs"].append(identifiant)

        if rapport["jdd_tiers_echecs"]:
            rapport["organisation"] = "refus_jdd_restants"
            rapport["message"] = (
                f"Suppression d'organisation refusée : échec de la suppression de "
                f"{len(rapport['jdd_tiers_echecs'])} JDD non suivis référençant encore "
                f"« {nom_org_commune} » : {', '.join(rapport['jdd_tiers_echecs'])}."
            )
            return rapport

    organisation = organisation_existante(conf, nom_org_commune)
    if organisation is None:
        rapport["organisation"] = "deja_absente"
        rapport["message"] = f"Organisation « {nom_org_commune} » déjà absente du nœud."
        return rapport

    organization_id = organisation.get("organization_id")
    statut_producteur = organisation.get("linked_producer_status")
    if statut_producteur == "VALIDATED":
        if not demander_detachement_producteur(conf, organization_id):
            rapport["organisation"] = "echec_demande_detachement"
            rapport["message"] = (
                f"Demande de détachement du producteur « {nom_org_commune} » "
                "refusée par le nœud — voir le journal ci-dessus pour la raison "
                "exacte."
            )
            return rapport
        rapport["organisation"] = "detachement_demande"
        rapport["message"] = (
            f"Détachement du producteur « {nom_org_commune} » demandé — relancer une "
            "fois validé par l'animateur du portail."
        )
        return rapport

    # Bug réel rencontré le 2026-11-14 (test E2E automatisé) : un détachement déjà
    # demandé mais pas encore validé par l'animateur (``IN_PROGRESS``/
    # ``DETACH_IN_PROGRESS``, cf. NodeLinkedProducerStatus côté Java) n'est **pas** la
    # même chose qu'un détachement validé (``DISENGAGED``) — y foncer directement vers
    # une demande d'archivage fait échouer le portail en ``409 invalidStateException``
    # (« votre organisation est en cours de rattachement ou de détachement »). Ne
    # tenter l'archivage qu'une fois cette tâche ``linked-producer-process`` validée.
    if statut_producteur in ("IN_PROGRESS", "DETACH_IN_PROGRESS"):
        rapport["organisation"] = "attente_validation_detachement"
        rapport["message"] = (
            f"Détachement du producteur « {nom_org_commune} » déjà demandé, en "
            "attente de validation par l'animateur du portail — relancer une fois "
            "validé avant de pouvoir demander l'archivage."
        )
        return rapport

    # Détachement validé ou organisation jamais rattachée (``DISENGAGED``/
    # ``CANCELLED``/``DRAFT``/absent) : demander
    # l'archivage portail — confirmé de bout en bout le 2026-11-14 (identité PROVIDER
    # du nœud, pas de compte animateur requis) comme la vraie route fonctionnelle de
    # suppression d'une organisation côté portail (voir rudi-harvest-toolkit/README.md
    # § demander_archivage_organisation). Remplace l'ancienne étape manuelle dans l'UI
    # Strukture. Le nœud ne reflète JAMAIS cet archivage une fois validé (rapport
    # Method.DELETE non géré côté nœud, confirmé par le code source) — on doit donc lire
    # l'état réel côté portail pour savoir où on en est, plutôt que linked_producer_status
    # (qui ne change plus à partir d'ici).
    try:
        etat_portail = etat_tache_organisation_portail(conf, organization_id)
    except EtatPortailIndisponibleError as e:
        # Jamais traiter une erreur (réseau, auth, 401/500 transitoire) comme une
        # confirmation d'archivage : l'organisation peut très bien être toujours
        # vivante côté portail — supprimer_organisation_noeud() serait alors une
        # vraie perte de donnée, pas un nettoyage de copie obsolète.
        rapport["organisation"] = "etat_portail_indisponible"
        rapport["message"] = (
            f"Impossible de vérifier l'état de « {nom_org_commune} » côté portail "
            f"({e}) — rien n'a été supprimé, relancer plus tard."
        )
        return rapport
    if etat_portail is None:
        # Organisation disparue du portail : archivage déjà validé lors d'un appel
        # précédent — ne reste que le nettoyage de la copie locale du nœud.
        ok_noeud = supprimer_organisation_noeud(conf, organization_id)
        if not ok_noeud:
            rapport["organisation"] = "echec_suppression_noeud"
            rapport["message"] = (
                f"Organisation « {nom_org_commune} » archivée côté portail (confirmé), "
                "échec de la suppression côté nœud."
            )
            return rapport
        rapport["organisation"] = "supprimee"
        rapport["message"] = f"Organisation « {nom_org_commune} » supprimée (portail + nœud)."
        return rapport

    if etat_portail.get("status") == "PENDING":
        # Une tâche organization-process est déjà en attente (demande d'archivage
        # précédente non encore traitée) — ne jamais en redéposer une 2e : POST
        # /organizations/tasks ne vérifie pas lui-même l'absence d'une tâche en cours.
        rapport["organisation"] = "attente_validation_archivage"
        rapport["message"] = (
            f"Demande d'archivage de « {nom_org_commune} » déjà en attente de "
            "validation par l'animateur du portail — relancer une fois validée."
        )
        return rapport

    resultat_archivage = demander_archivage_organisation(conf, organization_id, nom_org_commune)
    if not resultat_archivage:
        rapport["organisation"] = "echec_demande_archivage"
        rapport["message"] = (
            f"Demande d'archivage refusée par le portail pour « {nom_org_commune} » — "
            "voir le journal ci-dessus pour la raison exacte (souvent : des JDD liés "
            "encore publiés côté portail, y compris des brouillons orphelins)."
        )
        return rapport

    rapport["organisation"] = "archivage_demande"
    rapport["message"] = (
        f"Demande d'archivage envoyée pour « {nom_org_commune} » — relancer une fois "
        "validée par l'animateur du portail, pour nettoyer aussi la copie locale du nœud."
    )
    return rapport


__all__ = ["vider_commune"]
