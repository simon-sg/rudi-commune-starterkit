# Changelog

## Non publié — v3 : descriptions, contacts, licences, dates, géographie (voir BACKLOG.md)

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

## Non publié — entreprises/associations/élections/délibérations : CSV au lieu de JSON

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

## Non publié — organisation : plus d'appel portail automatisé à la suppression

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

## Non publié — vidage : plus d'appel portail séparé pour les datasets

`vider_commune()` appelait `supprimer_dataset_portail()` (OAuth2 direct au portail)
en plus de `supprimer_dataset()` (nœud) pour chaque JDD supprimé — ce second appel
échouait systématiquement en `401` dès qu'un profil n'a pas de compte ROBOT portail
dédié (le cas général : ce socle n'en a jamais eu). Confirmé par le code source du
nœud que `supprimer_dataset()` seul déclenche déjà ce relais automatiquement, avec
l'identité propre du nœud — un seul appel par JDD désormais, dans les deux boucles de
suppression (JDD suivis par l'état local et JDD non suivis détectés sur le nœud).

## Non publié — `--vider-commune` : détecte et propose les JDD non suivis

Avec `--supprimer-organisation`, si d'autres JDD référencent encore l'organisation
sans être suivis par ce socle (publiés par un autre outil sur le même nœud, ou un
test manuel), leur suppression est désormais détectée et **proposée** séparément
(confirmation `SUPPRIMER` dédiée) plutôt que de bloquer la suppression de
l'organisation sans aucun recours.

## Non publié — corrige deux bugs réels trouvés en conditions de production

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
