# Backlog v3

Suivi d'avancement de la v3 (demande du 2026-11-09). Statuts possibles : fait /
en cours / bloqué — attend Simon / pas commencé. Chaque ligne porte sa propre date de
dernière mise à jour (pas seulement le Journal global).

## Prochaines étapes
1. ~~Axe 1 (descriptions communes)~~ — fait, voir ci-dessous.
2. ~~`licences.py` + table complète (Axe 4, étape 1)~~ — fait.
3. ~~Câblage elus/elections (Axe 4, étape 2)~~ — fait.
4. ~~Remplacement DECP (Axe 4, étape 3)~~ — fait.
5. ~~Câblage licence des 10 modules non-data.gouv (Axe 4, étape 4)~~ — fait.
6. ~~Axe 6 (bbox, tous les modules)~~ — fait.
7. ~~Axe 2 (contacts)~~ — fait.
8. ~~Axe 3 (descriptions riches + mots-clés enrichis)~~ — fait. V3 complète, reste la
   vérification finale (tests + commits, voir Journal).

## 1. Descriptions des communes
Statut global : **fait**. Dernière màj : 2026-11-10.

`rudi_harvest_toolkit.wikipedia.resumer_commune_wikipedia()` (désambiguïsation Wikidata
par code INSEE, extrait MediaWiki complet, cache partagé) +
`description_commune.construire_description_commune()` (attribution CC BY-SA intégrée au
texte, repli explicite) câblés dans `organisations.py`/`cli.py`/les 13 modules. Résolu une
seule fois par run, avertissement CLI si repli générique utilisé.

