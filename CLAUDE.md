# Orchestration

Ce repo est suivi par une session d'orchestration permanente nommée
**"orchestration starterkit"**. Elle fait la revue qualité, le merge sur
`main`, le nettoyage des worktrees, la coordination avec la session doc et
avec starterkit-tester, et le déclenchement du déploiement du guide.

En conséquence, pour toute session qui travaille dans ce repo (y compris
dans un worktree) :

- **Ne mergez pas vous-même sur `main`** et ne poussez pas directement sur
  `main`. Committez sur votre branche/worktree, puis signalez votre travail
  à l'orchestrateur.
- **Ne déclenchez pas vous-même** le workflow `deploy-docs.yml` (déploiement
  du guide sur GitHub Pages). Il reste à déclenchement manuel par design
  (voir le commentaire en tête du fichier) ; c'est l'orchestrateur qui le
  lance, après revue.
- **En début de job**, envoyez un message (`SendMessage`) à la session
  **"orchestration starterkit"** pour indiquer sur quoi vous allez
  travailler (sujet, fichiers/zone concernés).
- **À chaque commit**, et avant de terminer votre job si vous avez committé
  quoi que ce soit dans ce repo, envoyez un message (`SendMessage`) à la
  session **"orchestration starterkit"** avec :
  - les commits concernés (hash + résumé),
  - si le changement touche le comportement utilisateur, le CLI ou toute
    API/sortie dont dépend le guide HTML (`docs/`, `guide/`) ou
    `starterkit-tester` — précisez-le explicitement, même si vous n'êtes pas
    sûr·e, l'orchestrateur tranche.

Si vous êtes la session doc (`rudi-commune-starterkit doc html`) ou une
session invoquée par l'orchestrateur pour une tâche précise, suivez ses
instructions telles que reçues par message plutôt que cette procédure
générique.
