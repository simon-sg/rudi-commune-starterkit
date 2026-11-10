"""Table curée des producteurs réels des 14 JDD du socle + producteur « commune ».

Chaque module ``datasets/<x>.py`` résout son ``producer`` RUDI via
:func:`resoudre_producer`, qui applique les 3 modes décidés avec l'utilisateur
(voir le plan, section « Qui apparaît comme producer Rudi ») :

- ``source`` (défaut) : le vrai producteur upstream (table :data:`ORGANISATIONS` ci-dessous).
- ``commune`` : la commune cible pour tous les JDD (:func:`organisation_commune`).
- ``par-jdd`` : au choix, JDD par JDD — l'appelant (``cli.py``) détermine le mode effectif
  par JDD et passe directement ``"source"``/``"commune"`` à :func:`resoudre_producer`, ce
  module n'a pas besoin de connaître le mode global.

**Cas particulier des délibérations** : contrairement aux 13 autres JDD, Mégalis Bretagne
n'est qu'une plateforme de republication, jamais le producteur réel — la commune EST déjà
la productrice de ses propres délibérations. Il n'y a donc aucune entrée ``DELIBERATIONS``
dans :data:`ORGANISATIONS` (ce serait factuellement faux d'y mettre « Mégalis Bretagne » en
mode ``source``) : :func:`resoudre_producer` retourne systématiquement
:func:`organisation_commune` pour cette clé, quel que soit le mode demandé.

Seuls ``organization_name``/``organization_caption``/``organization_summary``/
``organization_url`` sont transmis à la création d'une organisation sur un nœud RUDI
(``rudi_harvest_toolkit.rudi_client.demander_creation_organisation()`` ne transmet jamais
``organization_caption`` à la création — limite documentée dans le README du toolkit,
sans conséquence ici : la ``caption`` sert surtout à l'affichage une fois l'organisation
déjà connue du nœud/portail).
"""

from __future__ import annotations

ENTREPRISES = "entreprises"
ASSOCIATIONS = "associations"
BUDGET = "budget"
MARCHES_PUBLICS = "marches_publics"
ENERGIE = "energie"
DELIBERATIONS = "deliberations"
POPULATION = "population"
EAU_POTABLE = "eau_potable"
ETABLISSEMENTS_SCOLAIRES = "etablissements_scolaires"
ADRESSES = "adresses"
ELUS = "elus"
ELECTIONS = "elections"
IMMOBILIER_DVF = "immobilier_dvf"
IRVE = "irve"

