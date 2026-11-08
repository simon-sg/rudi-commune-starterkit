"""Confirmation partagée pour les actions destructrices — aucune dépendance vers
``cli.py`` ni ``vidage.py``, pour éviter tout risque de cycle d'import entre ces deux
modules (``vidage.py`` en a besoin, ``cli.py`` l'expose en mode scriptable via
``--confirmer``)."""

from __future__ import annotations

import sys


def confirmer(message: str, *, mot_attendu: str, confirmation_scriptable: str | None = None) -> bool:
    """Exige une confirmation explicite avant une action destructrice.

    - Avec un terminal : affiche ``message`` puis demande de retaper ``mot_attendu``
      (ex. ``"SUPPRIMER"``) — une simple validation ``[O/n]`` est jugée trop faible pour
      une suppression de JDD/organisation sur un portail partagé.
    - Sans terminal (scriptable) : jamais de prompt — ``confirmation_scriptable`` doit
      déjà valoir ``mot_attendu`` (ex. transmis via ``--confirmer SUPPRIMER``), sinon
      refus immédiat.
    """
    if not sys.stdin.isatty():
        return confirmation_scriptable == mot_attendu
    print(message)
    reponse = input(f"Taper {mot_attendu!r} pour confirmer : ").strip()
    return reponse == mot_attendu


__all__ = ["confirmer"]
