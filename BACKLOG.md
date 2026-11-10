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
- Fusion des JDD élections (toutes années/types/tours en un seul JDD structuré) — pas
  commencé (Axe 5, 3 incréments A/B/C).
- Historique budget plus profond + documentation des variables complexes (DGFiP) — pas
  commencé (Axe 4).
- Publication GeoJSON par ligne (au-delà de la bbox dataset simple de l'axe 6) — pas
  commencé (Axe 3).
- **Dates réelles pour les 10 modules non-data.gouv** — pas commencé (Axe 2).
- Contacts restant introuvables : Mégalis Bretagne, Hub'eau/BRGM, Éducation nationale
- Faire pointer `moissonneuse-batteuse/datagouv_to_rudi.py` vers
  `LICENCES_DATAGOUV_CONNUES` du toolkit au lieu de sa copie locale (Axe 1 — gain
  rapide, pas commencé)

## Décisions actées v4

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
  À livrer en release **0.3.1** indépendamment du reste de la v4.