# Les 14 clés existent dans registre.py (un module datasets/<x>.py par clé) ; DELIBERATIONS
# est la seule absente de cette table — voir docstring du module.
ORGANISATIONS: dict[str, dict] = {
    ENTREPRISES: {
        "organization_name": "INSEE",
        "organization_caption": "Institut national de la statistique et des études économiques",
        "organization_summary": (
            "Producteur du répertoire SIRENE, référentiel national des entreprises et de "
            "leurs établissements, diffusé notamment via recherche-entreprises.api.gouv.fr."
        ),
        "organization_url": "https://www.insee.fr",
    },
    ASSOCIATIONS: {
        "organization_name": "INSEE",
        "organization_caption": "Institut national de la statistique et des études économiques",
        "organization_summary": (
            "Producteur du répertoire SIRENE, qui immatricule aussi les associations "
            "(catégorie juridique 92xx), diffusé via recherche-entreprises.api.gouv.fr."
        ),
        "organization_url": "https://www.insee.fr",
    },
    BUDGET: {
        "organization_name": "DGFiP",
        "organization_caption": "Direction générale des Finances publiques",
        "organization_summary": (
            "Producteur des comptes individuels des communes (budget communal), diffusés "
            "via data.economie.gouv.fr."
        ),
        "organization_url": "https://www.economie.gouv.fr/dgfip",
    },
    MARCHES_PUBLICS: {
        "organization_name": "Ministère de l'Économie et des Finances",
        "organization_caption": "Données essentielles de la commande publique (DECP)",
        "organization_summary": (
            "Les acheteurs publics (dont les communes) déclarent leurs marchés publics "
            "sous forme de données essentielles de la commande publique (DECP), "
            "consolidées et diffusées par les services du ministère chargé de l'économie."
        ),
        "organization_url": "https://www.economie.gouv.fr",
    },
    ENERGIE: {
        "organization_name": "Agence ORE",
        "organization_caption": "Agence pour la transition écologique et les données de l'énergie",
        "organization_summary": (
            "Organisme de Répartition des données Énergétiques, producteur des données de "
            "consommation de gaz et d'électricité par commune, diffusées via "
            "portail.agenceore.fr."
        ),
        "organization_url": "https://www.agenceore.fr",
    },
    POPULATION: {
        "organization_name": "INSEE",
        "organization_caption": "Institut national de la statistique et des études économiques",
        "organization_summary": (
            "Producteur des estimations de population communale, diffusées via la "
            "plateforme Melodi."
        ),
        "organization_url": "https://www.insee.fr",
    },
    EAU_POTABLE: {
        "organization_name": "Agence régionale de santé (ARS)",
        "organization_caption": "Contrôle sanitaire des eaux destinées à la consommation humaine",
        "organization_summary": (
            "Les agences régionales de santé assurent le contrôle sanitaire de la qualité "
            "de l'eau potable distribuée ; les résultats sont consolidés et diffusés au "
            "niveau national via Hub'eau, simple plateforme d'agrégation (pas le "
            "producteur)."
        ),
        "organization_url": "https://www.hubeau.fr",
    },
    ETABLISSEMENTS_SCOLAIRES: {
        "organization_name": "Ministère de l'Éducation nationale",
        "organization_caption": "Annuaire de l'éducation",
        "organization_summary": (
            "Producteur de l'annuaire des établissements de l'enseignement scolaire du "
            "premier et second degré."
        ),
        "organization_url": "https://www.education.gouv.fr",
    },
    ADRESSES: {
        "organization_name": "Base Adresse Nationale",
        "organization_caption": "IGN / La Poste / DINUM - consortium Base Adresse Nationale",
        "organization_summary": (
            "La Base Adresse Nationale (BAN) est produite par un consortium associant "
            "l'IGN, La Poste et la direction interministérielle du numérique (DINUM), "
            "sous l'égide d'Etalab."
        ),
        "organization_url": "https://adresse.data.gouv.fr",
    },
    ELUS: {
        "organization_name": "Ministère de l'Intérieur",
        "organization_caption": "Répertoire National des Élus (RNE)",
        "organization_summary": (
            "Producteur du Répertoire National des Élus, qui recense les élus locaux et "
            "leurs mandats en cours."
        ),
        "organization_url": "https://www.interieur.gouv.fr",
    },
    ELECTIONS: {
        "organization_name": "Ministère de l'Intérieur",
        "organization_caption": "Résultats des élections",
        "organization_summary": (
            "Producteur des résultats officiels des élections, consolidés par bureau de "
            "vote puis par commune."
        ),
        "organization_url": "https://www.interieur.gouv.fr",
    },
    IMMOBILIER_DVF: {
        "organization_name": "DGFiP",
        "organization_caption": "Direction générale des Finances publiques",
        "organization_summary": (
            "Producteur des données de valeurs foncières (DVF), issues des déclarations "
            "de mutations immobilières à titre onéreux."
        ),
        "organization_url": "https://www.economie.gouv.fr/dgfip",
    },
    IRVE: {
        "organization_name": "Ministère de la Transition écologique",
        "organization_caption": "Infrastructures de recharge pour véhicules électriques (IRVE)",
        "organization_summary": (
            "Producteur du fichier consolidé national des infrastructures de recharge "
            "pour véhicules électriques (IRVE), ouvertes au public."
        ),
        "organization_url": "https://www.ecologie.gouv.fr",
    },
}


