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
    try:
        code = main()
    except Exception as exc:  # noqa: BLE001 - affichage volontairement générique
        print(f"Erreur inattendue : {exc}")
        code = 1

    input("Appuyez sur Entrée pour fermer...")
    sys.exit(code)
