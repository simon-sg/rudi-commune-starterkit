# Backlog v3

Suivi d'avancement de la v3 (demande du 2026-11-09). Statuts possibles : fait /
en cours / bloqué — attend Simon / pas commencé. Chaque ligne porte sa propre date de
dernière mise à jour (pas seulement le Journal global).

## Prochaines étapes
1. ~~Axe 1 (descriptions communes)~~ — fait, voir ci-dessous.
2. `licences.py` + table complète (Axe 4, étape 1).
3. Câblage elus/elections (Axe 4, étape 2).
4. Remplacement DECP (Axe 4, étape 3).
5. Axe 2 (contacts), Axe 3 (descriptions riches + mots-clés), reste de l'Axe 4, Axe 6.

## 1. Descriptions des communes
Statut global : **fait**. Dernière màj : 2026-11-10.

`rudi_harvest_toolkit.wikipedia.resumer_commune_wikipedia()` (désambiguïsation Wikidata
par code INSEE, extrait MediaWiki complet, cache partagé) +
`description_commune.construire_description_commune()` (attribution CC BY-SA intégrée au
texte, repli explicite) câblés dans `organisations.py`/`cli.py`/les 13 modules. Résolu une
seule fois par run, avertissement CLI si repli générique utilisé.

## 2. Contacts producteurs
| Organisation | Email confirmé | Statut | Dernière màj |
|---|---|---|---|
| INSEE | support-apim@insee.fr | pas commencé (connu, pas encore câblé) | 2026-11-10 |
| BAN (DINUM) | adresse@data.gouv.fr | pas commencé | 2026-11-10 |
| DGFiP | dtnum.donnees.gouvernance@dgfip.finances.gouv.fr | pas commencé (confiance moyenne) | 2026-11-10 |
| Ministère Intérieur | elections@interieur.gouv.fr | pas commencé | 2026-11-10 |
| IRVE (transport.data.gouv.fr) | contact@transport.beta.gouv.fr | pas commencé (confiance moyenne) | 2026-11-10 |
| DECP (Colin Maudry, via contact_points) | colin@colmo.tech | pas commencé (dépend du remplacement de source) | 2026-11-10 |
| Délibérations | `contact_email_commune` (mécanisme existant, pas une entrée curée) | connu par construction | 2026-11-10 |
| Mégalis Bretagne | — | repli générique — introuvable, `contact_statut: a_confirmer` | 2026-11-10 |
| Hub'eau / BRGM | — | repli générique — introuvable, `contact_statut: a_confirmer` | 2026-11-10 |
| Éducation nationale | — | repli générique — introuvable, `contact_statut: a_confirmer` | 2026-11-10 |

## 3. Descriptions riches des JDD (+ mots-clés enrichis, même commit)
| Module | Helper câblé | Contenu rédigé | Mots-clés enrichis | Statut | Dernière màj |
|---|---|---|---|---|---|
| entreprises | | | | pas commencé | 2026-11-10 |
| associations | | | | pas commencé | 2026-11-10 |
| budget | | | | pas commencé | 2026-11-10 |
| marches_publics | | | | pas commencé | 2026-11-10 |
| deliberations | | | | pas commencé | 2026-11-10 |
| population | | | | pas commencé | 2026-11-10 |
| eau_potable | | | | pas commencé | 2026-11-10 |
| etablissements_scolaires | | | | pas commencé | 2026-11-10 |
| adresses | | | | pas commencé | 2026-11-10 |
| elus | | | | pas commencé | 2026-11-10 |
| elections | | | | pas commencé | 2026-11-10 |
| immobilier_dvf | | | | pas commencé | 2026-11-10 |
| irve | | | | pas commencé | 2026-11-10 |

