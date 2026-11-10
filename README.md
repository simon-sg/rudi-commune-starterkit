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

## Fonctionnalités

| Module | Rôle |
|---|---|
| `datasets/*.py` (13 modules) + `_commun.py` | Un module par JDD (voir liste ci-dessus) — construction des métadonnées RUDI et des contacts, publication via `rudi_harvest_toolkit`. |
| `description_commune.py` | `construire_description_commune(commune)` — vrai résumé Wikipédia de la commune (désambiguïsé par code INSEE), attribution CC BY-SA intégrée au texte, second paragraphe maire actuel (RNE, pas Wikidata)/gentilé/superficie si disponibles, repli générique explicite sinon. |
| `licences.py` | `licence_pour_jdd(cle_jdd, licence_dynamique=None)` — point d'entrée unique pour la licence de chaque JDD : dynamique depuis data.gouv.fr si disponible, sinon table curée (`LICENCES_CUREES`) ; `LicenceInconnueError` si ni l'une ni l'autre — jamais de repli silencieux etalab-2.0. |
| `organisations.py` | Table curée des producteurs réels des 13 JDD qui en ont un propre (DGFiP, INSEE, Ministère de l'Intérieur...) ; `organisation_commune()` (producteur « la commune publie ses données ») ; `resoudre_producer()` (bascule entre les 3 modes `source`/`commune`/`par-jdd`, avec le cas particulier des délibérations, où la commune est toujours sa propre productrice) ; `CONTACTS_ORGANISATIONS`/`contact_curated_pour_jdd()` (contacts producteurs confirmés par recherche, distincts de `producer`). |
| `agregation_scrutin.py` | Agrégation bureau de vote → commune pour un scrutin électoral (format large) : normalisation du code commune (padding incohérent selon les millésimes, Corse-safe), unpivot candidat↔voix, sommation des totaux (inscrits/votants/exprimés...). |
| `registre.py` | Liste des 14 modules JDD, point d'entrée de la moisson complète. |
| `profils_communes.py` | Registre multi-communes (`.rudi_commune_starterkit/profils.json`) : mémorise code INSEE, URL/identifiants de nœud, mode producteur, email de contact — évite de tout ressaisir à chaque run. |
| `vidage.py` | « Vider une commune » : supprime les JDD déjà publiés par ce socle (voir plus bas). |
| `securite.py` | `email_suspect()` — avertit (sans bloquer) si un contact utilise un domaine sur un TLD réservé (`.local`/`.test`/`.example`/`.invalid`). |
| `cli.py` | Assistant interactif + mode scriptable, point d'entrée (`python3 -m rudi_commune_starterkit.cli`). |

### Qualité du contenu publié (v3)

Au-delà de la mécanique de publication, le contenu des 13 JDD est rigoureux par
construction, jamais deviné — détail complet dans `CHANGELOG.md`/`BACKLOG.md` :
- **Descriptions réelles** des communes (Wikipédia + maire RNE/gentilé/superficie) et
  des JDD (quoi/comment construit/variables/fréquence/source, mots-clés enrichis).
- **Licence réelle par JDD** — dynamique depuis data.gouv.fr si disponible, sinon une
  table curée par recherche ; un JDD sans licence confirmée échoue proprement plutôt
  que de publier une licence devinée.
- **Contacts producteurs réels** (table curée + extraction dynamique data.gouv.fr),
  priorité sur le repli générique `nom@example.org`.
- **Géolocalisation** (bbox) sur les 13 modules, calculée depuis le contour réel de
  la commune.

### Dates et GeoJSON par ligne (v4)

- **Dates réelles** sur tous les modules sauf `eau_potable.py` : dynamique
  data.gouv.fr, mtime du cache, fiche catalogue ODS/Melodi, ou MAX sur les
  enregistrements déjà chargés selon le module — jamais inventée (`eau_potable.py`
  reste sans date, aucun mécanisme exploitable côté source, documenté en BACKLOG).
- **GeoJSON par ligne** sur 5 des 13 modules (`adresses`, `etablissements_scolaires`,
  `entreprises`, `associations`, `irve`) pour une vue carte native, en plus du CSV —
  lignes sans coordonnée exploitable silencieusement omises, jamais une géométrie
  inventée (`eau_potable.py` reste sans GeoJSON, aucune coordonnée disponible côté
  source).

### Garde-fou organisation

Avant de lancer la moisson, vérifie si l'organisation de la commune existe et est
validée sur le nœud. Si absente : propose de la créer (ou la crée directement en
mode scriptable) puis s'arrête en attendant la validation de l'animateur du portail
— sans bloquer les JDD qui n'en dépendent pas. Code de sortie dédié
`EXIT_EN_ATTENTE_VALIDATION` (3), prioritaire sur les échecs partiels.

### Vider une commune (`--vider-commune`)

```bash
python3 -m rudi_commune_starterkit.cli \
  --depuis-registre --code-insee 35120 \
  --vider-commune --supprimer-organisation --confirmer SUPPRIMER
```

Supprime les JDD d'une commune déjà publiés par ce socle (nœud, avec relais
automatique du nœud vers le portail — aucun appel portail séparé nécessaire) et,
avec `--supprimer-organisation`, l'organisation de la commune :

