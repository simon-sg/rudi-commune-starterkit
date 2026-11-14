# Changelog

## 0.7.1 — 2026-11-14

### Correctifs trouvés en testant l'exécutable v0.7.0 (Windows + Linux, nœud réel)

- **Mot de passe pouvait s'afficher en clair** (`securite.lire_mot_de_passe`) : sous
  le binaire PyInstaller Linux (`/dev/tty` s'ouvre mais `termios.tcgetattr` échoue
  avec ENOTTY), `getpass` dégradait silencieusement vers une saisie échoique — un cas
  que `sys.stdin.isatty()` seul ne détecte pas. Élève maintenant cet avertissement en
  erreur (`AbsenceTerminalError`) avant toute saisie, plutôt que de laisser le mot de
  passe s'afficher. Volontairement multiplateforme (Windows dégrade aussi via
  `sys.stdin` substitué, pas seulement le cas Linux/ENOTTY qui l'a révélé).
- **Reprise après validation d'organisation sans retour visuel** : entre la question
  « [Entrée] pour vérifier... » et le début effectif du premier JDD, un délai réseau
  (résolution des organisations, description de la commune) pouvait laisser l'écran
  silencieux. Ajout d'un message « Vérification en cours, merci de patienter… ».
- **Hint « URL catalogue » trompeur** : « laissez vide dans la grande majorité des
  cas » encourageait une déduction automatique qui suppose la disposition Docker
  standard (port 3030) — fausse sur un nœud hébergé par un tiers, le cas normal pour
  un agent municipal. Reformulé pour inviter à demander l'URL à l'administrateur du
  nœud plutôt que de la déduire à l'aveugle (guide HTML mis à jour en miroir).
- **Wording incohérent « administrateur de votre territoire »** : uniformisé sur
  « administrateur du nœud » partout dans le wizard et le guide HTML (le
  « territoire » prêtait à confusion avec le territoire de la commune elle-même).
- Dépend de `rudi-harvest-toolkit` 0.5.4 (cache `_api_version`, timeouts organisation
  abaissés, reprise partielle Range sur coupure réseau — voir son propre changelog).

## 0.7.0 — 2026-11-13

### Guide utilisateur HTML (GitHub Pages)

Nouveau site statique (MkDocs Material, `guide/` + `docs/` jamais versionné) pour un
agent municipal non technique : une partie « Guide d'utilisation » (prérequis,
téléchargement, avertissements Windows normaux, pas-à-pas écran par écran,
relancer/mettre à jour, annuler une publication de test, dépannage) suivie des 13
fiches de données regroupées par thème, puis FAQ/glossaire/licences. Généré
entièrement depuis le code (`registre.py` pour les fiches, `guide/contenu_statique.py`
pour le reste) — aucun Markdown édité à la main, aucun appel réseau à la génération.
Déploiement manuel (`.github/workflows/deploy-docs.yml`, GitHub Pages).

### Reformulation du wizard interactif pour un agent municipal non technique

