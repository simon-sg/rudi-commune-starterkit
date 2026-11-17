"""Correctif console Windows — encodage de sortie.

**Bug réel corrigé le 2026-11-17**, trouvé en testant l'exécutable sur une vraie
machine Windows 11 (fr-FR) via une VM, pour la première fois depuis le début de ce
projet (jusque-là, seuls Linux/macOS et une émulation Wine peu fiable avaient pu être
testés — voir ``feedback_toujours_tester_e2e_pas_que_mocks`` en mémoire) : le wizard
plantait systématiquement dès la confirmation du code INSEE (1re vraie interaction),
avec ``UnicodeEncodeError: 'charmap' codec can't encode character '\\u2192'``.

Cause : la console Windows (``cmd.exe``) encode sa sortie standard avec le codepage
OEM/ANSI actif (``cp850``/``cp1252`` selon la locale), pas UTF-8, sauf configuration
explicite (``chcp 65001``) que rien ici ne fait. Ce codepage ne couvre pas tous les
caractères utilisés par ce programme pour l'habillage visuel (ex. la flèche « → » de
``cli.py``) — contrairement aux lettres accentuées françaises courantes (é, è, ç...),
qui *sont* couvertes par ces deux codepages et n'avaient donc jamais révélé le
problème plus tôt. N'importe quel appel à ``print()``/``input()`` affichant un tel
caractère lève alors ``UnicodeEncodeError`` avant même d'atteindre le nœud RUDI.

Correctif : forcer l'encodage UTF-8 en sortie dès le départ, quel que soit le
codepage actif de la console — règle le problème à la racine plutôt que d'auditer un
par un les caractères utilisés (une liste qui ne peut que s'allonger avec le temps).
``errors="replace"`` en dernier filet : sur un terminal vraiment ancien qui
n'afficherait pas certains glyphes malgré l'encodage correct, un caractère de
remplacement est substitué — jamais un plantage.
"""

from __future__ import annotations

import sys


def forcer_utf8_console() -> None:
    """Reconfigure stdout/stderr en UTF-8. Idempotente, sûre à appeler plusieurs
    fois (y compris dans la boucle de menu de l'exécutable packagé). Ne lève jamais :
    un flux sans ``reconfigure`` (redirigé vers un objet non standard, ex. certains
    contextes de test) ou qui refuse ce changement est simplement laissé tel quel —
    ce correctif est un confort pour la console réelle, jamais une condition requise
    pour que le programme fonctionne."""
    for flux in (sys.stdout, sys.stderr):
        try:
            flux.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError, OSError):
            pass


__all__ = ["forcer_utf8_console"]
