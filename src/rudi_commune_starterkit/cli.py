"""Assistant interactif + mode scriptable pour peupler un nœud RUDI à partir d'un code INSEE.

Deux modes, comme le reste de l'écosystème :

- **assistant** (par défaut, sans argument) : 9 étapes guidées (voir le plan,
  § Expérience CLI) — code INSEE, diagnostic de couverture structurelle, URL/
  identifiants du nœud, enregistrement optionnel (trousseau ou fichier en clair avec
  avertissement), test de connexion, choix du mode producteur (avec rapprochement des
  organisations déjà sur le nœud), mise à jour ou non des JDD déjà publiés, exécution.
- **scriptable** (dès qu'un flag est fourni, ex. ``--code-insee``) : aucun prompt, pensé
  pour cron/CI.

Les deux modes convergent sur :func:`executer_run`, le cœur partagé : résoudre la
commune, résoudre le producteur par JDD, boucler sur ``registre.MODULES``, décider de
republier via ``etat_hash``, publier via ``rudi_harvest_toolkit.publish``, construire le
rapport final et le code de sortie.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time

from rudi_harvest_toolkit.commune import (
    ArrondissementMunicipalError,
    CodeInseeInvalide,
    CommuneIntrouvableError,
    ErreurReseauCommune,
    resoudre_commune,
)
from rudi_harvest_toolkit.rudi_client import charger_conf_rudi, demander_creation_organisation
from rudi_harvest_toolkit.publish import publier_si_configue
from rudi_harvest_toolkit.state import charger_etat, sauvegarder_etat

from . import organisations, registre
from .description_commune import construire_description_commune
from .etat_hash import doit_republier, enregistrer_publication, hash_contenu_jdd
from .interaction import confirmer
from .profils_communes import charger_profils, enregistrer_profil, oublier_profil
from .resolution_noeud import (
    organisation_existante,
    resoudre_organisations_producteurs,
    tester_connexion_noeud,
)
from .resultat import StatutConnecteur
from .securite import (
    AbsenceTerminalError,
    TrousseauEnClairError,
    UrlNoeudNonSecurisee,
    ecrire_conf_fichier,
    email_suspect,
    email_valide,
    enregistrer_mot_de_passe_trousseau,
    lire_mot_de_passe,
    lire_mot_de_passe_trousseau,
    valider_url_noeud,
    verifier_permissions_conf,
)
from .vidage import vider_commune

# Cache Wikipédia partagé entre toutes les communes (pas à l'intérieur d'un
# dossier_sortie par commune, sinon le TTL de resumer_commune_wikipedia() ne sert à
# rien) — à la racine, à côté de ``.sortie_rudi_commune_starterkit/``.
DOSSIER_CACHE_WIKIPEDIA = ".cache_wikipedia"

EXIT_SUCCES = 0
EXIT_ECHECS_PARTIELS = 1
EXIT_ECHEC_TOTAL = 2
EXIT_EN_ATTENTE_VALIDATION = 3

CODE_REGION_BRETAGNE = "53"
MODES_PRODUCTEUR = ("source", "commune", "par-jdd")
_PAUSE_ENTRE_PUBLICATIONS_S = 2
CHEMIN_PROFILS_DEFAUT = os.path.join(".rudi_commune_starterkit", "profils.json")


# --------------------------------------------------------------------------------------
# Cœur partagé assistant / scriptable
# --------------------------------------------------------------------------------------


def resoudre_modes_par_jdd(
    organisation_producteur: str, organisation_par_jdd: dict | None,
) -> dict[str, str]:
    """Calcule le mode effectif (``"source"``/``"commune"``) par clé de JDD.

    - ``organisation_producteur`` ``"source"``/``"commune"`` : identique pour les 13 JDD.
    - ``"par-jdd"`` : ``organisation_par_jdd`` (schéma partiel, clés = sous-ensemble des
      JDD connus, valeurs ∈ {commune, source}) ; tout JDD absent retombe sur ``"source"``,
      annoncé par l'appelant (pas silencieusement ici).
    """
    cles = [m.CLE for m in registre.MODULES]
    if organisation_producteur in ("source", "commune"):
        return {cle: organisation_producteur for cle in cles}
    if organisation_producteur == "par-jdd":
        organisation_par_jdd = organisation_par_jdd or {}
        inconnues = set(organisation_par_jdd) - set(cles)
        if inconnues:
            raise ValueError(f"Clé(s) de JDD inconnue(s) dans organisation_par_jdd : {inconnues}")
        return {cle: organisation_par_jdd.get(cle, "source") for cle in cles}
    raise ValueError(f"organisation_producteur inconnu : {organisation_producteur!r}")


def diagnostic_couverture_structurelle(commune: dict) -> dict[str, str]:
    """Statuts connus **sans appel réseau supplémentaire** (ce que ``commune`` sait déjà) :
    seul cas structurel connu à ce stade, délibérations hors Bretagne."""
    diagnostic = {m.CLE: "a priori disponible" for m in registre.MODULES}
    if commune.get("code_region") != CODE_REGION_BRETAGNE:
        diagnostic[organisations.DELIBERATIONS] = "hors couverture structurelle (hors Bretagne)"
    return diagnostic


def _etat_organisation_commune(conf: dict, nom_org_commune: str) -> tuple[str, dict | None]:
    """Vérifie l'organisation de la commune sur le nœud — jamais les organisations
    source (INSEE, Mégalis...), référentiels partagés déjà censés exister.

    Retourne ``(etat, organisation)`` avec ``etat`` ∈ ``{"validee", "en_attente",
    "absente"}``. Fail-closed : tout statut manquant/inattendu est « en_attente »,
    jamais confondu avec « validee » (voir le plan, § garde-fou organisation — trois
    issues qui ne doivent jamais se confondre)."""
    organisation = organisation_existante(conf, nom_org_commune)
    if organisation is None:
        return "absente", None
    if (
        organisation.get("organization_status") == "VALIDATED"
        and organisation.get("linked_producer_status") == "VALIDATED"
    ):
        return "validee", organisation
    return "en_attente", organisation


def executer_run(
    *,
    commune: dict,
    conf: dict,
    modes_par_jdd: dict[str, str],
    contact_email_commune: str | None,
    forcer_maj: bool,
    only: set[str] | None,
    skip: set[str] | None,
    dry_run: bool,
    dossier_sortie: str,
    chemin_etat: str,
    confirmer_creation_organisation: bool = True,
) -> int:
    """Boucle sur les 13 JDD, publie, rapporte. Retourne le code de sortie.

    ``confirmer_creation_organisation`` : ``True`` (assistant interactif) demande
    confirmation avant de créer l'organisation de la commune si elle n'existe pas
    encore — c'est un acte sur un portail partagé, pas une création silencieuse.
    ``False`` (mode scriptable) la crée directement, cohérent avec l'absence de prompt.
    """
    code_insee = commune["code_insee"]
    modules = [
        m for m in registre.MODULES
        if (only is None or m.CLE in only) and (skip is None or m.CLE not in skip)
    ]

    # Résolu UNE SEULE FOIS par run (pas par module), avant producteurs_candidats, et
    # réutilisé aux deux sites qui construisent l'organisation de la commune — voir le
    # plan, § Axe 1 (sinon l'organisation créée sur le nœud et le producer publié avec
    # chaque JDD pourraient porter des résumés différents).
    description_commune = construire_description_commune(
        commune, dossier_cache=DOSSIER_CACHE_WIKIPEDIA,
        dossier_cache_rne=os.path.join(dossier_sortie, ".cache_rne"),
    )
    if description_commune["source"] == "repli_generique":
        print(f"[cli] [description] Wikipédia indisponible pour « {commune['nom']} » "
              "— description générique utilisée pour l'organisation de la commune.")

    producteurs_candidats = {}
    producteur_par_module: dict[str, dict] = {}
    for module in modules:
        producteur = organisations.resoudre_producer(
            module.CLE, modes_par_jdd[module.CLE], commune,
            description_commune=description_commune,
        )
        producteur_par_module[module.CLE] = producteur
        producteurs_candidats[producteur["organization_name"]] = producteur
    organisations_resolues, avertissement_rapprochement = resoudre_organisations_producteurs(
        conf, list(producteurs_candidats.values()),
    )
    if avertissement_rapprochement:
        print(f"[cli] {avertissement_rapprochement}")

    # Garde-fou organisation (voir le plan, § 2) : uniquement l'organisation de la
    # commune, jamais les organisations source — créer une organisation source
    # automatiquement serait une décision de gouvernance qui n'est pas la nôtre.
    organisation_en_attente = False
    organisation_creation_echouee = False
    jdd_bloques_par_organisation: set[str] = set()
    nom_org_commune = organisations.organisation_commune(commune)["organization_name"]
    modules_concernes = {
        cle for cle, p in producteur_par_module.items() if p["organization_name"] == nom_org_commune
    }
    if modules_concernes:
        try:
            etat_org, _organisation = _etat_organisation_commune(conf, nom_org_commune)
        except Exception as e:  # noqa: BLE001
            print(f"[cli] [organisation] Impossible de vérifier « {nom_org_commune} » "
                  f"({e}) — poursuite sans garde-fou, le nœud restera seul juge.")
            etat_org = "validee"  # ne bloque pas sur une panne de vérification annexe

        if etat_org == "absente":
            if dry_run:
                print(f"[cli] [dry-run] organisation « {nom_org_commune} » serait créée.")
                organisation_en_attente = True
            else:
                creer = not confirmer_creation_organisation or _demander_oui_non(
                    f"L'organisation « {nom_org_commune} » n'existe pas encore sur le "
                    "nœud. La créer", defaut=True,
                )
                if not creer:
                    print(f"[cli] Organisation « {nom_org_commune} » non créée (refus) — "
                          "les JDD qui en dépendent sont sautés ce run.")
                    organisation_en_attente = True
                else:
                    organisation = organisations.organisation_commune(
                        commune, description_commune=description_commune,
                    )
                    organisation_id = demander_creation_organisation(conf, organisation)
                    if organisation_id is None:
                        print(f"[cli] [organisation] Échec de la création de « {nom_org_commune} » "
                              "— ni « validée » ni « en attente », à corriger avant de relancer.")
                        organisation_creation_echouee = True
                    else:
                        print(f"[cli] Organisation « {nom_org_commune} » créée (id={organisation_id}), "
                              "en attente de validation par l'animateur du portail — relancer une "
                              "fois validée.")
                        organisation_en_attente = True
        elif etat_org == "en_attente":
            print(f"[cli] Organisation « {nom_org_commune} » en attente de validation par "
                  "l'animateur du portail — relancer une fois validée.")
            organisation_en_attente = True

        if organisation_en_attente or organisation_creation_echouee:
            jdd_bloques_par_organisation = modules_concernes

    etat = charger_etat(chemin_etat)
    rapport: dict[str, list[str]] = {
        "publié": [], "mis à jour": [], "sauté (inchangé)": [],
        "sauté (hors couverture)": [], "sauté (vide)": [],
        "sauté (organisation en attente)": [], "échec": [],
    }

    for module in modules:
        if module.CLE in jdd_bloques_par_organisation:
            if organisation_creation_echouee:
                rapport["échec"].append(module.CLE)
            else:
                rapport["sauté (organisation en attente)"].append(module.CLE)
            continue

        print(f"[cli] {module.CLE} ({module.TITRE})…")
        resultat = module.moissonner(
            code_insee, commune,
            dossier_sortie=dossier_sortie,
            mode_producer=modes_par_jdd[module.CLE],
            contact_email_commune=contact_email_commune,
            description_commune=description_commune,
        )

        if resultat.statut == StatutConnecteur.HORS_COUVERTURE:
            rapport["sauté (hors couverture)"].append(module.CLE)
            continue
        if resultat.statut == StatutConnecteur.VIDE:
            rapport["sauté (vide)"].append(module.CLE)
            continue
        if resultat.statut == StatutConnecteur.ECHEC:
            print(f"  [échec] {resultat.message}")
            rapport["échec"].append(module.CLE)
            continue

        # Le hash doit être calculé AVANT l'injection de organization_id ci-dessous :
        # ce champ dépend de l'état du nœud au moment du run (l'organisation existe-t-elle
        # déjà ?), pas du contenu réel du JDD — un run où elle existe déjà aurait sinon un
        # hash différent du run précédent qui l'a créée, sans aucun changement de contenu.
        local_id = resultat.rudi_metadata["local_id"]
        nouveau_hash = hash_contenu_jdd(resultat.rudi_metadata)
        deja_publie = local_id in etat
        if not doit_republier(etat, local_id, nouveau_hash, forcer_maj=forcer_maj):
            rapport["sauté (inchangé)"].append(module.CLE)
            continue

        nom_org = resultat.rudi_metadata["producer"]["organization_name"]
        organisation_id = organisations_resolues.get(nom_org, {}).get("organization_id")
        if organisation_id:
            resultat.rudi_metadata["producer"]["organization_id"] = organisation_id

        if dry_run:
            print("  [dry-run] publication simulée.")
            rapport["mis à jour" if deja_publie else "publié"].append(module.CLE)
            continue

        publie = publier_si_configue(conf, resultat.rudi_metadata, resultat.fichiers_filtres)
        if not publie:
            rapport["échec"].append(module.CLE)
            continue

        # Pause après chaque publication réussie : sendToPortal() est fire-and-forget
        # côté nœud (le PUT revient avant que le relais portail soit terminé) — des JDD
        # envoyés coup sur coup, qui plus est partageant le même producteur/contact (mode
        # commune), peuvent se faire concurrence côté Kalim et revenir en ERR-500 générique
        # (constaté en conditions réelles : 13/13 JDD refusés sans pause). Même mitigation
        # que moissonneuse-batteuse (``renvoyer_ressources_connues()``).
        time.sleep(_PAUSE_ENTRE_PUBLICATIONS_S)

        etat = enregistrer_publication(etat, local_id, nouveau_hash)
        rapport["mis à jour" if deja_publie else "publié"].append(module.CLE)

    if not dry_run:
        sauvegarder_etat(chemin_etat, etat)

    _afficher_rapport(rapport)

    # « En attente de validation » prend toujours le dessus sur un échec partiel —
    # règle fixe, pas une matrice à justifier cas par cas (voir le plan, § 2) : ce
    # n'est pas un échec, c'est un rendez-vous à reprendre une fois l'organisation
    # validée par l'animateur du portail.
    if organisation_en_attente:
        code = EXIT_EN_ATTENTE_VALIDATION
    elif rapport["échec"] and (rapport["publié"] or rapport["mis à jour"]):
        code = EXIT_ECHECS_PARTIELS
    elif rapport["échec"] and not (rapport["publié"] or rapport["mis à jour"]):
        code = EXIT_ECHEC_TOTAL
    else:
        code = EXIT_SUCCES

    if dry_run:
        if code != EXIT_SUCCES:
            print(f"[cli] [dry-run] code de sortie réel attendu : {code}.")
        return EXIT_SUCCES
    return code


def _afficher_rapport(rapport: dict[str, list[str]]) -> None:
    print("\n=== Rapport ===")
    for categorie, cles in rapport.items():
        if cles:
            print(f"  {categorie} : {', '.join(cles)}")


# --------------------------------------------------------------------------------------
# Assistant interactif
# --------------------------------------------------------------------------------------


def _demander(invite: str, *, defaut: str | None = None) -> str:
    suffixe = f" [{defaut}]" if defaut is not None else ""
    reponse = input(f"{invite}{suffixe} : ").strip()
    return reponse or (defaut or "")


def _demander_oui_non(invite: str, *, defaut: bool = False) -> bool:
    repli = "O/n" if defaut else "o/N"
    reponse = input(f"{invite} ({repli}) : ").strip().lower()
    if not reponse:
        return defaut
    return reponse in ("o", "oui", "y", "yes")


def _choisir_mode_producteur() -> tuple[str, dict | None]:
    """Étape « mode producteur » — factorisée pour être réutilisable aussi bien pour
    une nouvelle commune que pour corriger un profil repris du registre."""
    print("Qui doit apparaître comme producteur Rudi ?")
    print("  1) la commune pour tous les JDD")
    print("  2) le vrai organisme producteur pour chaque JDD (par défaut)")
    print("  3) choisir JDD par JDD")
    choix = _demander("Choix", defaut="2")
    organisation_par_jdd = None
    if choix == "1":
        organisation_producteur = "commune"
    elif choix == "3":
        organisation_producteur = "par-jdd"
        organisation_par_jdd = {}
        for module in registre.MODULES:
            if _demander_oui_non(f"  {module.CLE} : producteur = la commune", defaut=False):
                organisation_par_jdd[module.CLE] = "commune"
        chemin_export = _demander(
            "  Exporter cette correspondance pour un futur run (vide = ne pas exporter)",
            defaut="",
        )
        if chemin_export:
            with open(chemin_export, "w", encoding="utf-8") as f:
                json.dump(organisation_par_jdd, f, ensure_ascii=False, indent=2)
            print(f"  Correspondance exportée vers {chemin_export}.")
    else:
        organisation_producteur = "source"
    return organisation_producteur, organisation_par_jdd


def _demander_email_contact_commune(*, defaut: str | None = None) -> str:
    while True:
        contact_email_commune = _demander("Email de contact de la commune", defaut=defaut)
        if email_valide(contact_email_commune):
            avertissement = email_suspect(contact_email_commune)
            if avertissement:
                print(f"  [sécurité] Attention : {avertissement}")
            return contact_email_commune
        print("  Adresse email invalide.")


def _afficher_profil(profil: dict) -> None:
    print("Résumé du profil enregistré :")
    print(f"  Commune                : {profil['nom']} ({profil['code_insee']})")
    print(f"  Nœud                   : {profil['url_noeud']}")
    print(f"  Utilisateur            : {profil['usr']}")
    print(f"  Mode producteur        : {profil['mode_producteur']}")
    print(f"  Email contact commune  : {profil.get('contact_email_commune') or '(aucun)'}")
    print(f"  URL portail            : {profil.get('url_portail') or '(non renseignée)'}")


def _executer_depuis_profil(profil: dict, chemin_profils: str) -> int:
    """Reprend une commune déjà enregistrée : le mot de passe est résolu via le
    trousseau (clé ``(url_noeud, usr)``, jamais stocké dans le profil lui-même), le
    reste de la saisie est pré-rempli. Le registre n'est jamais une autorisation
    permanente — confirmation explicite avant de lancer quoi que ce soit."""
    print(f"\n→ Reprise de {profil['nom']} ({profil['code_insee']}) sur {profil['url_noeud']}\n")
    try:
        commune = resoudre_commune(profil["code_insee"])
    except (CodeInseeInvalide, ArrondissementMunicipalError, CommuneIntrouvableError) as e:
        print(f"  {e}")
        return EXIT_ECHEC_TOTAL
    except ErreurReseauCommune as e:
        print(f"  Erreur réseau : {e}")
        return EXIT_ECHEC_TOTAL

    url_noeud, usr = profil["url_noeud"], profil["usr"]
    try:
        pwd = lire_mot_de_passe_trousseau(url_noeud, usr)
    except TrousseauEnClairError as e:
        print(f"  {e}")
        pwd = None
    if pwd is None:
        print("  Mot de passe introuvable dans le trousseau pour ce profil.")
        try:
            pwd = lire_mot_de_passe(f"Mot de passe pour {usr}@{url_noeud} : ")
        except AbsenceTerminalError as e:
            print(f"  {e}")
            return EXIT_ECHEC_TOTAL

    conf = {"url": url_noeud, "usr": usr, "pwd": pwd}
    if profil.get("url_catalog"):
        conf["url_catalog"] = profil["url_catalog"]
    if profil.get("url_portail"):
        conf["url_portail"] = profil["url_portail"]

    organisation_producteur = profil["mode_producteur"]
    organisation_par_jdd = profil.get("organisation_par_jdd")
    contact_email_commune = profil.get("contact_email_commune")

    print()
    _afficher_profil(profil)
    while True:
        reponse = _demander(
            "Continuer, ou corriger un champ (contact/mode/portail)", defaut="continuer",
        ).strip().lower()
        if reponse in ("", "continuer", "o", "oui", "y", "yes"):
            break
        if reponse == "contact":
            contact_email_commune = _demander_email_contact_commune(defaut=contact_email_commune)
        elif reponse == "mode":
            organisation_producteur, organisation_par_jdd = _choisir_mode_producteur()
        elif reponse == "portail":
            profil["url_portail"] = _demander("URL du portail", defaut=profil.get("url_portail") or "") or None
            if profil["url_portail"]:
                conf["url_portail"] = profil["url_portail"]
        else:
            print("  Champ inconnu (contact/mode/portail).")

    print("\nTest de connexion au nœud…")
    if not tester_connexion_noeud(conf):
        print("  Échec : nœud injoignable ou identifiants invalides.")
        return EXIT_ECHEC_TOTAL
    print("  OK.\n")

    try:
        enregistrer_profil({
            **profil,
            "mode_producteur": organisation_producteur,
            "organisation_par_jdd": organisation_par_jdd,
            "contact_email_commune": contact_email_commune,
        }, chemin_profils)
    except ValueError as e:
        print(f"  [profils] Avertissement : profil non mis à jour ({e}).")

    modes_par_jdd = resoudre_modes_par_jdd(organisation_producteur, organisation_par_jdd)

    forcer_maj = _demander_oui_non(
        "Mettre à jour les JDD déjà publiés même sans changement détecté", defaut=False,
    )

    dossier_sortie = os.path.join(".sortie_rudi_commune_starterkit", commune["code_insee"])
    chemin_etat = os.path.join(".etat_rudi_commune_starterkit", f"{commune['code_insee']}.json")
    print()
    return executer_run(
        commune=commune, conf=conf, modes_par_jdd=modes_par_jdd,
        contact_email_commune=contact_email_commune, forcer_maj=forcer_maj,
        only=None, skip=None, dry_run=False,
        dossier_sortie=dossier_sortie, chemin_etat=chemin_etat,
    )


def _vider_commune_interactif(profil: dict, chemin_profils: str) -> int:
    """Vide une commune déjà enregistrée (JDD + organisation en option) — même
    résolution de ``conf`` que :func:`_executer_depuis_profil`, mais route vers
    :func:`vider_commune` au lieu de relancer la moisson."""
    print(f"\n→ Vidage de {profil['nom']} ({profil['code_insee']}) sur {profil['url_noeud']}\n")

    url_noeud, usr = profil["url_noeud"], profil["usr"]
    try:
        pwd = lire_mot_de_passe_trousseau(url_noeud, usr)
    except TrousseauEnClairError as e:
        print(f"  {e}")
        pwd = None
    if pwd is None:
        print("  Mot de passe introuvable dans le trousseau pour ce profil.")
        try:
            pwd = lire_mot_de_passe(f"Mot de passe pour {usr}@{url_noeud} : ")
        except AbsenceTerminalError as e:
            print(f"  {e}")
            return EXIT_ECHEC_TOTAL

    conf = {"url": url_noeud, "usr": usr, "pwd": pwd}
    if profil.get("url_catalog"):
        conf["url_catalog"] = profil["url_catalog"]
    if profil.get("url_portail"):
        conf["url_portail"] = profil["url_portail"]

    supprimer_organisation = _demander_oui_non(
        "Supprimer aussi l'organisation de la commune (si plus aucun JDD du nœud ne la "
        "référence)", defaut=False,
    )

    rapport = vider_commune(conf, profil["code_insee"], supprimer_organisation=supprimer_organisation)
    print(f"\n[cli] {rapport['message']}" if rapport["message"] else "\n[cli] Vidage terminé.")
    if rapport["jdd_supprimes"]:
        print(f"[cli]   JDD supprimés : {', '.join(rapport['jdd_supprimes'])}")
    if rapport["jdd_echecs"]:
        print(f"[cli]   JDD en échec : {', '.join(rapport['jdd_echecs'])}")
    if rapport["jdd_tiers_supprimes"]:
        print(f"[cli]   JDD non suivis supprimés : {', '.join(rapport['jdd_tiers_supprimes'])}")
    if rapport["jdd_tiers_echecs"]:
        print(f"[cli]   JDD non suivis en échec : {', '.join(rapport['jdd_tiers_echecs'])}")

    if rapport["organisation"] == "supprimee" and _demander_oui_non(
        f"Retirer {profil['nom']} du registre de communes", defaut=False,
    ):
        oublier_profil(profil["code_insee"], profil["url_noeud"], chemin_profils)
        print("  Profil retiré du registre.")

    # "attente_suppression_portail_manuelle" n'est pas un échec, comme
    # "detachement_demande" plus haut dans le flux : une attente normale d'une action
    # humaine (ici côté portail), pas un refus ni une erreur.
    if rapport["jdd_echecs"] or rapport["organisation"] in (
        "refus_jdd_restants", "echec_suppression_noeud",
    ):
        return EXIT_ECHECS_PARTIELS
    return EXIT_SUCCES


def executer_interactif() -> int:
    print("=== rudi-commune-starterkit — assistant ===\n")

    chemin_profils = CHEMIN_PROFILS_DEFAUT
    try:
        profils = charger_profils(chemin_profils)
    except ValueError as e:
        print(f"  {e}")
        return EXIT_ECHEC_TOTAL

    if profils:
        print("Communes déjà enregistrées :")
        for i, p in enumerate(profils, start=1):
            print(f"  {i}) {p['nom']} ({p['code_insee']}) — {p['url_noeud']}")
        print("  0) Nouvelle commune")
        while True:
            choix = _demander("Reprendre quelle commune", defaut="0")
            if choix in ("0", ""):
                break
            if choix.isdigit() and 1 <= int(choix) <= len(profils):
                profil = profils[int(choix) - 1]
                action = _demander(
                    "  1) Lancer la moisson  2) Vider cette commune — Action", defaut="1",
                )
                if action == "2":
                    return _vider_commune_interactif(profil, chemin_profils)
                return _executer_depuis_profil(profil, chemin_profils)
            print("  Choix invalide.")
        print()

    # Étape 1 : code INSEE
    while True:
        code_insee = _demander("Code INSEE de la commune")
        try:
            commune = resoudre_commune(code_insee)
            break
        except (CodeInseeInvalide, ArrondissementMunicipalError) as e:
            print(f"  {e}")
        except CommuneIntrouvableError as e:
            print(f"  {e}")
        except ErreurReseauCommune as e:
            print(f"  Erreur réseau : {e}")
            print("  L'outil a besoin du réseau pour résoudre un code INSEE — réessayer plus tard.")
    print(
        f"  → {commune['nom']} ({commune['code_insee']}), {commune['departement']} "
        f"({commune['region']}), population {commune.get('population') or '?'}\n"
    )

    # Étape 2 : diagnostic de couverture structurelle
    print("Diagnostic de couverture (structurel uniquement) :")
    for cle, statut in diagnostic_couverture_structurelle(commune).items():
        print(f"  - {cle} : {statut}")
    print()

    # Étape 3 : URL du nœud
    while True:
        url_noeud = _demander("URL du nœud RUDI (https://...)")
        try:
            url_noeud = valider_url_noeud(url_noeud)
            break
        except UrlNoeudNonSecurisee as e:
            print(f"  {e}")
            if _demander_oui_non("  Forcer quand même en http:// local (déconseillé)"):
                try:
                    url_noeud = valider_url_noeud(url_noeud, autoriser_http_local=True)
                    break
                except UrlNoeudNonSecurisee as e2:
                    print(f"  {e2}")
    url_catalog = _demander("URL catalogue (vide = déduite de l'URL du nœud)", defaut="") or None
    url_portail = _demander(
        "URL du portail (optionnelle — sans elle, --vider-commune restera "
        "indisponible pour cette commune)", defaut="",
    ) or None

    # Étape 4 : identifiants
    usr = _demander("Nom d'utilisateur")
    try:
        pwd = lire_mot_de_passe()
    except AbsenceTerminalError as e:
        print(f"  {e}")
        return EXIT_ECHEC_TOTAL

    conf = {"url": url_noeud, "usr": usr, "pwd": pwd}
    if url_catalog:
        conf["url_catalog"] = url_catalog
    if url_portail:
        conf["url_portail"] = url_portail

    # Étape 5 : enregistrement des identifiants
    if _demander_oui_non("Enregistrer ces identifiants pour la prochaine fois"):
        try:
            enregistrer_mot_de_passe_trousseau(url_noeud, usr, pwd)
            print("  Mot de passe enregistré dans le trousseau système.")
        except TrousseauEnClairError as e:
            print(f"  {e}")
            print("  Repli : fichier conf/rudi_node.json en clair (permissions 0600).")
            ecrire_conf_fichier(os.path.join("conf", "rudi_node.json"), conf)

    # Étape 6 : test de connexion
    print("\nTest de connexion au nœud…")
    if not tester_connexion_noeud(conf):
        print("  Échec : nœud injoignable ou identifiants invalides.")
        return EXIT_ECHEC_TOTAL
    print("  OK.\n")

    # Étape 7 : mode producteur
    organisation_producteur, organisation_par_jdd = _choisir_mode_producteur()

    modes_par_jdd = resoudre_modes_par_jdd(organisation_producteur, organisation_par_jdd)
    contact_email_commune = None
    if "commune" in modes_par_jdd.values():
        contact_email_commune = _demander_email_contact_commune()

    # Enregistrement du profil (hors mot de passe, resté au trousseau/fichier conf) —
    # c'est l'appel qui manquait pour fermer le bug « propose de se souvenir mais ne
    # relit jamais rien » : au prochain lancement, cette commune apparaît dans la liste
    # de l'étape 0 et toute cette saisie n'a plus besoin d'être refaite.
    try:
        enregistrer_profil({
            "code_insee": commune["code_insee"], "nom": commune["nom"],
            "url_noeud": url_noeud, "usr": usr,
            "url_catalog": url_catalog,
            "mode_producteur": organisation_producteur,
            "organisation_par_jdd": organisation_par_jdd,
            "contact_email_commune": contact_email_commune,
            "url_portail": url_portail,
        }, chemin_profils)
    except ValueError as e:
        print(f"  [profils] Avertissement : profil non enregistré ({e}).")

    # Étape 8 : mise à jour
    forcer_maj = _demander_oui_non(
        "Mettre à jour les JDD déjà publiés même sans changement détecté", defaut=False,
    )

    # Étape 9 : exécution
    dossier_sortie = os.path.join(".sortie_rudi_commune_starterkit", commune["code_insee"])
    chemin_etat = os.path.join(".etat_rudi_commune_starterkit", f"{commune['code_insee']}.json")
    print()
    return executer_run(
        commune=commune, conf=conf, modes_par_jdd=modes_par_jdd,
        contact_email_commune=contact_email_commune, forcer_maj=forcer_maj,
        only=None, skip=None, dry_run=False,
        dossier_sortie=dossier_sortie, chemin_etat=chemin_etat,
    )


# --------------------------------------------------------------------------------------
# Mode scriptable
# --------------------------------------------------------------------------------------


def _construire_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="rudi-commune-starterkit",
        description="Peuple un nœud RUDI avec le socle de JDD communaux à partir d'un code INSEE.",
    )
    parser.add_argument("--code-insee")
    parser.add_argument("--depuis-registre", action="store_true",
                        help="Résout nœud/identifiants/mode/contact depuis le registre "
                             "local (profils.py) plutôt que depuis les flags ci-dessous. "
                             "--url-noeud sert uniquement à désambiguïser si --code-insee "
                             "correspond à plusieurs profils (nœuds différents).")
    parser.add_argument("--url-noeud")
    parser.add_argument("--usr")
    parser.add_argument("--rudi-conf", help="Fichier JSON url/url_catalog/usr/pwd.")
    parser.add_argument("--utiliser-trousseau", action="store_true",
                        help="Lit le mot de passe dans le trousseau système (--url-noeud/--usr requis).")
    parser.add_argument("--organisation-producteur", choices=MODES_PRODUCTEUR, default="source")
    parser.add_argument("--organisation-par-jdd", help="Fichier JSON JDD -> commune|source.")
    parser.add_argument("--contact-commune", help="Email, obligatoire si au moins un JDD en mode commune.")
    parser.add_argument("--forcer-maj", action="store_true")
    parser.add_argument("--only", help="Clés de JDD séparées par des virgules.")
    parser.add_argument("--skip", help="Clés de JDD séparées par des virgules.")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--dossier-sortie")
    parser.add_argument("--etat", help="Fichier d'état JSON (hash par local_id).")
    parser.add_argument("--url-portail", help="Requis par --vider-commune/--supprimer-organisation.")
    parser.add_argument("--vider-commune", action="store_true",
                        help="Supprime les JDD de --code-insee déjà publiés par ce socle "
                             "(nœud + portail), au lieu de republier.")
    parser.add_argument("--supprimer-organisation", action="store_true",
                        help="Avec --vider-commune : supprime aussi l'organisation de la "
                             "commune si plus aucun JDD du nœud ne la référence.")
    parser.add_argument("--confirmer", metavar="SUPPRIMER",
                        help="Requis par --vider-commune en mode scriptable (jamais de "
                             "prompt sans terminal) : taper SUPPRIMER exactement.")
    return parser


def _resoudre_conf_scriptable(args: argparse.Namespace) -> dict:
    if args.rudi_conf:
        verifier_permissions_conf(args.rudi_conf)
        conf = charger_conf_rudi(args.rudi_conf)
        if not conf:
            raise ValueError(f"Fichier de conf introuvable ou illisible : {args.rudi_conf}")
        return conf

    if not args.url_noeud or not args.usr:
        raise ValueError(
            "--url-noeud et --usr sont requis sans --rudi-conf (mode scriptable, "
            "aucune saisie interactive)."
        )
    url_noeud = valider_url_noeud(args.url_noeud)
    if not args.utiliser_trousseau:
        raise ValueError(
            "Aucune source de mot de passe en mode scriptable : fournir --rudi-conf "
            "ou --utiliser-trousseau (jamais de mot de passe en argument CLI)."
        )
    pwd = lire_mot_de_passe_trousseau(url_noeud, args.usr)
    if pwd is None:
        raise ValueError(f"Aucun mot de passe enregistré dans le trousseau pour {args.usr}@{url_noeud}.")
    return {"url": url_noeud, "usr": args.usr, "pwd": pwd}


def _resoudre_profil_registre(args: argparse.Namespace) -> dict:
    """Résout un profil du registre par ``code_insee``, désambiguïsé par ``--url-noeud``
    si plusieurs nœuds existent pour la même commune. Ne devine jamais : ambiguïté non
    résolue par l'appelant -> erreur explicite, pas un choix arbitraire du premier trouvé."""
    profils = [p for p in charger_profils(CHEMIN_PROFILS_DEFAUT) if p["code_insee"] == args.code_insee]
    if not profils:
        raise ValueError(
            f"Aucun profil enregistré pour le code INSEE {args.code_insee!r} "
            f"(voir {CHEMIN_PROFILS_DEFAUT})."
        )
    if len(profils) > 1:
        if not args.url_noeud:
            noeuds = ", ".join(p["url_noeud"] for p in profils)
            raise ValueError(
                f"Plusieurs profils pour {args.code_insee!r} ({noeuds}) — --url-noeud "
                "requis pour désambiguïser."
            )
        profils = [p for p in profils if p["url_noeud"].rstrip("/").lower() == args.url_noeud.rstrip("/").lower()]
        if not profils:
            raise ValueError(f"Aucun profil pour {args.code_insee!r} sur le nœud {args.url_noeud!r}.")
    return profils[0]


