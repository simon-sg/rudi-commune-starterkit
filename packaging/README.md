# Exécutable municipal (Windows)

Empaquette le CLI existant (`rudi_commune_starterkit.cli.main`, wizard interactif
inchangé) en un `.exe` Windows autonome, pour un agent municipal non technique :
aucune installation Python, aucune ligne de commande. Voir le plan de cadrage pour
le contexte complet et les décisions actées.

## Déclencher un build

Sur GitHub : onglet *Actions* → workflow **Build executable (Windows, manuel)** →
*Run workflow*. Renseigner :
- `toolkit_ref` : le tag de `rudi-harvest-toolkit` à utiliser (ex. `v0.5.2` —
  **attention, c'est le tag du dépôt `rudi-harvest-toolkit`, pas celui de
  `rudi-commune-starterkit` ; les deux numérotations ne sont pas synchronisées**).
- `version` : le nom de la Release GitHub à créer (ex. `v0.7.0-exe1`).

Équivalent en ligne de commande : `gh workflow run build-executable.yml -f toolkit_ref=v0.5.2 -f version=v0.7.0-exe1`.

Le workflow construit l'exécutable puis publie une **Release GitHub en brouillon**
(pas un simple artifact de workflow — un artifact exige un compte GitHub pour être
téléchargé, inutilisable pour un agent municipal externe). **Rien n'est public tant
que la release reste en brouillon.**

## Avant de publier

1. Ouvrir la Release brouillon créée par le workflow (onglet *Releases*).
2. Télécharger le `.exe` attaché et le tester réellement sur Windows (ou a minima
   sous Wine, voir ci-dessous — Wine ne valide pas le trousseau Windows).
3. Si tout est bon, cliquer **« Publish release »** — c'est ce clic qui rend le
   fichier téléchargeable publiquement. Le lien stable à communiquer aux agents
   municipaux est `https://github.com/simon-sg/rudi-commune-starterkit/releases/latest/download/rudi-commune-starterkit.exe`
   (pointe toujours vers la dernière release *publiée*, jamais un brouillon).

## Itérer en local sous Linux (avant même un build Windows)

Le point d'entrée Python (`rudi-commune-starterkit`, inchangé) peut être testé
directement sans jamais passer par PyInstaller :
```
pip install -e .
rudi-commune-starterkit
```
C'est la boucle de rétroaction la plus rapide pour tout ce qui concerne l'UX du
wizard — `packaging/entrypoint.py` ne fait qu'ajouter la pause finale avant
fermeture, sans toucher au wizard lui-même.

## Smoke-test Windows depuis Linux (Wine)

Pour obtenir un vrai binaire PE Windows sans attendre un run CI à chaque essai :
1. Installer Wine, puis un Python Windows officiel *dans* Wine
   (`wine python-3.12.x-amd64.exe`).
2. Installer les dépendances et PyInstaller *via* ce Python sous Wine :
   `wine python -m pip install -e . pyinstaller pyinstaller-hooks-contrib`.
3. Builder : `wine python -m PyInstaller --onefile --console --name rudi-commune-starterkit packaging/entrypoint.py`.
4. Lancer `dist/rudi-commune-starterkit.exe` sous Wine.

**Limite connue, à ne jamais oublier** : la résolution du backend `keyring`
(trousseau Windows Credential Manager/DPAPI) sous Wine n'est **pas fidèle** à une
vraie session Windows. Le wizard propose réellement d'enregistrer les identifiants
dans ce trousseau — ce chemin de code sera exercé par un usage réel. Un test Wine
positif ne valide donc que la mécanique d'empaquetage et l'UX générale, jamais le
trousseau. Seul un test sur `windows-latest` (CI) ou une vraie machine/VM Windows
valide ce point.

## Lancer un `.exe` déjà construit sous Wine (sans rebuild)

Pour rejouer rapidement un échec signalé sur un vrai poste Windows (ex. diagnostiquer
un message d'erreur), sans refaire tout le build PyInstaller sous Wine (§
précédente) : télécharger l'asset `.exe` d'une Release (brouillon ou publiée) et le
lancer directement sous Wine.

**Piège rencontré en pratique** : lancer `wine rudi-commune-starterkit.exe < un_fichier`
(stdin redirigé classiquement, y compris depuis `/dev/null` ou un fichier vide) échoue
systématiquement avec `[PYI-xxx:ERROR] Failed to start embedded python interpreter!` /
`OSError: [WinError 6] Descripteur invalide` — Wine ne traduit pas correctement un
descripteur Unix redirigé en handle Windows valide pour ce bootloader `--console`.
**Solution** : allouer un vrai pseudo-terminal avec `script` :
```
script -qc "wine rudi-commune-starterkit.exe --code-insee 75056 --rudi-conf conf.json" sortie.log < stdin_vide.txt
```
Avec un vrai tty, l'exécutable fonctionne normalement — y compris la pause finale
« Appuyez sur Entrée pour fermer » qui, cette fois, bloque réellement en attendant une
entrée (contrairement à un stdin non-tty qui lève `EOFError` immédiatement) : prévoir
un `timeout` si le script doit se terminer seul.

Utiliser `--rudi-conf <fichier.json>` (contenu `{"url": ..., "usr": ..., "pwd": ...}`)
plutôt que l'assistant interactif évite d'avoir à scripter toutes les questions du
wizard pour isoler un seul comportement (ex. le test de connexion au nœud).

## Points de friction connus côté utilisateur final (non résolus en v1)

- **SmartScreen** : Windows affichera très probablement « Windows a protégé votre
  ordinateur » au premier lancement (binaire non signé) — l'agent doit cliquer
  « Informations complémentaires » puis « Exécuter quand même ».
- **Antivirus** : un faux positif est possible (comportement heuristique connu pour
  les binaires PyInstaller `--onefile` non signés).
- Les deux points demanderaient une signature de code (certificat payant) pour
  disparaître — hors scope v1, à documenter plutôt qu'à corriger.

## Certificat TLS non reconnu (nœud de test, certificat auto-signé)

Rencontré en pratique sur un nœud de test fourni par un tiers (Rennes Métropole) :
`SSLError ... self-signed certificate in chain`. L'outil ne contourne **jamais** ça
silencieusement — l'agent municipal ne peut pas installer un certificat racine
lui-même, donc un contournement explicite est proposé :
- **Assistant interactif** : un prompt demande de taper `ACCEPTER` après un
  avertissement clair sur le risque d'interception (MITM).
- **Mode scriptable** : flag `--ignorer-certificat-tls` (aucun prompt possible sans
  terminal).

Dans les deux cas, seul un certificat non reconnu déclenche la proposition — jamais
un autre type d'échec (DNS, timeout...), où continuer sans vérifier le certificat ne
résoudrait rien. Une fois accepté, la vérification TLS reste désactivée pour le
reste du run (session HTTP partagée par tout l'outil, pas de retour en arrière sans
relancer).