## 4. Licence / dates / mots-clés / source
| Module | Licence | Dates | Source | Statut | Dernière màj |
|---|---|---|---|---|---|
| elus | dynamique (data.gouv), repli curé disponible | à câbler | inchangée | pas commencé | 2026-11-10 |
| elections | dynamique (data.gouv), repli curé disponible | à câbler | inchangée | pas commencé | 2026-11-10 |
| marches_publics | confirmée (lov2 → etalab-2.0, Colin Maudry) | dynamique (last_modified) | **à changer → Colin Maudry (data.gouv)** | pas commencé | 2026-11-10 |
| entreprises | CUSTOM (SIRENE + RNE) | non disponible (voir point ouvert) | inchangée | pas commencé | 2026-11-10 |
| associations | CUSTOM (SIRENE + RNE) | non disponible (voir point ouvert) | inchangée | pas commencé | 2026-11-10 |
| budget | curée (etalab-2.0) | non disponible (voir point ouvert) | inchangée | pas commencé | 2026-11-10 |
| deliberations | curée (etalab-2.0) | non disponible (voir point ouvert) | inchangée | pas commencé | 2026-11-10 |
| population | curée (etalab-2.0) | non disponible (voir point ouvert) | inchangée | pas commencé | 2026-11-10 |
| eau_potable | curée (etalab-2.0) | non disponible (voir point ouvert) | inchangée | pas commencé | 2026-11-10 |
| etablissements_scolaires | curée (etalab-2.0) | non disponible (voir point ouvert) | inchangée | pas commencé | 2026-11-10 |
| adresses | curée (etalab-2.0) | non disponible (voir point ouvert) | inchangée | pas commencé | 2026-11-10 |
| immobilier_dvf | curée (etalab-2.0) | non disponible (voir point ouvert) | inchangée | pas commencé | 2026-11-10 |
| irve | curée (etalab-2.0) | non disponible (voir point ouvert) | inchangée | pas commencé | 2026-11-10 |

**Point ouvert — dates des 10 modules non-data.gouv** : aucune date réelle disponible
(limite technique documentée, Axe 4 : `download_cache.telecharger()` ne remonte pas les
en-têtes HTTP). Rechercher une date de publication par source officielle serait un
nouveau chantier de recherche comparable à celui des licences/contacts. **Décision à
prendre avec Simon** : faire ce chantier dans cette v3, ou le reporter en v4.
Statut : bloqué — attend Simon.

## 5. Géolocalisation (vue carte) — Axe 6, tous les modules sans exception
| Module | Statut | Dernière màj |
|---|---|---|
| entreprises | pas commencé | 2026-11-10 |
| associations | pas commencé | 2026-11-10 |
| budget | pas commencé | 2026-11-10 |
| marches_publics | pas commencé | 2026-11-10 |
| deliberations | pas commencé | 2026-11-10 |
| population | pas commencé | 2026-11-10 |
| eau_potable | pas commencé | 2026-11-10 |
| etablissements_scolaires | pas commencé | 2026-11-10 |
| adresses | pas commencé | 2026-11-10 |
| elus | pas commencé | 2026-11-10 |
| elections | pas commencé | 2026-11-10 |
| immobilier_dvf | pas commencé | 2026-11-10 |
| irve | pas commencé | 2026-11-10 |

`bbox_depuis_contour()` déjà disponible dans le toolkit (`rudi_harvest_toolkit.commune`),
testé (Polygon/MultiPolygon/anneaux intérieurs/axes non mélangés) — reste le câblage dans
les 13 modules.

## Backlog v4 (hors scope de cette v3, détaillé plus bas)
- Fusion des JDD élections (toutes années/types/tours en un seul JDD structuré)
- Historique budget plus profond + documentation des variables complexes (DGFiP)
- Publication GeoJSON par ligne (au-delà de la bbox dataset simple de l'axe 6)
- Contacts restant introuvables : Mégalis Bretagne, Hub'eau/BRGM, Éducation nationale
- Faire pointer `moissonneuse-batteuse/datagouv_to_rudi.py` vers
  `LICENCES_DATAGOUV_CONNUES` du toolkit au lieu de sa copie locale (évite une 3ᵉ
  divergence future, pas une obligation immédiate)

## Point à arbitrer (ni v3 ni v4, dépend du budget)
- Test d'intégration `executer_run()` sur les 13 modules (signature, threading, absence
  d'exception non rattrapée) — recommandé par la relecture technique, coût non trivial ;
  à faire si le budget de cette v3 le permet, sinon les tests statiques de complétude et
  de contrat de signature couvrent l'essentiel du risque pour un coût bien moindre.

## Journal
- 2026-11-09 : plan v3 conçu, recherche web faite (licences, contacts, source DECP).
- 2026-11-10 : plan relu en 3 passes opencode (architecture, testabilité, produit) et
  corrigé en conséquence.
- 2026-11-10 : Axe 1 implémenté et testé (`rudi_harvest_toolkit.wikipedia` +
  `description_commune.py` + câblage `organisations.py`/`cli.py`/13 modules) —
  `bbox_depuis_contour()` (Axe 6) ajouté en même temps au toolkit (même fichier,
  `commune.py`), câblage dans les modules restant à faire (voir § 5 ci-dessus).