def executer_scriptable(args: argparse.Namespace) -> int:
    if not args.code_insee:
        print("[cli] --code-insee est requis en mode scriptable.", file=sys.stderr)
        return EXIT_ECHEC_TOTAL
    if args.supprimer_organisation and not args.vider_commune:
        print("[cli] --supprimer-organisation nécessite --vider-commune.", file=sys.stderr)
        return EXIT_ECHEC_TOTAL

    profil = None
    if args.depuis_registre:
        try:
            profil = _resoudre_profil_registre(args)
        except ValueError as e:
            print(f"[cli] {e}", file=sys.stderr)
            return EXIT_ECHEC_TOTAL
        args.url_noeud = profil["url_noeud"]
        args.usr = profil["usr"]
        args.utiliser_trousseau = True
        args.organisation_producteur = profil["mode_producteur"]
        args.contact_commune = profil.get("contact_email_commune")

    try:
        conf = _resoudre_conf_scriptable(args)
    except (ValueError, UrlNoeudNonSecurisee, TrousseauEnClairError) as e:
        print(f"[cli] {e}", file=sys.stderr)
        return EXIT_ECHEC_TOTAL
    if profil and profil.get("url_catalog"):
        conf["url_catalog"] = profil["url_catalog"]
    if profil and profil.get("url_portail"):
        conf["url_portail"] = profil["url_portail"]
    if args.url_portail:
        conf["url_portail"] = args.url_portail

    if args.vider_commune:
        def _confirmer_fn(message: str, *, mot_attendu: str) -> bool:
            return confirmer(message, mot_attendu=mot_attendu, confirmation_scriptable=args.confirmer)

        rapport = vider_commune(
            conf, args.code_insee,
            chemin_etat=args.etat,
            supprimer_organisation=args.supprimer_organisation,
            confirmer_fn=_confirmer_fn,
        )
        print(f"[cli] {rapport['message']}" if rapport["message"] else "[cli] Vidage terminé.")
        if rapport["jdd_supprimes"]:
            print(f"[cli]   JDD supprimés : {', '.join(rapport['jdd_supprimes'])}")
        if rapport["jdd_echecs"]:
            print(f"[cli]   JDD en échec : {', '.join(rapport['jdd_echecs'])}", file=sys.stderr)
        if rapport["jdd_tiers_supprimes"]:
            print(f"[cli]   JDD non suivis supprimés : {', '.join(rapport['jdd_tiers_supprimes'])}")
        if rapport["jdd_tiers_echecs"]:
            print(f"[cli]   JDD non suivis en échec : {', '.join(rapport['jdd_tiers_echecs'])}",
                  file=sys.stderr)
        if rapport["organisation"] == "supprimee" and profil:
            # Jamais automatique (voir le plan, § 6) : en scriptable, pas de prompt
            # possible, donc on se contente de signaler que le profil est périmé.
            print(f"[cli]   Organisation supprimée : le profil {profil['code_insee']}/"
                  f"{profil['url_noeud']} dans le registre est désormais périmé. Lancer "
                  f"l'assistant interactif pour le retirer si besoin.")
        if rapport["jdd_echecs"] or (rapport["organisation"] and rapport["organisation"] != "supprimee"):
            return EXIT_ECHECS_PARTIELS
        return EXIT_SUCCES

    try:
        commune = resoudre_commune(args.code_insee)
    except (CodeInseeInvalide, ArrondissementMunicipalError, CommuneIntrouvableError,
            ErreurReseauCommune) as e:
        print(f"[cli] {e}", file=sys.stderr)
        return EXIT_ECHEC_TOTAL

    organisation_par_jdd = profil.get("organisation_par_jdd") if profil else None
    if organisation_par_jdd is None and args.organisation_producteur == "par-jdd":
        if not args.organisation_par_jdd:
            print("[cli] --organisation-par-jdd est requis avec --organisation-producteur par-jdd.",
                  file=sys.stderr)
            return EXIT_ECHEC_TOTAL
        with open(args.organisation_par_jdd, encoding="utf-8") as f:
            organisation_par_jdd = json.load(f)

    try:
        modes_par_jdd = resoudre_modes_par_jdd(args.organisation_producteur, organisation_par_jdd)
    except ValueError as e:
        print(f"[cli] {e}", file=sys.stderr)
        return EXIT_ECHEC_TOTAL

    if "commune" in modes_par_jdd.values():
        if not args.contact_commune or not email_valide(args.contact_commune):
            print("[cli] --contact-commune (email valide) est requis : au moins un JDD "
                  "est en mode commune.", file=sys.stderr)
            return EXIT_ECHEC_TOTAL
        avertissement = email_suspect(args.contact_commune)
        if avertissement:
            print(f"[cli] [sécurité] Attention : {avertissement}", file=sys.stderr)

    if not tester_connexion_noeud(conf):
        print("[cli] Nœud injoignable ou identifiants invalides.", file=sys.stderr)
        return EXIT_ECHEC_TOTAL

    only = set(args.only.split(",")) if args.only else None
    skip = set(args.skip.split(",")) if args.skip else None
    dossier_sortie = args.dossier_sortie or os.path.join(
        ".sortie_rudi_commune_starterkit", commune["code_insee"],
    )
    chemin_etat = args.etat or os.path.join(
        ".etat_rudi_commune_starterkit", f"{commune['code_insee']}.json",
    )

    return executer_run(
        commune=commune, conf=conf, modes_par_jdd=modes_par_jdd,
        contact_email_commune=args.contact_commune, forcer_maj=args.forcer_maj,
        only=only, skip=skip, dry_run=args.dry_run,
        dossier_sortie=dossier_sortie, chemin_etat=chemin_etat,
        confirmer_creation_organisation=False,
    )


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if not argv:
        return executer_interactif()
    args = _construire_parser().parse_args(argv)
    return executer_scriptable(args)


if __name__ == "__main__":
    sys.exit(main())