# Contacts producteurs réels confirmés par recherche web (v3, Axe 2) — table séparée,
# **jamais fusionnée** dans ORGANISATIONS : producteur_reel() retourne son dict tel quel
# (sans filtrage) jusque dans rudi_metadata["producer"] (passthrough intégral vérifié par
# test_pivot.py::test_producer_pre_forme_conserve_tel_quel) ; des clés contact_* ajoutées
# directement dans ORGANISATIONS seraient donc publiées telles quelles dans producer,
# qui n'a pas vocation à porter un contact. contact_statut est obligatoire sur chaque
# entrée ("confirme" ou "a_confirmer", jamais absent ni une autre valeur — vérifié par
# test_organisations.py) : une recherche qui a échoué reste tracée, pas silencieusement
# absente de la table.
CONTACTS_ORGANISATIONS: dict[str, dict] = {
    ENTREPRISES: {
        "contact_name": "Support APIM", "contact_email": "support-apim@insee.fr",
        "contact_statut": "confirme",
    },
    ASSOCIATIONS: {
        "contact_name": "Support APIM", "contact_email": "support-apim@insee.fr",
        "contact_statut": "confirme",
    },
    ADRESSES: {
        "contact_name": "Équipe BAN", "contact_email": "adresse@data.gouv.fr",
        "contact_statut": "confirme",
    },
    BUDGET: {
        "contact_name": "DTNUM",
        "contact_email": "dtnum.donnees.gouvernance@dgfip.finances.gouv.fr",
        "contact_statut": "confirme",
    },
    IMMOBILIER_DVF: {
        "contact_name": "DTNUM",
        "contact_email": "dtnum.donnees.gouvernance@dgfip.finances.gouv.fr",
        "contact_statut": "confirme",
    },
    ELUS: {
        "contact_name": "Ministère de l'Intérieur",
        "contact_email": "elections@interieur.gouv.fr", "contact_statut": "confirme",
    },
    ELECTIONS: {
        "contact_name": "Ministère de l'Intérieur",
        "contact_email": "elections@interieur.gouv.fr", "contact_statut": "confirme",
    },
    IRVE: {
        "contact_name": "transport.data.gouv.fr",
        "contact_email": "contact@transport.beta.gouv.fr", "contact_statut": "confirme",
    },
    # eau_potable, etablissements_scolaires : producteurs introuvables malgré recherche
    # poussée (BRGM/Hub'eau : seul dpo@brgm.fr, hors-sujet ; Éducation nationale : seule
    # adresse trouvée était celle de l'éditeur technique de la plateforme, pas du
    # Ministère) — contact_statut explicitement "a_confirmer", jamais une entrée absente.
    EAU_POTABLE: {"contact_statut": "a_confirmer"},
    ETABLISSEMENTS_SCOLAIRES: {"contact_statut": "a_confirmer"},
    # deliberations : PAS d'entrée ici. Ce JDD est le seul dont le producteur EST la
    # commune elle-même (producteur_reel("deliberations") lève KeyError par construction,
    # voir resoudre_producer()) ; son contact réel est donc contact_email_commune, déjà
    # propagé par la branche email_commune existante de contacts_pour_producer(). Publier
    # un repli générique ici publierait un email factice alors que le vrai contact est
    # trivialement disponible.
    # marches_publics : pas d'entrée curée ici — contact réel résolu dynamiquement via
    # contact_points (Colin Maudry, colin@colmo.tech), priorité 1 de la chaîne de
    # contacts_pour_producer(), toujours disponible donc jamais besoin d'un repli curé.
}


def contact_curated_pour_jdd(cle_jdd: str) -> dict | None:
    """Entrée ``CONTACTS_ORGANISATIONS`` pour ce JDD, ou ``None`` si absente de la table
    (accesseur tolérant — contrairement à ``licences.licence_pour_jdd()``, qui lève
    volontairement : un contact confirmé manquant retombe sur le repli générique déjà
    accepté, ce n'est jamais un échec du JDD)."""
    return CONTACTS_ORGANISATIONS.get(cle_jdd)


