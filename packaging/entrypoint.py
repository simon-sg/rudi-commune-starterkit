"""Bootstrap PyInstaller pour l'exécutable autonome (double-clic, sans console
laissée ouverte par défaut sous Windows).

Ce fichier n'est utilisé que pour le packaging — il ne fait pas partie du
package `rudi_commune_starterkit` et n'est pas couvert par sa suite de tests.
`main()` (CLI normal) n'est pas modifiée : un agent municipal non technique qui
double-clique l'exécutable n'a pas de terminal ouvert derrière lui, donc sans
la pause finale la fenêtre se fermerait instantanément avant qu'il ait pu lire
le résultat (succès, échec partiel, ou erreur).
"""

import sys

from rudi_commune_starterkit.cli import main

if __name__ == "__main__":
    code = 1
    try:
        code = main()
    except SystemExit as exc:
        # argparse (--help, flag invalide) lève SystemExit, pas une Exception —
        # non capturé par le except ci-dessous, il fermerait la fenêtre sans
        # jamais atteindre la pause finale.
        code = exc.code if isinstance(exc.code, int) else (0 if exc.code is None else 1)
    except Exception as exc:  # noqa: BLE001 - affichage volontairement générique
        print(f"Erreur inattendue : {exc}")
        code = 1
    finally:
        # Si stdin est fermé/non interactif (ex. lancement non-console, smoke-test
        # CI), ce input() lèverait lui-même EOFError — à ignorer, pas à laisser
        # planter juste après avoir affiché le résultat.
        try:
            input("Appuyez sur Entrée pour fermer...")
        except EOFError:
            pass

    sys.exit(code)
