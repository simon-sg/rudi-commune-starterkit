"""Résolution des organisations déjà présentes sur un nœud RUDI cible.

Évite qu'un producteur en mode ``commune``/``par-jdd`` (voir ``organisations.py``) soit
créé en doublon quand il existe déjà sur le nœud sous une orthographe légèrement
différente (casse, accents, espaces).
"""

from __future__ import annotations

import requests

from rudi_harvest_toolkit import rudi_client
from rudi_harvest_toolkit.tabular import normaliser_nom_colonne


def tester_connexion_noeud(conf: dict, erreur_sortie: dict | None = None) -> bool:
    """Wrapper direct autour de ``rudi_client.noeud_pret()`` — ``cli.py`` n'importe pas
    ``rudi_client`` directement, frontière claire support/toolkit.

    ``erreur_sortie``, si fourni, reçoit le détail de l'échec (voir
    :func:`rudi_client.noeud_pret`) — utilisé par ``cli.py`` pour proposer d'ignorer
    la vérification TLS uniquement en cas de certificat non reconnu, jamais pour les
    autres causes d'échec (DNS, timeout, etc.)."""
    return rudi_client.noeud_pret(conf, erreur_sortie=erreur_sortie)


def erreur_est_certificat_tls(erreur_sortie: dict) -> bool:
    """True si l'échec renvoyé par :func:`tester_connexion_noeud` vient d'un
    certificat TLS non reconnu (ex. certificat auto-signé sur un nœud de test) —
    seul cas où proposer d'ignorer la vérification TLS a un sens ; une erreur DNS ou
    un timeout ne serait pas résolu en ignorant le certificat."""
    return isinstance(erreur_sortie.get("exception"), requests.exceptions.SSLError)


def desactiver_verification_tls_noeud() -> None:
    """Ignore la vérification du certificat TLS pour le reste du run — seulement
    après confirmation explicite de l'utilisateur final (risque d'interception,
    voir :func:`rudi_client.desactiver_verification_tls`)."""
    rudi_client.desactiver_verification_tls()


def organisation_existante(conf: dict, organization_name: str) -> dict | None:
    """Wrapper direct autour de ``rudi_client.organisation_par_nom()`` — même frontière
    que :func:`tester_connexion_noeud`. Utilisé par le garde-fou organisation de
    ``cli.py`` (créer + s'arrêter tant que l'organisation de la commune n'est pas
    validée), distinct de :func:`resoudre_organisations_producteurs` qui ne fait que
    rapprocher des noms pour éviter un doublon, sans jamais regarder le statut."""
    return rudi_client.organisation_par_nom(conf, organization_name)


def normaliser_nom_organisation(nom: str) -> str:
    """Clé de comparaison tolérante (casse/accents/espaces) — même logique que
    ``rudi_harvest_toolkit.tabular.normaliser_nom_colonne``, réutilisée telle quelle."""
    return normaliser_nom_colonne(nom)


def rapprocher_organisation(nom_candidat: str, organisations_noeud: list[dict]) -> dict | None:
    """Égalité normalisée stricte entre ``nom_candidat`` et ``organization_name`` des
    organisations déjà sur le nœud. Pas de correspondance floue par similarité en v1 —
    limite documentée, pas un oubli."""
    cible = normaliser_nom_organisation(nom_candidat)
    for organisation in organisations_noeud:
        if normaliser_nom_organisation(organisation.get("organization_name") or "") == cible:
            return organisation
    return None


def resoudre_organisations_producteurs(
    conf: dict, producteurs_candidats: list[dict],
) -> tuple[dict[str, dict], str | None]:
    """Rapproche chaque producteur candidat avec les organisations déjà sur le nœud.

    Retourne ``(mapping, avertissement)`` : ``mapping[organization_name] ->`` le dict
    producteur, enrichi d'un ``organization_id`` si rapproché, inchangé sinon (dans ce
    cas ``publier_dataset()`` créera l'organisation normalement, ce n'est pas une
    erreur). ``avertissement`` est ``None`` si le listing du nœud a réussi, sinon une
    chaîne expliquant que le rapprochement n'a pas pu être vérifié — jamais une
    exception qui bloquerait l'appelant pour cet appel annexe."""
    try:
        organisations_noeud = rudi_client.lister_organisations(conf)
    except Exception as e:  # noqa: BLE001
        mapping = {p["organization_name"]: dict(p) for p in producteurs_candidats}
        avertissement = (
            "Impossible de lister les organisations déjà présentes sur le nœud "
            f"({e}) — le rapprochement n'a pas pu être vérifié, les noms construits "
            "localement seront utilisés tels quels."
        )
        return mapping, avertissement

    mapping = {}
    for producteur in producteurs_candidats:
        producteur_resolu = dict(producteur)
        trouve = rapprocher_organisation(producteur["organization_name"], organisations_noeud)
        if trouve and trouve.get("organization_id"):
            producteur_resolu["organization_id"] = trouve["organization_id"]
        mapping[producteur["organization_name"]] = producteur_resolu
    return mapping, None


__all__ = [
    "desactiver_verification_tls_noeud",
    "erreur_est_certificat_tls",
    "normaliser_nom_organisation",
    "organisation_existante",
    "rapprocher_organisation",
    "resoudre_organisations_producteurs",
    "tester_connexion_noeud",
]
