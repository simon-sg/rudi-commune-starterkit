"""Décision de republication par hash de contenu normalisé.

Volontairement **pas** ``rudi_harvest_toolkit.state.dataset_a_change()`` (qui compare un
champ ``last_modified`` — inadapté ici, les 13 JDD de ce socle n'ont pas de notion
uniforme de « dernière modification source »). Ce module ne fait que décider si un JDD
doit être republié ; la lecture/écriture brute du fichier d'état reste
``rudi_harvest_toolkit.state.charger_etat``/``sauvegarder_etat``, appelées par
``cli.py``, pas par ce module.
"""

from __future__ import annotations

import hashlib
import json


def hash_contenu_jdd(rudi_metadata: dict) -> str:
    """SHA-256 hexadécimal d'une sérialisation JSON déterministe de ``rudi_metadata``.

    Varie automatiquement si ``producer``/description changent (c'est tout le dict qui
    est haché, pas un sous-ensemble choisi à la main) — condition nécessaire pour qu'une
    bascule de mode producteur (source <-> commune) soit détectée comme un changement.
    N'inclut jamais les chemins de ``fichiers_filtres`` : ce sont des chemins temporaires
    locaux, pas du contenu Rudi, et ``ResultatConnecteur`` les porte séparément de
    ``rudi_metadata``.
    """
    serialise = json.dumps(rudi_metadata, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(serialise.encode("utf-8")).hexdigest()


def doit_republier(etat: dict, local_id: str, nouveau_hash: str, *, forcer_maj: bool) -> bool:
    """``True`` si ``forcer_maj``, si ``local_id`` est inconnu, ou si le hash a changé."""
    if forcer_maj:
        return True
    entree = etat.get(local_id)
    if entree is None:
        return True
    return entree.get("hash") != nouveau_hash


def enregistrer_publication(etat: dict, local_id: str, nouveau_hash: str) -> dict:
    """Retourne une copie de ``etat`` avec ``local_id`` enregistré — ne mute pas l'original."""
    nouvel_etat = dict(etat)
    nouvel_etat[local_id] = {"hash": nouveau_hash}
    return nouvel_etat


__all__ = ["doit_republier", "enregistrer_publication", "hash_contenu_jdd"]