`cli.py` : jargon interne (clé technique de JDD, « producteur Rudi », « la moisson »,
nom d'un flag CLI cité dans un prompt interactif) remplacé par du langage métier —
voir BACKLOG.md pour le détail. Comportement et codes de sortie inchangés.

### Backlog v5 — doublon d'organisation, 404 DECP, menu Quitter, attente validation

4 corrections ponctuelles trouvées en testant l'exécutable municipal sur un nœud réel
(Rennes Métropole, 2026-11-13) :

- **Doublon d'organisation** (corrigé côté `rudi-harvest-toolkit` >= 0.5.3) :
  `organization_id` déterministe au lieu d'aléatoire — une organisation créée par une
  tentative précédente n'est plus jamais dupliquée par un nouvel essai.
- **404 sur le dataset DECP** (`marches_publics.py`) : message clair et actionnable au
  lieu du texte brut `requests` quand le dataset tiers (Colin Maudry, mis à jour quasi
  quotidiennement) devient introuvable.
- **Menu « Quitter » (`q`)** dans l'assistant interactif — jusqu'ici seul Ctrl+C
  permettait de sortir proprement.
- **Détection des doublons de commune** : la branche « Nouvelle commune » signale
  désormais un profil existant pour le même code INSEE (éventuellement sur un autre
  nœud) et propose de le reprendre directement.
- **Attente de validation animateur sans relance complète** : après une création
  d'organisation en attente de validation, l'assistant propose de vérifier sur demande
  et reprend automatiquement la suite du run dès que validée (au lieu d'obliger à tout
  relancer).

### Exécutable Windows autonome (agent municipal)

Nouveau mode de distribution, sans changement fonctionnel du CLI existant : un
`.exe` Windows (`packaging/entrypoint.py` + PyInstaller `--onefile`) empaquette
`rudi_commune_starterkit.cli.main` tel quel (même wizard interactif complet — code
INSEE, URL du nœud RUDI, identifiants, mode producteur, etc. — rien n'est pré-rempli
ni simplifié), pour qu'un agent municipal non technique puisse peupler son propre
nœud RUDI sans installer Python ni taper de ligne de commande. Build déclenché
manuellement (`.github/workflows/build-executable.yml`, `workflow_dispatch`),
publié en Release GitHub brouillon pour revue avant publication publique (voir
`packaging/README.md`).

Diagnostic d'échec de connexion amélioré (dépend de `rudi-harvest-toolkit`
>= 0.5.1) : le message affiché en cas d'échec montre maintenant la vraie cause
(exception réseau ou code HTTP) au lieu du générique « nœud injoignable ou
identifiants invalides », qui était trompeur — ce test ne vérifie jamais les
identifiants. Nouveau flag `--ignorer-certificat-tls` (mode scriptable) / prompt
de confirmation (assistant interactif) pour continuer malgré un certificat TLS
non reconnu (ex. certificat auto-signé sur un nœud de test) — jamais par défaut,
avertissement explicite sur le risque d'interception à chaque utilisation.

L'exécutable affiche désormais un message de chargement au démarrage, et
propose de relancer l'assistant depuis le début (au lieu de refermer puis
redoubler-cliquer) en cas d'échec.

## 0.6.0 — 2026-11-11

### Historique budget complet (Axe 4, changement cassant) + glossaires

`budget.py` publie désormais l'historique complet disponible (2000-2025, 26
exercices, selon disponibilité pour la commune) au lieu du seul dernier exercice
(2023-2024) — union de 12 datasets Opendatasoft distincts de la DGFiP, harmonisés par
nom de colonne (schémas de 173 à 254 colonnes selon l'exercice). **Changement de
modèle de média** : n'est plus un FILE hybride passthrough (impossible à maintenir
avec 12 sources à unir) mais un CSV local unique écrit par ce socle (une ligne par
exercice réellement trouvé, `an` en tête). Dégradation par dataset (pas globale) si
une requête échoue pour la commune : avertissement + note visible dans `limites`,
échec du run seulement si les 12 échouent simultanément.

**Correction de recherche notable** : une première vérification avait conclu à une
couverture 2008-2025 en ne regardant que l'*existence* des 12 datasets sans lire leur
*contenu* réel — en creusant davantage, le dataset nommé `2008` s'est révélé contenir
en réalité les exercices 2000 à 2008 (champ `an` interne), rétablissant la couverture
complète 2000-2025 sans trou. Voir `BACKLOG.md` pour le détail.

Nouveau glossaire (paramètre `glossaire` de `construire_description_structuree()`,
disponible depuis la v0.5.0) sourcé depuis la fiche de métadonnées DGFiP officielle
(`Maquette_commune.ods`) : ~43 codes structurants (`prod`, `impo1`, `dgf`, `caf`,
`dette`...) + la convention de préfixes f/m/r/rm, restreint aux colonnes
effectivement publiées pour la commune.