**Correction post-livraison (test réel Acigné, 2026-11-10)** : `longueur_min` (garde-fou
contre les ébauches) abaissé de 250 à 80 caractères — le résumé réel d'Acigné (192
caractères) était à tort traité comme une ébauche. Second paragraphe ajouté
(`description_commune._paragraphe_complementaire()`) : maire actuel (RNE,
`rudi_harvest_toolkit.rne.maire_actuel()` — pas Wikidata P6, qui reste affiché
indéfiniment sans signal d'obsolescence après une élection non répercutée), gentilé et
superficie (Wikidata P1549/P2046, `resumer_commune_wikipedia()`) — chacun omis si
absent, paragraphe entier omis si aucun des trois n'est disponible.

## 2. Contacts producteurs
Statut global : **fait**. Dernière màj : 2026-11-10.

| Organisation | Email confirmé | Statut | Dernière màj |
|---|---|---|---|
| INSEE | support-apim@insee.fr | fait (table curée) | 2026-11-10 |
| BAN (DINUM) | adresse@data.gouv.fr | fait (table curée) | 2026-11-10 |
| DGFiP | dtnum.donnees.gouvernance@dgfip.finances.gouv.fr | fait (table curée, confiance moyenne) | 2026-11-10 |
| Ministère Intérieur | elections@interieur.gouv.fr | fait (table curée, repli dynamique prioritaire câblé) | 2026-11-10 |
| IRVE (transport.data.gouv.fr) | contact@transport.beta.gouv.fr | fait (table curée, confiance moyenne) | 2026-11-10 |
| DECP (Colin Maudry, via contact_points) | colin@colmo.tech | fait (contact dynamique, priorité 1 confirmée réelle) | 2026-11-10 |
| Délibérations | `contact_email_commune` (mécanisme existant, pas une entrée curée) | connu par construction | 2026-11-10 |
| Mégalis Bretagne | — | repli générique — introuvable, `contact_statut: a_confirmer` | 2026-11-10 |
| Hub'eau / BRGM | — | repli générique — introuvable, `contact_statut: a_confirmer` | 2026-11-10 |
| Éducation nationale | — | repli générique — introuvable, `contact_statut: a_confirmer` | 2026-11-10 |

`CONTACTS_ORGANISATIONS` + `contact_curated_pour_jdd()` (`organisations.py`) + chaîne de
priorité dans `contacts_pour_producer()` (`_commun.py`) : contact dynamique data.gouv
(`extraire_contacts_datagouv()`, migré dans `rudi_harvest_toolkit.contacts`) > contact curé
confirmé > repli générique. `rudi_harvest_toolkit.contacts` migré depuis
`moissonneuse-batteuse`, qui en garde un shim de réexportation (zéro changement pour ses
6 appelants).

## 3. Descriptions riches des JDD (+ mots-clés enrichis, même commit)
Statut global : **fait**. Dernière màj : 2026-11-10.

`construire_description_structuree()` (nouveau, `rudi_harvest_toolkit.description` —
assembleur de mise en page pur, zéro connaissance du domaine) câblé via une fonction
`_description_enrichie()` par module, contenu quoi/comment construit/variables rédigé à
la main pour chacun des 13 JDD. Vérifié forme ET contenu par module (`<ul>` + lien final
dans le HTML rendu, et au moins un mot-clé métier propre au module).

| Module | Helper câblé | Contenu rédigé | Mots-clés enrichis | Statut | Dernière màj |
|---|---|---|---|---|---|
| population | oui | oui | oui | fait | 2026-11-10 |
| entreprises | oui | oui | oui | fait | 2026-11-10 |
| associations | oui | oui | oui | fait | 2026-11-10 |
| budget | oui | oui | oui | fait | 2026-11-10 |
| immobilier_dvf | oui | oui | oui | fait | 2026-11-10 |
| deliberations | oui | oui | oui | fait | 2026-11-10 |
| eau_potable | oui | oui | oui | fait | 2026-11-10 |
| etablissements_scolaires | oui | oui | oui | fait | 2026-11-10 |
| adresses | oui | oui | oui | fait | 2026-11-10 |
| irve | oui | oui | oui | fait | 2026-11-10 |
| elus | oui | oui | oui | fait | 2026-11-10 |
| elections | oui | oui | oui | fait | 2026-11-10 |
| marches_publics | oui | oui | oui | fait | 2026-11-10 |

## 4. Licence / dates / mots-clés / source
Statut global : **fait** (licence + source + mots-clés, ces derniers via l'Axe 3
ci-dessus ; dates des 10 modules non-data.gouv reportées en v4, décision Simon).
Dernière màj : 2026-11-10.

| Module | Licence | Dates | Source | Statut | Dernière màj |
|---|---|---|---|---|---|
| elus | dynamique (data.gouv), repli curé en place | dynamique (last_modified) | inchangée | fait | 2026-11-10 |
| elections | dynamique (data.gouv), repli curé en place | dynamique (last_modified) | inchangée | fait | 2026-11-10 |
| marches_publics | dynamique (data.gouv, lov2 → etalab-2.0, Colin Maudry) | dynamique (last_modified) | **changée → Colin Maudry (data.gouv)** | fait | 2026-11-10 |
| entreprises | curée, CUSTOM (SIRENE + RNE) | non disponible (voir point ouvert) | inchangée | fait | 2026-11-10 |
| associations | curée, CUSTOM (SIRENE + RNE) | non disponible (voir point ouvert) | inchangée | fait | 2026-11-10 |
| budget | curée (etalab-2.0) | non disponible (voir point ouvert) | inchangée | fait | 2026-11-10 |
| deliberations | curée (etalab-2.0) | non disponible (voir point ouvert) | inchangée | fait | 2026-11-10 |
| population | curée (etalab-2.0) | non disponible (voir point ouvert) | inchangée | fait | 2026-11-10 |
| eau_potable | curée (etalab-2.0) | non disponible (voir point ouvert) | inchangée | fait | 2026-11-10 |
| etablissements_scolaires | curée (etalab-2.0) | non disponible (voir point ouvert) | inchangée | fait | 2026-11-10 |
| adresses | curée (etalab-2.0) | non disponible (voir point ouvert) | inchangée | fait | 2026-11-10 |
| immobilier_dvf | curée (etalab-2.0) | non disponible (voir point ouvert) | inchangée | fait | 2026-11-10 |
| irve | curée (etalab-2.0) | non disponible (voir point ouvert) | inchangée | fait | 2026-11-10 |

Chaque module résout sa licence via `licences.licence_pour_jdd(CLE)` (jamais de repli
silencieux Etalab) — complétude vérifiée par
`test_licences.py::test_toutes_les_cles_de_modules_ont_une_licence_curee`. Les 3 modules
data.gouv (`elus`, `elections`, `marches_publics`) ont en plus la licence/date dynamique
résolue depuis la fiche source, avec repli curé si absente.

**Point tranché (2026-11-10, décision Simon)** : dates des 10 modules non-data.gouv
reportées en v4 (voir Backlog v4 ci-dessous) — la v3 reste close sans ce chantier.

## 5. Géolocalisation (vue carte) — Axe 6, tous les modules sans exception
Statut global : **fait**. Dernière màj : 2026-11-10.

| Module | Statut | Dernière màj |
|---|---|---|
| entreprises | fait | 2026-11-10 |
| associations | fait | 2026-11-10 |
| budget | fait | 2026-11-10 |
| marches_publics | fait | 2026-11-10 |
| deliberations | fait | 2026-11-10 |
| population | fait | 2026-11-10 |
| eau_potable | fait | 2026-11-10 |
| etablissements_scolaires | fait | 2026-11-10 |
| adresses | fait | 2026-11-10 |
| elus | fait | 2026-11-10 |
| elections | fait | 2026-11-10 |
| immobilier_dvf | fait | 2026-11-10 |
| irve | fait | 2026-11-10 |

`bbox_depuis_contour()` (toolkit, `rudi_harvest_toolkit.commune`) + `geography_pour_commune()`
(starterkit, `datasets/_commun.py`) câblés dans les 13 modules via
`construire_rudi_metadata(geography=...)`. `None` (clé omise) si le contour de la commune
est absent — jamais de bbox devinée. Vérifié par un test de contrat statique
(`test_registre.py`) et une preuve bout-en-bout (`test_population.py`).

## Backlog v4 — en cours d'implémentation (plan détaillé, relu en 5 passes)
- ~~Migration d'urgence de la source DVF (Axe 0)~~ — **fait**, voir « Décisions actées
  v4 » et Journal ci-dessous. Release 0.3.1.
- ~~Fusion des JDD élections (toutes années/types/tours en un seul JDD structuré)~~ —
  **fait** (Axe 5, incréments A+B+C complets : fusion + Parquet, jointure élu/sièges
  2026 T1, glossaire nuance + marqueur `sieges_disponibles`). Release 0.5.0. Voir
  Journal.
- ~~Historique budget plus profond + documentation des variables complexes (DGFiP)~~ —
  **fait** (Axe 4) : union de 12 datasets DGFiP (2000-2025, sans trou), glossaire
  budget + 3 autres modules (DVF, DECP, eau potable). Release 0.6.0. Voir Journal.
- ~~Publication GeoJSON par ligne (au-delà de la bbox dataset simple de l'axe 6)~~ —
  **fait** (Axe 3) : `rudi_harvest_toolkit.geojson` + `valider_alignement_medias()`
  (garde-fou d'ordre) construits et testés ; `adresses.py`,
  `etablissements_scolaires.py` (export GeoJSON natif de l'ODS, correct pour ce
  dataset), `entreprises.py`/`associations.py` (latitude/longitude déjà fournis par
  établissement), `irve.py` (parsing local obligatoire — export natif confirmé
  inversé) câblés. `eau_potable.py` confirmé et documenté sans géométrie disponible
  (pas une régression). Voir Journal.
- ~~Dates réelles pour les 10 modules non-data.gouv~~ — **fait** (Axe 2) : `adresses.py`/
  `immobilier_dvf.py` (mtime du cache), `irve.py` (MAX last_modified ODS trié),
  `etablissements_scolaires.py`/`budget.py` (metas.default.modified ODS),
  `entreprises.py`/`associations.py` (date_mise_a_jour*, MAX sur les résultats),
  `deliberations.py` (MAX date_acte/date_publication), `population.py` (fiche catalogue
  Melodi). `eau_potable.py` reste sans date réelle (aucune disponible côté source,
  documenté ci-dessous). Voir Journal.
- Contacts restant introuvables : Mégalis Bretagne, Hub'eau/BRGM, Éducation nationale
- ~~Faire pointer `moissonneuse-batteuse/datagouv_to_rudi.py` vers
  `LICENCES_DATAGOUV_CONNUES` du toolkit au lieu de sa copie locale~~ — **fait** (Axe 1),
  voir Journal.

## Décisions actées v4

- **2026-11-11 (Axe 5, incrément A)** : périmètre régionales/départementales/
  cantonales inclus dans la fusion (confirmé par comptage exhaustif du jeu source :
  56 scrutins, 7 types, 1999-2026) malgré leur caractère local plutôt que national au
  sens strict — cohérence avec l'esprit de la décision initiale (« toutes élections
  nationales si le jeu les couvre ») et valeur réelle d'un historique électoral local
  pour un catalogue communal. Choix Parquet confirmé (232 Mo par commune et par run,
  ~12x moins que les CSV sources mais ~16x plus que l'ancien JDD mono-scrutin — un
  coût assumé en échange de 56 scrutins, pas un gain net). Noms `ratio_*` natifs du
  jeu agrégé retenus pour les colonnes de pourcentage (plutôt que
  `pourcentage_exprimes` de l'ancien CSV, incompatibles en sens).
- **2026-11-10 (Axe 0, urgence DVF)** : la ressource départementale consommée par
  `immobilier_dvf.py` (`files.data.gouv.fr/geo-dvf/latest/csv/{année}/departements/
  {dep}.csv.gz`) était explicitement annoncée pour suppression (« suppression au
  31/11/2026 »). Vérifié en direct : aucun accès par département ne subsiste dans le
  dataset officiel (`demandes-de-valeurs-foncieres-geolocalisees`) — seules des
  ressources nationales existent. Choix fait entre 2 options nationales : la ressource
  unique « DVF juillet 2021 - juin 2026 - fichier unique » (`dvf.csv.gz`, 609 Mo) plutôt
  que les 6 fichiers annuels (`full-YYYY.csv.gz`, union de schéma) — un seul
  téléchargement/une seule entrée de cache, schéma confirmé identique à l'ancienne
  source. URL résolue dynamiquement (`datagouv.get_dataset_metadata()` +
  `selectionner_ressource()`), jamais codée en dur (le nom physique du fichier change à
  chaque republication côté data.gouv.fr).

## Limites de couverture connues

| Cause | Module | Visibilité catalogue | Suivi v5 éventuel |
|---|---|---|---|
| Fichier DVF national unique couvre juillet 2021 à juin 2026 — les mutations antérieures ne sont plus accessibles via cette source (l'ancienne source départementale ne remontait déjà que ~5-6 ans en arrière, pas de régression de fenêtre) | `immobilier_dvf.py` | Description riche (« années disponibles ») | — |
| Aucune date de mise à jour de jeu exploitable côté source : `resultats_dis` (Hub'eau) n'expose qu'une `date_prelevement` par ligne de résultat, pas une date de mise à jour du jeu — `dataset_dates.updated` reste absent (pas une régression, cette source n'a jamais eu de date réelle) | `eau_potable.py` | Aucune (pas de mécanisme à ajouter tant que `limites` — Axe 4 — n'existe pas) | Revisiter si Hub'eau expose un jour une date de mise à jour de jeu |
| Aucune coordonnée géographique disponible (`resultats_dis` : 32 champs, aucun n'est une géométrie ; `reseaux` n'est qu'une liste d'identifiants) — pas de GeoJSON possible | `eau_potable.py` | Aucune (idem, en attendant `limites`) | Revisiter si Hub'eau expose un jour une géométrie par point de prélèvement |
| `entreprises.py`/`associations.py` : une entreprise/association sans établissement correspondant publié (`matching_etablissements` vide) produit 0 point sur la carte même si son siège est géolocalisé — conséquence de ce que publie `simplifier_resultat_entreprise()`, pas un bug | `entreprises.py`, `associations.py` | Aucune (idem) | — |
| `adresses.py`/`immobilier_dvf.py` : date affichée = date de récupération locale (mtime du cache, TTL 30 j), pas la date de mise à jour réelle de la source — écart possible jusqu'à 30 jours | `adresses.py`, `immobilier_dvf.py` | `dataset_dates.updated` (date de cache, pas de source) | — |
| Municipales 2008 partielles (communes >3500 hab. seulement) ; pas de second tour pour les européennes (1 seul tour pour ce type d'élection) | `elections.py` | Description riche (`limites`) | — |
| Colonnes `elu`/`sieges_conseil_municipal`/`sieges_conseil_communautaire` : disponibles seulement pour les municipales 2026 (`2026_muni_t1`) des communes pourvues dès le premier tour — `2026_muni_t2` et tous les autres scrutins n'ont pas de sièges exploitables dans la source actuelle | `elections.py` | Description riche (`limites`) | Intégrer une source des résultats définitifs T2 (hors périmètre v4) |

## Point tranché (2026-11-10, décision Simon)
- Test d'intégration `executer_run()` sur les 13 modules — **pas maintenant**. Les
  tests statiques de complétude/contrat de signature couvrent l'essentiel du risque
  pour un coût bien moindre ; à reconsidérer si un bug d'enchaînement apparaît en réel.

## Journal
- 2026-11-09 : plan v3 conçu, recherche web faite (licences, contacts, source DECP).
- 2026-11-10 : plan relu en 3 passes opencode (architecture, testabilité, produit) et
  corrigé en conséquence.
- 2026-11-10 : Axe 1 implémenté et testé (`rudi_harvest_toolkit.wikipedia` +
  `description_commune.py` + câblage `organisations.py`/`cli.py`/13 modules) —
  `bbox_depuis_contour()` (Axe 6) ajouté en même temps au toolkit (même fichier,
  `commune.py`), câblage dans les modules restant à faire (voir § 5 ci-dessus).
- 2026-11-10 : Axe 4 (licence/dates/source) implémenté et testé pour les 13 modules —
  `licences.py` (table complète + point d'entrée unique), `elus`/`elections` câblés sur
  la licence/date dynamique data.gouv avec repli curé, `LICENCES_DATAGOUV_CONNUES`
  ajoutée au toolkit, 10 modules non-data.gouv câblés sur la table curée, remplacement de
  la source DECP de `marches_publics.py` (Colin Maudry, data.gouv.fr, filtrage local en
  flux avec le nouveau paramètre `prefixe=True` de `filtrer_csv()`/`lire_csv_filtre()`).
  Reste : mots-clés enrichis (lié à l'Axe 3), point ouvert dates des 10 modules
  non-data.gouv (bloqué — attend Simon).
- 2026-11-10 : Axe 6 (bbox) câblé et testé sur les 13 modules (`geography_pour_commune()`
  dans `_commun.py`, test de contrat statique + preuve bout-en-bout sur `population.py`).
- 2026-11-10 : Axe 2 (contacts) implémenté et testé — `rudi_harvest_toolkit.contacts`
  migré depuis `moissonneuse-batteuse` (shim de réexportation côté origine, zéro
  changement pour ses 6 appelants), `CONTACTS_ORGANISATIONS` + chaîne de priorité
  (dynamique data.gouv > curé confirmé > repli générique) câblée dans
  `contacts_pour_producer()`.
- 2026-11-10 : Axe 3 (descriptions riches + mots-clés enrichis) implémenté et testé —
  `construire_description_structuree()` ajouté au toolkit, câblé par module (13 commits)
  avec contenu quoi/comment construit/variables rédigé à la main pour chaque JDD,
  mots-clés enrichis dans le même commit. V3 fonctionnellement complète, vérification
  finale faite (suites complètes des deux dépôts vertes, commits locaux).
- 2026-11-10 : premier test réel (commune d'Acigné) par Simon — 2 défauts trouvés et
  corrigés le même jour (vue tableau cassée sur 8 modules, régression infra déjà
  connue ; description de commune non enrichie, garde-fou anti-ébauches trop strict,
  voir § 1 ci-dessus). Les 2 points ouverts du backlog tranchés par Simon : dates des
  10 modules non-data.gouv reportées en v4, test d'intégration `executer_run()` pas
  fait maintenant. **V3 close.**
- 2026-11-10 : plan v4 écrit (5 axes), relu en 5 passes (3 opencode + vérification
  ciblée id_brut_miom/jointure élections + 1 passe de cohérence Claude Code + 1 passe
  indépendante par un agent Claude dédié) — toutes les corrections intégrées au plan.
  Implémentation démarrée, sous-traitée à `opencode run` axe par axe avec reprise
  directe par Claude Code dès épuisement du quota gratuit.
- 2026-11-10 : Axe 0 (urgence DVF) implémenté et testé (quota opencode épuisé, fait
  directement) — `immobilier_dvf.py` migré vers la ressource nationale unique
  `dvf.csv.gz`, résolution dynamique via `datagouv.get_dataset_metadata()`/
  `selectionner_ressource()`, dates dérivées de `date_mutation` (plus de sondage par
  année ni d'union de schéma). Suite complète des deux dépôts verte (357 + 321 tests).
  Livré en release **0.3.1**, poussé sur `main` + tag.
- 2026-11-10 : Axe 1 (dédoublonnage licences) implémenté et testé dans
  `moissonneuse-batteuse` (quota opencode épuisé, fait directement) — `LICENCES`
  importe désormais `LICENCES_DATAGOUV_CONNUES` du toolkit au lieu de sa copie locale ;
  test `odc-odbl` manquant ajouté. 233 tests verts, poussé sur `main`.
- 2026-11-10 : Axe 3 (GeoJSON), première tranche implémentée et testée (quota opencode
  épuisé, fait directement) — nouveau `rudi_harvest_toolkit.geojson`
  (`construire_feature_collection()`, `AucuneGeometrieValide`) et
  `rudi_client.valider_alignement_medias()` (garde-fou d'ordre, pas seulement de
  compte — trou trouvé en passe 5 de relecture du plan) ; `adresses.py` câblé (second
  média GeoJSON).
- 2026-11-10 : Axe 2 (dates réelles) implémenté et testé en totalité (quota opencode
  épuisé, fait directement) — nouveau `rudi_harvest_toolkit.http_dates`
  (`entete_derniere_modification()`, `date_dataset_ods()`, `parser_date_iso_stricte()`,
  jamais `pivot.parser_date_http()` qui invente une date sur échec) et
  `download_cache.date_fichier_cache()`. Câblage par module : `adresses.py`/
  `immobilier_dvf.py` (mtime du cache), `irve.py` (MAX last_modified ODS trié, piège
  ISO vs format HTTP corrigé en cours de route), `etablissements_scolaires.py`/
  `budget.py` (metas.default.modified, vérifié en direct), `entreprises.py`/
  `associations.py` (nouveau `date_plus_recente_entreprises()` partagé dans
  `_commun.py`, MAX sur date_mise_a_jour/_insee/_rne), `deliberations.py` (MAX
  date_acte/date_publication, aucune requête supplémentaire), `population.py`
  (nouvelle fiche catalogue Melodi `GET /melodi/catalog/{id}`, best-effort).
  `eau_potable.py` confirmé et documenté sans date réelle disponible (BACKLOG §
  Limites de couverture connues) — pas une régression. Suite complète verte à chaque
  étape, poussé sur `main` par petits commits.
- 2026-11-10 : Axe 3 (GeoJSON) complété en totalité (quota opencode épuisé, fait
  directement) — `etablissements_scolaires.py` (export GeoJSON natif de l'ODS,
  correct pour ce dataset, pas de parsing local nécessaire), `entreprises.py`/
  `associations.py` (`latitude`/`longitude` ajoutés à `_CHAMPS_ETABLISSEMENT`,
  partagé dans `_commun.py` — pas de géocodage BAN nécessaire, les champs sont déjà
  fournis par l'API), `irve.py` (parsing local depuis `consolidated_longitude`/
  `consolidated_latitude`, export natif confirmé inversé — second téléchargement du
  même CSV déjà utilisé par le média hybride, ordre des médias imposé par
  `valider_alignement_medias()`). `eau_potable.py` confirmé et documenté sans
  géométrie disponible. Suite complète verte à chaque étape, poussé sur `main`.
  **Axes 1, 2 et 3 désormais tous complets — release 0.4.0.**
- 2026-11-11 : Axe 5 incrément A (fusion élections + Parquet, sans jointure
  élu/sièges) implémenté et testé (quota opencode épuisé, fait directement) —
  vérifié en direct sur le jeu réel (`general_results.parquet`/
  `candidats_results.parquet` téléchargés intégralement une fois pour confirmer
  schéma/56 scrutins/7 types/ex. Gévezé 2026 municipales T1 cohérent avec l'ancien
  JDD mono-scrutin). Nouveau `agregation_scrutin.agreger_long_vers_commune()`
  (+ `recalculer_ratios()`, `TYPES_ELECTION`, `TypeElectionInconnu`,
  `decomposer_id_election()`), nouveau `rudi_harvest_toolkit.tabular.
  lire_parquet_filtre()` (+ dépendance `pyarrow>=14` obligatoire), nouveaux
  paramètres `glossaire`/`limites` sur `construire_description_structuree()`
  (None par défaut, non-régression testée — infrastructure partagée avec l'Axe 4).
  `datasets/elections.py` entièrement réécrit : résolution des 2 ressources Parquet
  (motif + `format="parquet"` pour lever l'ambiguïté CSV/Parquet, même titre),
  jointure canton/circonscription au niveau bureau avant agrégation commune, surface
  publiée mise à jour (titre/synopsis/fréquence/nom de fichier/légende/mots-clés —
  plus aucune mention de « municipales » seule). Fixtures de test : fichiers Parquet
  réels écrits sur disque via `pyarrow.parquet.write_table()` (pas de mock de
  `pyarrow`). Suite complète verte (407 tests), poussé sur `main`.
- 2026-11-11 : Axe 5 incrément B (jointure élu/sièges, municipales 2026 T1) implémenté
  et testé (délégation opencode tentée mais bloquée — process resté bloqué ~2h sur une
  invite de permission sans TTY, faute du flag `--auto` ; relance avec `--auto`
  refusée par le classifieur auto mode de Claude Code, « Create Unsafe Agents » —
  fait directement). Nouveau `agregation_scrutin.joindre_elu_sieges()` (jointure
  `(code_insee, no_panneau)`, n'enrichit que `2026_muni_t1`, jamais d'exception sur
  clé absente, ne mute jamais son entrée) ; nouveau `_index_elu_sieges()` dans
  `elections.py` (dépivot des 13 blocs de la source municipales 2026 actuelle, `elu`
  dérivé de `sieges_conseil_municipal > 0` — la colonne `Elu N` de la source est vide
  partout). Enrichissement optionnel : un échec de cette source secondaire dégrade
  proprement (avertissement, colonnes vides) sans jamais faire échouer le run (déjà
  toute sa valeur sans cette jointure, incrément A). 5 nouvelles colonnes CSV (`elu`,
  `sieges_conseil_municipal`, `sieges_conseil_communautaire`, `libelle_liste`,
  `libelle_abrege`). Suite complète verte (417 tests), poussé sur `main`.
- 2026-11-11 : Axe 5 incrément C (glossaire nuance + `sieges_disponibles`) implémenté
  et testé (fait directement, après l'épisode opencode bloqué de l'incrément B) —
  glossaire sourcé depuis la ressource officielle `nuances.csv` du jeu agrégé (2
  versions coexistent, circulaires différentes : résolution manuelle titre+format+max
  `last_modified`, `selectionner_ressource()` ne combine pas motif et plus-récent),
  restreint à l'affichage aux codes nuance effectivement présents dans le CSV publié
  pour la commune (le fichier source reste complet et fait autorité, seul l'affichage
  est filtré — pas une curation manuelle partielle). Nouvelle colonne booléenne
  `sieges_disponibles` (vrai seulement pour les lignes `2026_muni_t1` jointes avec
  succès) rendant explicite, ligne par ligne, la limite déjà documentée en texte.
  Enrichissement optionnel (glossaire), comme la jointure de l'incrément B : un échec
  dégrade proprement sans faire échouer le run. Suite complète verte (421 tests).
  **Axe 5 désormais complet (incréments A+B+C) — release 0.5.0.**

## Axe 4 — fait (2026-11-11)

**Sous-chantier A — historique budget complet.** Catalogue réel des 12 datasets ODS
« comptes individuels des communes » vérifié en direct
(`data.economie.gouv.fr/api/explore/v2.1/catalog/datasets/{id}`), **en deux temps** —
la première passe de recherche (notée plus tôt dans ce document, maintenant corrigée)
avait conclu à tort à une couverture 2008-2025 en ne vérifiant que l'*existence* des
12 datasets sans lire leur *contenu* réel. **Correction, trouvée en creusant sur
demande explicite de Simon** : interroger chaque dataset (`/records?where=dep='035'
AND icom='120'`) montre que le dataset nommé `...-2008` contient en réalité les
exercices **2000 à 2008** (9 lignes, champ `an` = 2000..2008), et le dataset nommé
`...-20090` (⚠️ typo source : `20090`, pas `2009`) l'exercice 2009 seul — **couverture
réelle 2000-2025, sans trou ni recoupement entre les 12 datasets**, conforme à
l'ambition initiale du plan (que la première passe avait crue impossible à tenir).
Leçon retenue : ne jamais conclure sur la couverture d'un dataset à partir de son nom
seul, toujours interroger son contenu (champ `an`).

Les 12 `dataset_id` réels (dans l'ordre utilisé par `budget.py::_DATASET_IDS`) :
`...-2008` (an 2000-2008), `...-20090` (an 2009), `...-2010`, `...-2011-2015`,
`...-2016`, `...-2017`, `...-2018`, `...-2019-2020`, `...-2021`, `...-2022`,
`...-2023-2024`, `...-2025`. Les 12 exposent tous `dep`/`icom`/`an` (vérifié champ par
champ) — la politique de dégradation prévue par le plan (« si un dataset ancien
n'expose pas dep/icom ») n'a donc jamais été nécessaire.

`budget.py` n'est plus un FILE hybride passthrough (impossible à maintenir avec 12
sources à unir) : il interroge les 12 datasets (pagination complète, jamais tronquée
silencieusement), harmonise les colonnes par nom (union, pas position — schémas
DGFiP de 173 à 254 colonnes selon l'exercice), écrit un CSV local unique (une ligne
par exercice réellement trouvé pour la commune, `an` en tête). Dégradation par
dataset (pas globale) si une requête échoue : avertissement + note dans `limites`,
échec du run seulement si les 12 échouent. `date_source` = max des `metas.default.
modified` des seuls datasets ayant contribué une ligne.

Glossaire (nouveau paramètre `glossaire=` de `construire_description_structuree()`,
disponible depuis l'Axe 5 incrément A) sourcé depuis la fiche de métadonnées DGFiP
officielle (`Maquette_commune.ods`, publiée par chaque dataset, téléchargée et
convertie en direct via `soffice --headless --convert-to csv` — jamais recopié de
mémoire) : ~43 codes structurants + une note sur la convention de préfixes
f/m/r/rm, restreint à l'affichage aux colonnes effectivement publiées pour la
commune (comme le glossaire nuance de l'Axe 5).

**Sous-chantier B — glossaire des 3 autres modules à nomenclature opaque.** Vérifié en
direct avant d'écrire quoi que ce soit (mécanisme DVF à réutiliser, mentionné par le
plan, n'existe en réalité plus : l'Axe 0 l'a supprimé en passant à un fichier
national unique sans union de schéma) :
- `immobilier_dvf.py` : la quasi-totalité des codes DVF ont déjà leur libellé en clair
  dans une colonne adjacente (`code_type_local`/`type_local`,
  `code_nature_culture`/`nature_culture`) — vérifié sur un échantillon réel du fichier
  source (en-tête + lignes, récupéré par une requête `Range` HTTP partielle, sans
  télécharger les 609 Mo complets). Glossaire limité aux 2 identifiants réellement
  non triviaux : `id_mutation`, `id_parcelle`.
- `marches_publics.py` : le `schema.json` publié par le dataset Colin Maudry porte
  déjà des labels clairs pour presque toutes les colonnes. Seul `codeCPV`
  (nomenclature européenne) est réellement opaque — glossé.
- `eau_potable.py` : **la prémisse du plan était fausse, pas seulement incomplète** —
  vérifié sur un échantillon réel (Gévezé) que chaque `code_parametre` SISE-Eaux est
  déjà accompagné de son `libelle_parametre` en clair dans la même ligne, donc rien à
  glosser là. Les véritables codes mono-lettre non expliqués
  (`code_type_parametre` N/O, `code_lieu_analyse` L/T, `conformite_*_prelevement`
  C/S) n'ont, à cette date, aucune légende publique trouvée (ni dans l'API, ni dans
  la doc Hub'eau) — **aucun glossaire ajouté plutôt que d'inventer leur sens** ;
  documentés comme limite à la place.

Suite complète verte (433 tests, +12 vs avant l'Axe 4). Release 0.6.0.
