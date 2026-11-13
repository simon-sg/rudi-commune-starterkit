# Guide utilisateur HTML (MkDocs)

Génère le site statique publié sur GitHub Pages — guide d'utilisation pour un agent
municipal non technique + présentation des 13 données publiables. Voir BACKLOG.md,
chantier C, pour le contexte et les décisions actées.

## Principe

`docs/` n'est **jamais** versionné ni édité à la main (voir `.gitignore`) — il est
entièrement reconstruit par `generer.py` à partir de deux sources, jamais dupliquées
ailleurs :

- `registre.lister_modules()` (13 JDD du socle) pour les fiches de données —
  `TITRE`/`SYNOPSIS_PATRON`/`DESCRIPTION_PATRON`/`THEME`/`FREQUENCE_MAJ`, déjà écrits
  à la main dans chaque module `src/rudi_commune_starterkit/datasets/*.py`.
- `contenu_statique.py` pour tout le reste (accueil, tutoriel, FAQ, glossaire,
  licences) — texte rédigé une fois avec soin, pas un gabarit générique.

Aucun appel réseau pendant la génération : les fiches sont rendues avec une commune
d'exemple fixe (`contenu_statique.COMMUNE_EXEMPLE`), pas une vraie moisson en direct.

## Utilisation locale

```bash
pip install -e . mkdocs-material
python -m guide.generer   # écrit docs/
mkdocs serve               # http://127.0.0.1:8000, rechargement automatique
```

`mkdocs build --strict` (utilisé en CI) échoue sur tout lien ou page manquant.

## Points d'attention pour une future session

- `mkdocs.yml` liste les 7 pages du tutoriel **en dur** dans sa section `nav`
  (volontaire) ; les 13 fiches de données, elles, ne sont **jamais** listées en dur —
  seul `donnees/index.md` est dans la nav, les fiches sont atteintes depuis cet index
  et par la recherche. Ajouter/retirer un JDD dans `registre.py` n'implique donc
  jamais de toucher `mkdocs.yml`.
- `tests/test_guide.py::TestAntiDeriveWizard` vérifie mot pour mot que les citations
  du wizard (`cli.py`) reprises dans `pas-a-pas.md`/`relancer.md` existent toujours
  dans les deux fichiers. Une reformulation d'une invite du wizard sans mettre à jour
  `CITATIONS_WIZARD_A_VERIFIER` (ou le texte du tutoriel) fait échouer ce test —
  c'est voulu, pas un faux positif à contourner.
- Déploiement : `.github/workflows/deploy-docs.yml`, déclenchement manuel
  (`workflow_dispatch`), même convention que `build-executable.yml`. Nécessite
  d'activer Pages une fois dans Settings du dépôt GitHub (source = GitHub Actions) —
  action humaine, hors portée de ce code.