Glossaires ajoutés aux 3 autres modules à nomenclature initialement jugée opaque,
après vérification en direct de chacun (pas une curation à l'aveugle) :
- `immobilier_dvf.py` : `id_mutation`, `id_parcelle` (les autres codes DVF ont déjà
  leur libellé en clair dans une colonne adjacente, vérifié sur un échantillon réel).
- `marches_publics.py` : `codeCPV` (seul code réellement opaque, le reste du schéma
  DECP porte déjà des labels clairs).
- `eau_potable.py` : **aucun glossaire ajouté** — la prémisse initiale (codes
  paramètres SISE-Eaux à glosser) s'est révélée fausse (chaque `code_parametre` est
  déjà accompagné de son libellé en clair) ; les codes mono-lettre réellement
  opaques (`code_type_parametre`, `code_lieu_analyse`, `conformite_*_prelevement`)
  n'ont aucune légende publique trouvée — documentés en `limites`, pas inventés.

## 0.5.0 — 2026-11-11

### Glossaire nuance + marqueur `sieges_disponibles` (incrément C)

La description riche du JDD élections inclut désormais un glossaire des codes nuance
(`LDVD`, `LFI`, `LUG`…) effectivement rencontrés dans le fichier publié pour la
commune, sourcé depuis la ressource officielle `nuances.csv` du jeu agrégé (2 versions
coexistent selon la circulaire — la plus récente est résolue automatiquement). Le
fichier source reste complet et fait autorité ; seul l'affichage est restreint aux
codes présents pour ne pas publier une table de 51 entrées sur une commune qui n'en
utilise que 2 ou 3.

Nouvelle colonne booléenne `sieges_disponibles` (vraie seulement pour les lignes
`2026_muni_t1` enrichies avec succès par la jointure de l'incrément B) : rend la
limite déjà documentée en texte visible ligne par ligne dans le CSV lui-même, pas
seulement dans la description.

**Axe 5 (fusion des JDD élections) désormais complet : incréments A (fusion + Parquet),
B (jointure élu/sièges) et C (glossaire + marqueur) tous livrés.**

### Jointure élu/sièges, municipales 2026 T1 (incrément B)

Les lignes `2026_muni_t1` du JDD fusionné (incrément A, ci-dessous) portent désormais
5 colonnes supplémentaires — `elu`, `sieges_conseil_municipal`,
`sieges_conseil_communautaire`, `libelle_liste`, `libelle_abrege` — par jointure
`(code_insee, no_panneau)` avec la source municipales 2026 T1 actuelle (seule source à
porter ces colonnes, absentes du jeu agrégé). Nouveau `agregation_scrutin.
joindre_elu_sieges()` : n'enrichit que `2026_muni_t1` (jamais `2026_muni_t2`, qui n'a
pas de sièges exploitables dans la source actuelle — conseil pas encore constitué),
ne lève jamais sur une clé absente (commune au second tour : cas normal, pas une
erreur).

Enrichissement **optionnel** : un échec de cette source secondaire (réseau, etc.)
dégrade proprement (avertissement, colonnes vides) sans jamais faire échouer tout le
run — le JDD fusionné a déjà toute sa valeur sans cette jointure.

### Fusion des JDD élections : 56 scrutins, 1999-2026 (changement cassant)

**Changement cassant** : `datasets/elections.py` ne publie plus un seul scrutin
(« municipales 2026, 1er tour ») mais l'historique complet disponible dans le jeu
agrégé data.gouv.fr « donnees-des-elections-agregees » — présidentielles,
législatives, municipales, européennes, régionales, départementales et cantonales, de
1999 à 2026 (vérifié par comptage exhaustif du fichier source : 56 élections
distinctes, 7 types). Le fichier publié change de nom
(`elections_{code_insee}.csv`, plus `elections_municipales_2026_t1_{code_insee}.csv`)
et de schéma (colonnes `annee`/`type_election`/`tour` en tête, ratios natifs `ratio_*`
du jeu agrégé à la place de `pourcentage_exprimes`). Titre, synopsis, fréquence de
mise à jour, légende du média et mots-clés mis à jour en conséquence (plus aucune
mention de « municipales » seule).

