# rudi-commune-starterkit

Moissonneur générique : à partir d'un **code INSEE** de commune, de l'URL d'un **nœud
RUDI** et de ses identifiants, peuple ce nœud avec un socle de **14 JDD communaux de
base** (entreprises, associations, budget communal, marchés publics, consommations
gaz/électricité, délibérations, population, qualité de l'eau potable, établissements
scolaires, voies et adresses, élus, résultats d'élections, valeurs foncières, bornes de
recharge électrique).

Contrairement à `moissonneuse-batteuse` (territoire fixe, 43 communes de Rennes
Métropole codées en dur), cet outil est **générique** : aucune table de communes, juste
une résolution dynamique du code INSEE donné.

## État actuel

En cours de construction par lots. Déjà en place :

| Module | Rôle |
|---|---|
| `rudi_commune_starterkit.organisations` | Table curée des producteurs réels des 13 JDD qui en ont un propre (DGFiP, INSEE, Ministère de l'Intérieur...) + `organisation_commune()` (producteur "la commune publie ses données") + `resoudre_producer()` (bascule entre les 3 modes `source`/`commune`/`par-jdd`, avec le cas particulier des délibérations, où la commune est toujours sa propre productrice). |
| `rudi_commune_starterkit.agregation_scrutin` | Agrégation bureau de vote → commune pour un scrutin électoral (format large) : normalisation du code commune (padding incohérent selon les millésimes, Corse-safe), unpivot candidat↔voix, sommation des totaux (inscrits/votants/exprimés...). |

Les 13 modules `datasets/*.py`, `cli.py` (assistant interactif + mode scriptable) et
`registre.py` (liste des modules JDD) sont désormais en place.

## Nouveautés v2 (registre de communes, garde-fous, nettoyage)

- **Registre multi-communes** (`profils_communes.py`, fichier
  `.rudi_commune_starterkit/profils.json`) : l'assistant interactif propose de repartir
  d'une commune déjà enregistrée (code INSEE, URL/identifiants de nœud, mode producteur,
  email de contact) plutôt que de tout ressaisir à chaque run. Mode scriptable :
  `--depuis-registre` (+ `--url-noeud` pour désambiguïser si plusieurs nœuds existent
  pour le même code INSEE).
- **Garde-fou organisation** : avant de lancer la moisson, vérifie si l'organisation de
  la commune existe et est validée sur le nœud. Si absente : propose de la créer (ou la
  crée directement en scriptable) puis s'arrête en attendant la validation de
  l'animateur du portail — sans bloquer les JDD qui n'en dépendent pas. Nouveau code de
  sortie `EXIT_EN_ATTENTE_VALIDATION` (3), prioritaire sur les échecs partiels.
  L'assistant interactif demande désormais aussi l'URL du portail (optionnelle) dès la
  saisie initiale d'une commune, pour que `--vider-commune` reste disponible plus tard
  sans avoir à la ressaisir via le registre.
- **Contact du producteur source** : désormais inclus même en mode `commune` (il
  disparaissait auparavant complètement dès qu'on publiait au nom de la commune).
- **Avertissement email suspect** (`securite.email_suspect()`) : signale un domaine de
  contact sur un TLD réservé (`.local`/`.test`/`.example`/`.invalid`, RFC 2606/6761) sans
  jamais bloquer — un repli d'hygiène, pas une garantie.
- **Em-dash → trait d'union** dans tout le contenu publié (titres/captions).
- **`--vider-commune`** [`--supprimer-organisation`] [`--confirmer SUPPRIMER`] : supprime
  les JDD d'une commune déjà publiés par ce socle (nœud + portail), avec suppression de
  l'organisation en option (détachement producteur d'abord si nécessaire, arrêt en
  attente de validation sinon). Nécessite `conf["url_portail"]`/`--url-portail`.

## Dépendance

Dépend de [`rudi-harvest-toolkit`](../rudi-harvest-toolkit) (chemin local), en particulier
des modules ajoutés pour ce projet : `commune` (résolution code INSEE → nom/géographie/
SIREN), `fichier_hybride` (média `FILE` dont l'URL reste distante), `tabular` (lecteur CSV
streaming), `datagouv` (résolution dataset → ressource), `download_cache` (téléchargement
avec cache disque).

## Installation en mode éditable

```bash
pip install --user --break-system-packages -e /media/simon/DATA4T/Dev/rudi-commune-starterkit
```

Si l'import échoue après coup avec un module manquant du toolkit alors qu'il existe bien
dans le code source, c'est le piège classique du cache wheel pip figeant une ancienne
version éditable — réinstaller en forçant :

```bash
pip install --user --break-system-packages --no-cache-dir --force-reinstall \
  --no-deps -e /media/simon/DATA4T/Dev/rudi-harvest-toolkit
```

## Tests

```bash
python3 -m pytest tests/
```

Logique pure, zéro réseau (fixtures en dur).

## Configuration du nœud RUDI cible

Voir `conf/rudi_node.example.json` — à copier en `conf/rudi_node.json` (gitignoré) pour un
usage non-interactif, ou à saisir via l'assistant CLI (à venir) qui ne l'écrit en clair
qu'en dernier recours (repli sur le trousseau système `keyring` en priorité).