def producteur_reel(cle_jdd: str) -> dict:
    """Producteur réel curé pour ``cle_jdd`` (copie — l'appelant peut muter librement)."""
    try:
        return dict(ORGANISATIONS[cle_jdd])
    except KeyError:
        raise KeyError(
            f"Aucun producteur curé pour la clé JDD {cle_jdd!r} dans organisations.py "
            "(délibérations exceptée : voir resoudre_producer())."
        ) from None


def organisation_commune(commune: dict, *, description_commune: dict | None = None) -> dict:
    """Producteur « la commune publie ses données » — construit explicitement le nom.

    Ni ``geo.api.gouv.fr`` (``"Gévezé"``, sans « Commune de ») ni la fiche SIRENE de la
    commune (``"COMMUNE DE GEVEZE"``, en majuscules) ne donnent la forme voulue : ce nom
    est la source de vérité, pas un repli flou.

    ``description_commune`` (optionnel, keyword-only — voir
    ``description_commune.construire_description_commune()``) : si fourni et porteur
    d'un ``organization_summary`` (résumé Wikipédia ou repli générique déjà résolu par
    l'appelant), remplace la phrase générique codée en dur ici et, si une ``url`` est
    présente, l'ajoute en ``organization_url``. Rétrocompatible : sans cet argument,
    comportement strictement inchangé.
    """
    nom = f"Commune de {commune['nom']}"
    resume = description_commune or {}
    summary = resume.get("organization_summary") or (
        f"Collectivité territoriale, commune de {commune['nom']}"
        f" ({commune.get('code_insee', '')})."
    )
    organisation = {
        "organization_name": nom,
        "organization_caption": "Collectivité territoriale",
        "organization_summary": summary,
    }
    if resume.get("url"):
        organisation["organization_url"] = resume["url"]
    return organisation


def resoudre_producer(
    cle_jdd: str, mode: str, commune: dict, *, description_commune: dict | None = None,
) -> dict:
    """Résout le ``producer`` RUDI d'un JDD selon le mode effectif pour ce JDD.

    ``mode`` : ``"source"`` ou ``"commune"`` (le mode ``"par-jdd"`` de l'assistant CLI se
    traduit, JDD par JDD, en l'un de ces deux appels — ce module ne connaît que le mode
    déjà résolu pour ce JDD précis).

    Les délibérations ignorent ``mode`` et retournent toujours :func:`organisation_commune`
    — voir la docstring du module. ``description_commune`` (keyword-only) n'a d'effet
    que dans les branches qui retournent :func:`organisation_commune` — ignoré en mode
    ``"source"``, puisque ``producteur_reel()`` ne décrit jamais la commune elle-même.
    """
    if cle_jdd == DELIBERATIONS:
        return organisation_commune(commune, description_commune=description_commune)
    if mode == "commune":
        return organisation_commune(commune, description_commune=description_commune)
    if mode == "source":
        return producteur_reel(cle_jdd)
    raise ValueError(f"mode de producteur inconnu : {mode!r} (attendu 'source' ou 'commune')")


__all__ = [
    "ADRESSES",
    "ASSOCIATIONS",
    "BUDGET",
    "CONTACTS_ORGANISATIONS",
    "DELIBERATIONS",
    "EAU_POTABLE",
    "ELECTIONS",
    "ELUS",
    "ENERGIE",
    "ENTREPRISES",
    "ETABLISSEMENTS_SCOLAIRES",
    "IMMOBILIER_DVF",
    "IRVE",
    "MARCHES_PUBLICS",
    "ORGANISATIONS",
    "POPULATION",
    "contact_curated_pour_jdd",
    "organisation_commune",
    "producteur_reel",
    "resoudre_producer",
]