Source basculée sur des fichiers **Parquet** (232 Mo par commune et par run, ~12x
moins que les CSV sources du même jeu mais ~16x plus que l'ancien JDD mono-scrutin —
un coût assumé, pas un gain net) via la nouvelle fonction toolkit
`lire_parquet_filtre()`. Nouveau chemin d'agrégation `agregation_scrutin.
agreger_long_vers_commune()` (format long, group by élection + identité candidat —
distinct du chemin bureau→commune existant, qui reste disponible pour un futur
scrutin publié en format large), plus `recalculer_ratios()`, `TYPES_ELECTION`,
`TypeElectionInconnu`, `decomposer_id_election()`.

Colonnes `code_canton`/`libelle_canton`/`code_circonscription`/
`libelle_circonscription` préservées (jointure au niveau bureau de vote, avant
l'agrégation commune).

**Limites documentées (description riche, `limites`)** : municipales 2008 partielles
(communes >3500 hab. seulement), pas de second tour pour les européennes, colonnes
`elu`/`sieges_*` (incrément B, ci-dessus) disponibles seulement pour les municipales
2026 des communes pourvues dès le premier tour.

## 0.4.0 — 2026-11-10

### Dates réelles pour 9 des 10 modules non-data.gouv (Axe 2, v4)

Tous les JDD publiaient jusqu'ici soit une date dynamique data.gouv.fr (6 modules),
soit rien (`date_source` absent, le nœud dérivant une date par défaut). Cette version
câble une date réelle, dérivée de la source, pour les 9 modules restants où un
mécanisme existe — jamais une date inventée (`rudi_harvest_toolkit.http_dates`,
nouveau, garantit `None` plutôt qu'une date devinée sur toute entrée non parsable) :

- `adresses.py`/`immobilier_dvf.py` : mtime du fichier en cache (cohérence
  date/contenu garantie par construction, TTL 30 jours).
- `irve.py` : MAX(`last_modified`) sur les enregistrements filtrés, triés (une seule
  requête réutilisée, pas d'appel supplémentaire).
- `etablissements_scolaires.py`/`budget.py` : `metas.default.modified` de la fiche
  catalogue Opendatasoft (requête de métadonnées légère).
- `entreprises.py`/`associations.py` : MAX sur `date_mise_a_jour`/
  `date_mise_a_jour_insee`/`date_mise_a_jour_rne`, par établissement.
- `deliberations.py` : MAX(`date_acte`, `date_publication`) sur les actes déjà
  chargés.
- `population.py` : fiche catalogue Melodi (`GET /melodi/catalog/{id}`, sans
  authentification), best-effort.

**Limite connue, documentée (pas une régression)** : `eau_potable.py` reste sans date
réelle — aucun champ de mise à jour de jeu exploitable côté source (Hub'eau n'expose
qu'une date de prélèvement par ligne).

### GeoJSON par ligne pour 5 des 6 modules candidats (Axe 3, v4)

Chaque JDD géolocalisé publie désormais, en plus de son CSV, un second média GeoJSON
(`rudi_harvest_toolkit.geojson`, nouveau) pour une vue carte native sur le portail :

- `adresses.py` : depuis les colonnes `lon`/`lat` natives du CSV BAN.
- `etablissements_scolaires.py` : export GeoJSON natif de l'ODS (confirmé correct
  pour ce dataset, pas de parsing local).
- `entreprises.py`/`associations.py` : `latitude`/`longitude`, déjà fournis par
  établissement par l'API `recherche-entreprises.api.gouv.fr` (pas de géocodage BAN
  nécessaire).
- `irve.py` : parsing local depuis `consolidated_longitude`/`consolidated_latitude` —
  **l'export GeoJSON natif de cette source inverse les coordonnées** (confirmé sur
  plusieurs communes), jamais utilisé.

Une ligne sans coordonnée exploitable est silencieusement omise de la carte (pas une
géométrie inventée) ; un avertissement console signale le nombre de lignes omises.

**Limite connue, documentée (pas une régression)** : `eau_potable.py` reste sans
GeoJSON — aucune coordonnée géographique disponible côté source. `entreprises.py`/
`associations.py` : une entreprise/association sans établissement correspondant
publié produit 0 point même si son siège est géolocalisé (conséquence de ce que
publie déjà `simplifier_resultat_entreprise()`, pas un bug introduit ici).

## 0.3.1 — 2026-11-10

### Migration d'urgence de la source DVF (Axe 0, v4)

La ressource départementale consommée par `immobilier_dvf.py`
(`files.data.gouv.fr/geo-dvf/latest/csv/{année}/departements/{dep}.csv.gz`) était
explicitement annoncée pour suppression (« suppression au 31/11/2026 ») sur le dataset
data.gouv.fr. Vérifié en direct : aucun accès par département ne subsiste dans ce
dataset — migration vers la ressource nationale unique **« DVF juillet 2021 - juin
2026 - fichier unique »** (`dvf.csv.gz`, 609 Mo), résolue dynamiquement via
`datagouv.get_dataset_metadata()`/`selectionner_ressource()` (jamais une URL figée —
le nom physique du fichier change à chaque republication côté data.gouv.fr).

**Changement de comportement** : plus de sondage par année (`NB_ANNEES_A_SONDER`
supprimé) ni d'union de schéma entre millésimes — un seul fichier, un seul appel
réseau. La colonne `annee_millesime_dvf` (ajoutée artificiellement par l'ancien code)
disparaît : les années publiées sont désormais dérivées de la colonne native
`date_mutation`, réellement présente dans la source.

**Limite de couverture** : la nouvelle source couvre juillet 2021 à juin 2026 — pas de
régression par rapport à l'ancienne source (qui ne remontait déjà que ~5-6 ans).

## 0.3.0 — 2026-11-10

### description de commune : second paragraphe (maire/gentilé/superficie)

Correction post-livraison de la v3, suite à un test réel sur Acigné : l'intro
Wikipédia réelle (192 caractères) était rejetée par le garde-fou anti-ébauches
(`longueur_min=250`), alors que ce n'était pas une ébauche — juste une petite commune
peu documentée. `longueur_min` abaissé à 80 (`rudi_harvest_toolkit.wikipedia`).

En complément, un second paragraphe compense désormais un intro court :
- **Maire actuel** — nouveau `rudi_harvest_toolkit.rne.maire_actuel()`, source
  Répertoire National des Élus (Ministère de l'Intérieur), **pas** Wikidata (propriété
  P6, trouvée affichant un mandat de 2014 sans date de fin alors que le RNE listait
  déjà le mandat renouvelé en mars 2026 — Wikidata ne signale jamais son obsolescence).
- **Gentilé et superficie** (Wikidata P1549/P2046) — nouvelle requête SPARQL
  complémentaire dans `wikipedia.resumer_commune_wikipedia()`, réutilisant le QID déjà
  résolu ; omis si absents sur Wikidata (gentilé souvent non renseigné pour les petites
  communes), jamais devinés.

Paragraphe entier omis si aucune des trois informations n'est disponible.

### v3 : descriptions, contacts, licences, dates, géographie (voir BACKLOG.md)

Qualité du contenu publié par les 13 JDD, pas la mécanique du socle — détail complet
dans `BACKLOG.md`. **Republication unique des 13 JDD à l'activation de cette version**
(description + licence + géographie changent le hash de contenu de chacun), pas des
événements isolés par commit :

- **Descriptions des communes réelles** (`rudi_harvest_toolkit.wikipedia` +
  `description_commune.py`) : résumé Wikipédia désambiguïsé par code INSEE (Wikidata
  `P374`), attribution CC BY-SA intégrée au texte, repli explicite si absent.
- **Descriptions riches des 13 JDD** (`rudi_harvest_toolkit.description`) : quoi/comment
  construit/variables publiées/fréquence/source, mots-clés enrichis par module.
- **Licence réelle par JDD, jamais de repli silencieux etalab-2.0** (`licences.py`) :
  dynamique depuis data.gouv.fr pour `elus`/`elections`/`marches_publics`, curée pour les
  10 autres ; un JDD sans licence confirmée échoue proprement (`ECHEC`) plutôt que de
  publier une licence devinée.
- **Contacts producteurs réels** (`CONTACTS_ORGANISATIONS` + `rudi_harvest_toolkit.
  contacts`, migré depuis `moissonneuse-batteuse`) : chaîne de priorité contact
  dynamique data.gouv > contact curé confirmé > repli générique.
- **Remplacement de la source `marches_publics.py` (DECP)** : l'ancienne source
  (`data.economie.gouv.fr`) était touchée par un trou de remontée AIFE non confirmé
  résolu ; remplacée par le jeu consolidé indépendant de Colin Maudry (data.gouv.fr),
  mise à jour quasi quotidienne, avec avertissement CLI si la source se fige.
- **Géographie (bbox) sur les 13 modules** (`geography_pour_commune()`) : la fiche
  catalogue affiche désormais une localisation, calculée depuis le contour de la commune
  (`bbox_depuis_contour()`, toolkit).
- Nouveau `BACKLOG.md` à la racine, tenu à jour à chaque axe.

### entreprises/associations/élections/délibérations : CSV au lieu de JSON

Ces 4 JDD n'avaient jamais d'onglet « tableau » sur le portail : leur seul média
`FILE` était en `application/json`, format que le front-office ne reconnaît pas pour
l'aperçu tabulaire (seuls CSV/XLS/XLSX le sont). Republiés en CSV `;` :

- `entreprises.py`/`associations.py` : nouvelle `lignes_csv_entreprises()`
  (`_commun.py`) — dénormalise une ligne par établissement, champs entreprise
  répétés ; champs établissement préfixés `etablissement_` (collision de noms avec
  `activite_principale`/`etat_administratif`, présents aux deux niveaux).
- `elections.py` : dénormalise une ligne par liste candidate, totaux de la commune
  (`Inscrits`/`Votants`/...) répétés sous `totaux_*`.
- `deliberations.py` : déjà une liste plate d'actes, conversion directe.

`population.py` et `eau_potable.py` restent en JSON hybride (URL externe jamais
retéléchargée, décision déjà actée) — ni Hub'eau ni l'API Melodi n'offrent d'export
CSV natif (testé `format=csv` et `Accept: text/csv`, les deux ignorent/rejettent),
et basculer en CSV supposerait d'abandonner le hybride pour ces deux JDD. Laissé tel
quel pour l'instant, sujet distinct.

### organisation : plus d'appel portail automatisé à la suppression

Suite directe de l'entrée précédente : une fois le producteur détaché et validé par
l'animateur du portail, la suppression de l'organisation **elle-même** côté Strukture
échouait toujours en `401` (`demander_suppression_organisation()`). Vérifié cette
fois dans le code source du nœud que ce n'est pas un problème d'identifiants à
trouver : seuls les actes `attach`/`detach`/`has_task` sont relayés par le nœud pour
une organisation, jamais la suppression — aucun relais n'existe pour cette opération
précise, contrairement à la création et au détachement.

`vider_commune()` ne tente donc plus cet appel. Une fois le détachement validé, il
demande désormais une confirmation explicite et distincte (`SUPPRIME_PORTAIL`,
différente du `SUPPRIMER` utilisé pour le reste) attestant que l'utilisateur —
seul l'animateur du portail a cet accès — a lui-même supprimé l'organisation dans
l'UI Strukture ; cette confirmation déclenche alors le nettoyage de la copie locale
du nœud. Tant qu'elle n'est pas donnée, l'organisation reste détachée mais présente
des deux côtés — état dégradé volontaire, jamais d'orpheline créée.

### vidage : plus d'appel portail séparé pour les datasets

`vider_commune()` appelait `supprimer_dataset_portail()` (OAuth2 direct au portail)
en plus de `supprimer_dataset()` (nœud) pour chaque JDD supprimé — ce second appel
échouait systématiquement en `401` dès qu'un profil n'a pas de compte ROBOT portail
dédié (le cas général : ce socle n'en a jamais eu). Confirmé par le code source du
nœud que `supprimer_dataset()` seul déclenche déjà ce relais automatiquement, avec
l'identité propre du nœud — un seul appel par JDD désormais, dans les deux boucles de
suppression (JDD suivis par l'état local et JDD non suivis détectés sur le nœud).

### `--vider-commune` : détecte et propose les JDD non suivis

Avec `--supprimer-organisation`, si d'autres JDD référencent encore l'organisation
sans être suivis par ce socle (publiés par un autre outil sur le même nœud, ou un
test manuel), leur suppression est désormais détectée et **proposée** séparément
(confirmation `SUPPRIMER` dédiée) plutôt que de bloquer la suppression de
l'organisation sans aucun recours.

### corrige deux bugs réels trouvés en conditions de production

- `vider_commune()` plantait avec `KeyError: 'local_id'` sur un JDD restant publié
  par un autre outil (le champ est optionnel dans le schéma RUDI) — repli sur
  `global_id`.
- `vider_commune(..., supprimer_organisation=True)` court-circuitait avec « Rien à
  supprimer » dès que l'état local était vide, alors que l'organisation pouvait
  légitimement être la seule chose restant à traiter (ex. relance après un run
  précédent qui a déjà supprimé tous les JDD).

## 0.2.0 — Registre de communes, garde-fous, nettoyage (v2)

- **Registre multi-communes** (`profils_communes.py`, fichier
  `.rudi_commune_starterkit/profils.json`) : l'assistant interactif propose de
  repartir d'une commune déjà enregistrée (code INSEE, URL/identifiants de nœud,
  mode producteur, email de contact) plutôt que de tout ressaisir à chaque run.
  Mode scriptable : `--depuis-registre` (+ `--url-noeud` pour désambiguïser si
  plusieurs nœuds existent pour le même code INSEE).
- **Garde-fou organisation** : avant de lancer la moisson, vérifie si l'organisation
  de la commune existe et est validée sur le nœud. Si absente : propose de la créer
  (ou la crée directement en scriptable) puis s'arrête en attendant la validation de
  l'animateur du portail — sans bloquer les JDD qui n'en dépendent pas. Nouveau code
  de sortie `EXIT_EN_ATTENTE_VALIDATION` (3), prioritaire sur les échecs partiels.
- **Contact du producteur source** : désormais inclus même en mode `commune` (il
  disparaissait auparavant complètement dès qu'on publiait au nom de la commune).
- **Avertissement email suspect** (`securite.email_suspect()`) : signale un domaine
  de contact sur un TLD réservé (`.local`/`.test`/`.example`/`.invalid`, RFC
  2606/6761) sans jamais bloquer — un repli d'hygiène, pas une garantie.
- **Em-dash → trait d'union** dans tout le contenu publié (titres/captions).
- **`--vider-commune` [`--supprimer-organisation`] [`--confirmer SUPPRIMER`]** :
  première version, suppression des JDD d'une commune déjà publiés par ce socle,
  avec suppression de l'organisation en option.

## 0.1.0 — Premier socle

13 modules `datasets/*.py` (entreprises, associations, budget communal, marchés
publics, consommations gaz/électricité, délibérations, population, qualité de l'eau
potable, établissements scolaires, voies et adresses, élus, résultats d'élections,
valeurs foncières, bornes de recharge électrique — 14 JDD au total, les
délibérations étant un cas particulier de `_commun.py`), `organisations.py` (table
curée des producteurs réels), `agregation_scrutin.py`, `registre.py`, `cli.py`
(assistant interactif + mode scriptable).
