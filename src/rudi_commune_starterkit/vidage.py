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
    demander_detachement_producteur,
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
    chemin_etat: str | None = None,
    supprimer_organisation: bool = False,
    confirmer_fn=confirmer,
) -> dict:
    """Supprime les JDD de ``code_insee`` connus de l'état local (nœud + portail), puis
    l'organisation de la commune si ``supprimer_organisation`` et que plus aucun JDD du
    nœud ne la référence.

    Retourne un rapport ``dict`` : ``jdd_supprimes``/``jdd_echecs`` (listes de
    ``local_id``, les JDD connus de l'état local), ``jdd_tiers_supprimes``/
    ``jdd_tiers_echecs`` (listes de ``local_id``/``global_id``, les JDD **non suivis**
    par ce socle mais référençant l'organisation — proposés à la suppression
    séparément, uniquement si ``supprimer_organisation``), ``organisation`` (``None`` si
    non demandé, sinon un statut parmi ``"supprimee"``/``"deja_absente"``/
    ``"detachement_demande"``/``"refus_jdd_restants"``/
    ``"attente_suppression_portail_manuelle"``/``"echec_suppression_noeud"``) et
    ``message`` (texte explicatif, toujours renseigné sauf succès silencieux).
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
    if organisation.get("linked_producer_status") == "VALIDATED":
        demander_detachement_producteur(conf, organization_id)
        rapport["organisation"] = "detachement_demande"
        rapport["message"] = (
            f"Détachement du producteur « {nom_org_commune} » demandé — relancer une "
            "fois validé par l'animateur du portail."
        )
        return rapport

    # Pas d'appel automatisé à demander_suppression_organisation() : la suppression
    # d'une organisation côté portail (Strukture, OrganizationServiceImpl.
    # deleteOrganization) exige un rôle PROVIDER applicatif — contrairement à la
    # création/au détachement, il n'existe aucun relais nœud pour cette opération
    # précise (seuls les actes "attach"/"detach"/"has_task" existent côté nœud), et
    # aucun compte ROBOT séparé n'a jamais existé pour ce socle (testé 3 façons,
    # toujours 401 — voir mémoire project_rudi_organisation_validation_workflow).
    # Seul l'animateur du portail (l'utilisateur lui-même) peut la supprimer, dans
    # l'UI Strukture — mot de confirmation distinct de SUPPRIMER pour qu'un lancement
    # scriptable habituel (--confirmer SUPPRIMER) ne puisse jamais prétendre
    # faussement que cette action manuelle a eu lieu.
    if not confirmer_fn(
        f"Organisation « {nom_org_commune} » détachée. Sa suppression côté portail "
        "(Strukture) nécessite ton accès animateur — à faire toi-même dans l'UI "
        "Strukture. Une fois cette suppression portail faite, retape "
        "SUPPRIME_PORTAIL pour nettoyer aussi la copie locale du nœud.",
        mot_attendu="SUPPRIME_PORTAIL",
    ):
        rapport["organisation"] = "attente_suppression_portail_manuelle"
        rapport["message"] = (
            f"Organisation « {nom_org_commune} » détachée, suppression portail "
            "manuelle non confirmée — copie locale du nœud conservée (pas "
            "d'orpheline créée). Supprime-la toi-même dans l'UI Strukture, puis "
            "relance en confirmant SUPPRIME_PORTAIL."
        )
        return rapport

    ok_noeud = supprimer_organisation_noeud(conf, organization_id)
    if not ok_noeud:
        rapport["organisation"] = "echec_suppression_noeud"
        rapport["message"] = (
            f"Organisation « {nom_org_commune} » supprimée côté portail (confirmé "
            "manuellement), échec de la suppression côté nœud."
        )
        return rapport

    rapport["organisation"] = "supprimee"
    rapport["message"] = f"Organisation « {nom_org_commune} » supprimée (portail + nœud)."
    return rapport


__all__ = ["vider_commune"]
