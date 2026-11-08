"""Helpers partagés entre les modules ``datasets/*.py`` — jamais importés hors de ce
package (contrairement à ``rudi_harvest_toolkit``, ce module encode des choix propres aux
14 JDD de ce socle, pas une brique générique à mutualiser ailleurs)."""

from __future__ import annotations

import uuid

from rudi_harvest_toolkit.http import session
from rudi_harvest_toolkit.rudi_client import email_par_defaut

from .. import organisations

RECHERCHE_ENTREPRISES_API = "https://recherche-entreprises.api.gouv.fr"

# Confirmé par lecture de l'OpenAPI de l'API le 2026-11-07 (/openapi.json) : per_page max 25.
_PER_PAGE_MAX = 25
# Garde-fou de pagination (plan § Modèle de média : "prévoir un plafond de pagination
# explicite" pour les connecteurs paginés — une grande ville peut représenter des milliers
# de pages). 400 pages * 25 = 10 000 résultats max par commune.
PLAFOND_PAGES_DEFAUT = 400


def local_id_jdd(cle_jdd: str, code_insee: str) -> str:
    """UUIDv5 déterministe dépendant SEULEMENT de ``(cle_jdd, code_insee)`` — jamais du
    mode producer ni d'aucune autre option, pour qu'une bascule source/commune (voir le
    plan, § Qui apparaît comme producer Rudi, « bascule de mode et état déjà publié ») ne
    duplique jamais la ressource sur le nœud."""
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"rudi-commune-starterkit/{cle_jdd}/{code_insee}"))


def contacts_pour_producer(
    cle_jdd: str, producer: dict, commune: dict, *, email_commune: str | None = None,
) -> list[dict]:
    """Contacts à transmettre à ``construire_rudi_metadata(contacts_source=...)``.

    Le contact de la source réelle (``organisations.producteur_reel(cle_jdd)``, ex.
    INSEE, DGFiP, Mégalis Bretagne) est désormais inclus dans les DEUX modes — avant ce
    changement, il disparaissait complètement en mode ``commune`` (``contacts_source``
    n'étant alors jamais vide, le repli générique de ``publier_dataset()`` ne se
    déclenchait jamais). Pas de nouvelle table d'emails « curés » : on réutilise le même
    repli déjà accepté en mode source (``email_par_defaut()``) plutôt que d'inventer des
    adresses plausibles mais fausses dans un catalogue ouvert.

    - Si ``producer`` résout vers la commune (mode ``commune`` pour CE JDD précis — pas
      seulement ``email_commune is not None``, qui serait vrai aussi pour un JDD resté en
      mode ``source`` dans un run ``par-jdd`` mixte) ET qu'un ``email_commune`` est fourni :
      contact commune + contact source (si ce JDD en a une — les délibérations n'en ont
      pas). Sans ``email_commune`` (ex. ``deliberations.py``, producteur toujours la
      commune mais ``contact_email_commune`` non renseigné) : pas de contact commune
      explicite ici — ``publier_dataset()`` retombe sur son repli générique nommé d'après
      le producteur, comportement historique inchangé pour ce cas précis.
    - Sinon (mode ``source`` pour ce JDD) : seulement le contact source, explicite ici
      plutôt que laissé au repli implicite de ``publier_dataset()`` — mêmes valeurs,
      mais visibles et testables à cet endroit.
    """
    try:
        source = organisations.producteur_reel(cle_jdd)
        contact_source: dict | None = {
            "contact_name": source["organization_name"],
            "email": email_par_defaut(source["organization_name"]),
        }
    except KeyError:
        contact_source = None  # délibérations : pas de source distincte

    nom_org_commune = organisations.organisation_commune(commune)["organization_name"]
    contacts = []
    if producer["organization_name"] == nom_org_commune and email_commune:
        contacts.append({"contact_name": nom_org_commune, "email": email_commune})
    if contact_source:
        contacts.append(contact_source)
    return contacts


def recherche_entreprises(
    code_commune: str,
    *,
    nature_juridique: str | None = None,
    etat_administratif: str | None = None,
    session_http=None,
    timeout: int = 30,
    plafond_pages: int = PLAFOND_PAGES_DEFAUT,
) -> list[dict]:
    """Pagine ``recherche-entreprises.api.gouv.fr/search`` pour une commune et retourne
    tous les résultats (liste à plat, sur toutes les pages jusqu'à ``plafond_pages``).

    Le filtre serveur ``code_commune`` matche toute entreprise ayant au moins un
    établissement dans la commune (``matching_etablissements``), pas seulement son siège —
    confirmé empiriquement le 2026-11-07 (Gévezé : "LA POSTE", siège à Paris, apparaît via
    un établissement fermé sur place). ``etat_administratif="A"`` filtre l'**unité
    légale** (pas l'établissement lui-même), pas un filtre parfait mais le seul exposé par
    l'API à ce niveau.
    """
    session_http = session_http or session
    params_base = {"code_commune": code_commune, "per_page": _PER_PAGE_MAX}
    if nature_juridique:
        params_base["nature_juridique"] = nature_juridique
    if etat_administratif:
        params_base["etat_administratif"] = etat_administratif

    resultats: list[dict] = []
    page = 1
    while True:
        reponse = session_http.get(
            f"{RECHERCHE_ENTREPRISES_API}/search",
            params={**params_base, "page": page},
            timeout=timeout,
        )
        reponse.raise_for_status()
        donnees = reponse.json()
        resultats.extend(donnees.get("results", []))
        total_pages = donnees.get("total_pages", page)
        if page >= total_pages or page >= plafond_pages:
            break
        page += 1
    return resultats


_CHAMPS_ENTREPRISE = (
    "siren", "nom_complet", "sigle", "activite_principale", "categorie_entreprise",
    "tranche_effectif_salarie", "date_creation", "etat_administratif", "nature_juridique",
)
_CHAMPS_ETABLISSEMENT = (
    "siret", "adresse", "code_postal", "libelle_commune", "est_siege",
    "activite_principale", "etat_administratif",
)


def simplifier_resultat_entreprise(resultat: dict) -> dict:
    """Aplatit un résultat ``recherche-entreprises`` en un dict léger, ouvrable tel quel.

    Ignore volontairement ``dirigeants`` (personnes physiques avec date de naissance),
    ``finances``/``complements``/``tva`` (hors sujet open data communal) — même principe
    que l'allowlist de colonnes décidée pour le RNE dans le plan : ne jamais publier plus
    de données personnelles que nécessaire.
    """
    simplifie = {champ: resultat.get(champ) for champ in _CHAMPS_ENTREPRISE}
    simplifie["etablissements"] = [
        {champ: etab.get(champ) for champ in _CHAMPS_ETABLISSEMENT}
        for etab in resultat.get("matching_etablissements", [])
    ]
    return simplifie


__all__ = [
    "PLAFOND_PAGES_DEFAUT",
    "RECHERCHE_ENTREPRISES_API",
    "contacts_pour_producer",
    "local_id_jdd",
    "recherche_entreprises",
    "simplifier_resultat_entreprise",
]
