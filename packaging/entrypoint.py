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

# Affiché avant l'import ci-dessous, qui déclenche le chargement de pandas/pyarrow
# (via registre.py -> modules JDD) — la partie la plus lente du démarrage une fois
# l'exécutable lui-même décompressé par le bootloader PyInstaller. Ce message
# n'apparaît qu'une fois Python démarré : il ne couvre pas la décompression native
# qui précède (hors de portée de ce script, trop tôt pour qu'aucun code Python
# s'exécute).
print("Chargement des ressources, merci de patienter...")
sys.stdout.flush()

from rudi_commune_starterkit.cli import main


def _executer_une_fois() -> int:
    try:
        return main()
    except SystemExit as exc:
        # argparse (--help, flag invalide) lève SystemExit, pas une Exception —
        # non capturé par le except ci-dessous, il fermerait la fenêtre sans
        # jamais atteindre la pause finale.
        return exc.code if isinstance(exc.code, int) else (0 if exc.code is None else 1)
    except Exception as exc:  # noqa: BLE001 - affichage volontairement générique
        print(f"Erreur inattendue : {exc}")
        return 1


if __name__ == "__main__":
    code = 1
    while True:
        code = _executer_une_fois()
        if code != 0:
            # Avertissement ci-dessous : la création d'organisation (côté
            # rudi_harvest_toolkit) n'est pas garantie idempotente — un échec
            # ambigu (ex. serveur lent) peut avoir réussi côté nœud sans que la
            # réponse soit arrivée, et un nouvel essai immédiat peut alors créer
            # une organisation en double si le nœud n'a pas encore fini d'indexer
            # la précédente. Vrai correctif (organization_id déterministe/
            # idempotent côté toolkit) hors scope de ce fichier — voir le backlog.
            print(
                "\nÉchec (ou succès partiel). Si cela s'est produit après la "
                "création d'une organisation ou la publication d'un JDD, "
                "vérifiez sur le nœud avant de relancer (un nouvel essai "
                "immédiat peut créer un doublon)."
            )
        # Retour automatique au menu plutôt qu'une fermeture forcée après chaque
        # run (jusqu'ici, un succès fermait directement la fenêtre sans possibilité
        # de traiter une autre commune) : Entrée rappelle main() depuis le début
        # (aucune donnée déjà saisie n'est réutilisée — elle réaffiche notamment le
        # menu des communes déjà enregistrées, avec son propre choix « Quitter »),
        # 'q' ferme directement sans repasser par ce menu.
        try:
            reponse = input(
                "\nAppuyez sur Entrée pour revenir au menu, 'q' pour quitter : "
            ).strip().lower()
        except EOFError:
            # Stdin fermé/non interactif (ex. smoke-test CI) : pas de prompt
            # possible, on ferme comme avant ce changement.
            break
        if reponse in ("q", "quitter"):
            break
        print()

    sys.exit(code)
