"""Registre local des communes déjà configurées — jamais le mot de passe.

Corrige le bug réel constaté en conditions réelles : l'assistant *propose* de mémoriser
les identifiants (``securite.enregistrer_mot_de_passe_trousseau()``) mais ne relit
jamais rien au run suivant — ni le mot de passe, ni le reste de la saisie (code INSEE,
URL, mode producteur, email de contact). Ce module ferme la seconde moitié du bug : la
mémorisation du **profil** (tout sauf le mot de passe, qui reste au trousseau système,
clé par ``(url_noeud, usr)`` comme avant).

Une commune peut changer de nœud RUDI (migration, changement de prestataire) sans que
cela doive écraser un profil existant pour la même commune sur l'ancien nœud : la clé
d'upsert est donc ``(code_insee, url_noeud normalisé)``, jamais ``code_insee`` seul.
"""

from __future__ import annotations

import json
import os

_CHEMIN_DEFAUT = os.path.join(".rudi_commune_starterkit", "profils.json")


def _normaliser_url(url_noeud: str) -> str:
    """Casse et slash final ignorés pour la comparaison de clé — deux saisies de la
    même URL (``https://N.fr/`` vs ``https://n.fr``) ne doivent jamais créer deux
    profils distincts pour la même commune."""
    return url_noeud.strip().rstrip("/").lower()


def charger_profils(chemin: str = _CHEMIN_DEFAUT) -> list[dict]:
    """Charge la liste des profils enregistrés. Fichier absent → ``[]`` (premier usage,
    pas une erreur). JSON corrompu → erreur explicite : contrairement à l'état de
    republication (``rudi_harvest_toolkit.state``), un registre corrompu mérite d'être
    signalé plutôt que silencieusement vidé — il contient la seule copie de la
    correspondance commune/nœud, pas une donnée reconstructible depuis le serveur."""
    if not os.path.exists(chemin):
        return []
    with open(chemin, "r", encoding="utf-8") as f:
        try:
            profils = json.load(f)
        except json.JSONDecodeError as e:
            raise ValueError(
                f"{chemin} existe mais n'est pas un JSON valide ({e}) — corriger ou "
                "supprimer ce fichier avant de poursuivre, aucun profil n'est deviné."
            ) from e
    if not isinstance(profils, list):
        raise ValueError(f"{chemin} doit contenir une liste de profils, pas {type(profils).__name__}.")
    return profils


def enregistrer_profil(profil: dict, chemin: str = _CHEMIN_DEFAUT) -> None:
    """Upsert par ``(code_insee, url_noeud normalisé)`` — écriture atomique (fichier
    temporaire + ``os.replace``), jamais de verrou de fichier (outil mono-utilisateur,
    pas d'exécution concurrente à protéger). ``profil`` ne doit jamais contenir de
    mot de passe : ce module ne le vérifie pas, c'est à l'appelant de ne jamais le lui
    donner (voir ``cli.py``, qui sépare toujours ``pwd`` du dict profil)."""
    profils = charger_profils(chemin)
    cle_cible = (profil["code_insee"], _normaliser_url(profil["url_noeud"]))
    profils = [
        p for p in profils
        if (p["code_insee"], _normaliser_url(p["url_noeud"])) != cle_cible
    ]
    profils.append(profil)

    dossier = os.path.dirname(chemin)
    if dossier:
        os.makedirs(dossier, exist_ok=True)
    chemin_temporaire = f"{chemin}.tmp"
    with open(chemin_temporaire, "w", encoding="utf-8") as f:
        json.dump(profils, f, ensure_ascii=False, indent=2)
    os.replace(chemin_temporaire, chemin)


def oublier_profil(code_insee: str, url_noeud: str, chemin: str = _CHEMIN_DEFAUT) -> bool:
    """Retire un profil du registre. Retourne ``True`` s'il a été trouvé et retiré,
    ``False`` sinon (idempotent — un appel répété n'est jamais une erreur)."""
    profils = charger_profils(chemin)
    cle_cible = (code_insee, _normaliser_url(url_noeud))
    profils_restants = [
        p for p in profils
        if (p["code_insee"], _normaliser_url(p["url_noeud"])) != cle_cible
    ]
    if len(profils_restants) == len(profils):
        return False

    dossier = os.path.dirname(chemin)
    if dossier:
        os.makedirs(dossier, exist_ok=True)
    chemin_temporaire = f"{chemin}.tmp"
    with open(chemin_temporaire, "w", encoding="utf-8") as f:
        json.dump(profils_restants, f, ensure_ascii=False, indent=2)
    os.replace(chemin_temporaire, chemin)
    return True


__all__ = ["charger_profils", "enregistrer_profil", "oublier_profil"]