1. Si d'autres JDD référencent encore l'organisation sans être suivis par ce socle
   (publiés par un autre outil sur le même nœud, ou un test manuel), leur
   suppression est détectée et **proposée** séparément (confirmation `SUPPRIMER`
   dédiée) plutôt que de bloquer sans recours.
2. Si le producteur est encore rattaché (`linked_producer_status: VALIDATED`), un
   détachement est demandé — la suite nécessite la validation de l'animateur du
   portail dans l'UI Strukture, puis un nouveau run.
3. Une fois détaché, **la suppression de l'organisation côté portail n'est jamais
   automatisée** : aucun relais nœud n'existe pour cette opération précise (seuls
   les actes attacher/détacher existent), et aucun compte applicatif séparé n'a
   jamais existé pour ce socle. Seul l'animateur (l'utilisateur) peut la faire, dans
   l'UI Strukture. Une fois cette suppression portail faite à la main, relancer en
   tapant `SUPPRIME_PORTAIL` (mot distinct de `SUPPRIMER`) pour nettoyer la copie
   locale du nœud — tant que ce n'est pas confirmé, l'organisation reste détachée
   mais présente des deux côtés (état dégradé acceptable, jamais d'orpheline créée).

Aussi disponible depuis l'assistant interactif : en reprenant une commune du
registre, un choix *« Lancer la moisson / Vider cette commune »* propose le vidage
sans passer par le mode scriptable.

## Installation

Layout `src/`, backend `setuptools`. Environnement Debian « externally-managed »,
d'où `--break-system-packages` :

```bash
pip install --user --break-system-packages -e /media/simon/DATA4T/Dev/rudi-commune-starterkit
```

Si l'import échoue après coup avec un module manquant du toolkit alors qu'il existe
bien dans le code source, c'est le piège classique du cache wheel pip figeant une
ancienne version éditable — réinstaller en forçant :

```bash
pip install --user --break-system-packages --no-cache-dir --force-reinstall \
  --no-deps -e /media/simon/DATA4T/Dev/rudi-harvest-toolkit
```

## Configuration du nœud RUDI cible

Voir `conf/rudi_node.example.json` — à copier en `conf/rudi_node.json` (gitignoré)
pour un usage non-interactif (`--rudi-conf`), ou à saisir via l'assistant interactif,
qui propose le trousseau système (`keyring`) avant tout repli en clair.

## Utilisation

**Assistant interactif** (recommandé pour une première commune ou une suppression) :

```bash
python3 -m rudi_commune_starterkit.cli
```

Propose de repartir d'une commune du registre ou d'en saisir une nouvelle ; demande
ensuite le mot de passe (trousseau système en priorité), le mode de publication
(`source`/`commune`/`par-jdd`), l'email de contact si nécessaire.

**Mode scriptable** (non interactif, pour l'automatisation) — principaux flags :

| Flag | Rôle |
|---|---|
| `--code-insee` | Requis. Code INSEE de la commune cible. |
| `--depuis-registre` [`--url-noeud`] | Résout nœud/identifiants/mode/contact depuis le registre local plutôt que depuis les flags suivants ; `--url-noeud` désambiguïse si plusieurs nœuds existent pour le même code INSEE. |
| `--url-noeud` / `--usr` / `--rudi-conf` / `--utiliser-trousseau` | Identifiants du nœud, en alternative au registre. |
| `--organisation-producteur {source,commune,par-jdd}` | Mode de publication (défaut `source`). |
| `--organisation-par-jdd` | Fichier JSON JDD → `commune`\|`source`, pour le mode `par-jdd`. |
| `--contact-commune` | Email de contact, obligatoire si au moins un JDD publie au nom de la commune. |
| `--only` / `--skip` | Clés de JDD séparées par des virgules, pour limiter la moisson. |
| `--forcer-maj` | Republie même les JDD inchangés. |
| `--dry-run` | Aucun appel réseau mutant (RUDI) — rapporte ce qui serait fait. |
| `--etat` | Fichier d'état JSON (hash par `local_id`), par défaut `.etat_rudi_commune_starterkit/<code_insee>.json`. |
| `--url-portail` | URL du portail — requis par `--vider-commune`/`--supprimer-organisation`. |
| `--vider-commune` [`--supprimer-organisation`] [`--confirmer SUPPRIMER`] | Voir « Vider une commune » ci-dessus. |

Exemple, moisson complète d'une commune déjà enregistrée :

```bash
python3 -m rudi_commune_starterkit.cli --depuis-registre --code-insee 35120
```

## Dépendance

Dépend de [`rudi-harvest-toolkit`](../rudi-harvest-toolkit) (chemin local), en
particulier des modules ajoutés pour ce projet : `commune` (résolution code INSEE →
nom/géographie/SIREN), `fichier_hybride` (média `FILE` dont l'URL reste distante),
`tabular` (lecteur CSV streaming), `datagouv` (résolution dataset → ressource),
`download_cache` (téléchargement avec cache disque).

## Tests

```bash
python3 -m pytest tests/
```

Logique pure, zéro réseau (fixtures en dur).

## Historique

Voir [`CHANGELOG.md`](CHANGELOG.md).
