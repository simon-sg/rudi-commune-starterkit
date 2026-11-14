"""Contenu éditorial statique du guide utilisateur HTML (MkDocs) de
``rudi-commune-starterkit`` — voir ``guide/README.md`` pour le principe général.

Ce module est la **seule source de vérité** pour tout texte qui n'est pas extrait
directement de ``registre.py`` (titre/synopsis/description/thème/fréquence des 13 JDD —
ceux-là restent dans le code des modules, jamais dupliqués ici, voir
``guide/generer.py::_fiche_jdd``). Rédigé pour un **agent municipal non technique**
(décision BACKLOG.md, chantier C) : langage métier, jargon expliqué au premier usage,
jamais de supposition sur ce que le lecteur sait déjà.

Les citations du wizard (``pas-à-pas.md``) reprennent mot pour mot les invites de
``cli.py`` — vérifié par ``tests/test_guide.py`` (contrat statique anti-dérive) :
si quelqu'un reformule une invite du wizard sans toucher à ce fichier, ce test casse.
"""

from __future__ import annotations

# Commune utilisée pour illustrer les 13 fiches — la même que les fixtures de test de
# ce dépôt (tests/test_cli.py::_GEVEZE) : pas une vraie moisson en direct (aucun appel
# réseau pendant la génération du guide), juste les patrons TITRE/SYNOPSIS_PATRON/
# DESCRIPTION_PATRON du code, rendus avec un exemple cohérent avec le reste du projet.
COMMUNE_EXEMPLE = {"nom": "Gévezé", "code_insee": "35120"}

# THEME (interne, module.THEME) -> libellé de regroupement en français, pour la page
# "Les données publiées". Toute valeur absente d'ici s'affiche telle quelle (defensive,
# voir generer.py) plutôt que de planter si un futur module introduit un nouveau thème.
THEME_LIBELLES: dict[str, str] = {
    "society": "Démographie",
    "economy": "Économie locale",
    "citizenship": "Citoyenneté & vie démocratique",
    "health": "Santé",
    "transportation": "Transports",
    "housing": "Habitat & logement",
    "education": "Éducation",
    "location": "Adresses & voirie",
}

# FREQUENCE_MAJ (interne, module.FREQUENCE_MAJ) -> formulation lisible. Repli sur la
# valeur brute si absente (même logique défensive que THEME_LIBELLES).
FREQUENCE_LIBELLES: dict[str, str] = {
    "annuelle": "chaque année",
    "mensuelle": "chaque mois",
    "à chaque élection": "à chaque élection",
    "quasi quotidienne": "presque tous les jours",
}

ORDRE_GROUPES = [
    "Démographie", "Économie locale", "Citoyenneté & vie démocratique", "Santé",
    "Transports", "Habitat & logement", "Éducation", "Adresses & voirie",
]


# --------------------------------------------------------------------------------------
# Accueil
# --------------------------------------------------------------------------------------

PAGE_ACCUEIL = """# Les données ouvertes de votre commune

Ce guide accompagne **rudi-commune-starterkit**, l'outil qui publie automatiquement,
sur une plateforme ouverte appelée RUDI, un socle de données publiques concernant une
commune : population, budget, marchés publics, qualité de l'eau, bornes de recharge
électrique, et dix autres sujets. Les données publiées proviennent toutes de sources
publiques déjà ouvertes (INSEE, data.gouv.fr, DGFiP...) — l'outil les retrouve, les
met en forme et les republie de façon lisible pour la commune concernée, il ne crée
aucune donnée nouvelle.

Trois entrées, selon ce que vous cherchez :

<div class="grid cards" markdown>

-   :material-help-circle:{ .lg .middle } **Je veux utiliser l'outil pour ma commune**

    ---

    Le guide pas-à-pas, les prérequis, et quoi faire en cas de blocage.

    [:octicons-arrow-right-24: Commencer le guide d'utilisation](guide/prerequis.md)

-   :material-database:{ .lg .middle } **Quelles données sont publiées, et d'où
    viennent-elles ?**

    ---

    Les 13 fiches de données, classées par thème.

    [:octicons-arrow-right-24: Voir les données publiées](donnees/index.md)

-   :material-frequently-asked-questions:{ .lg .middle } **J'ai une question, ou je
    veux signaler/corriger une donnée**

    ---

    Licences, vie privée, comment demander une correction.

    [:octicons-arrow-right-24: Foire aux questions](faq.md)

</div>

!!! note "Ce guide ne contient aucune donnée réelle"
    Les exemples de ce site (commune, chiffres, adresses) sont illustratifs — ils
    servent à montrer la forme des données publiées, pas leur contenu réel pour une
    commune précise. Les vraies données de votre commune sont consultables sur le
    portail RUDI qui vous a été indiqué par l'administrateur de votre territoire.
"""


# --------------------------------------------------------------------------------------
# Guide d'utilisation — 7 pages, entre l'accueil et les fiches JDD
# --------------------------------------------------------------------------------------

_PAGE_PREREQUIS = """# Prérequis

Avant de commencer, réunissez ces quatre éléments — comptez environ 15 minutes pour
tout rassembler et lancer l'outil une première fois.

## 1. Un ordinateur Windows

La version actuelle de l'outil (un fichier `.exe` à double-cliquer) fonctionne sous
**Windows**. Aucune installation de logiciel supplémentaire n'est nécessaire, et aucun
droit administrateur sur l'ordinateur n'est requis.

## 2. Une connexion internet

L'outil interroge plusieurs sources publiques en ligne (INSEE, data.gouv.fr, DGFiP...)
et publie le résultat sur le nœud RUDI de votre territoire — tout se fait en ligne,
rien ne fonctionne hors connexion.

## 3. Le code INSEE de votre commune

Un numéro à 5 caractères qui identifie officiellement votre commune (ex. `35120`). Si
vous ne le connaissez pas, il figure sur la plupart des documents administratifs de la
mairie, ou se retrouve facilement en recherchant le nom de la commune suivi de « code
INSEE ».

## 4. Les identifiants d'accès à un nœud RUDI — **le point à vérifier en premier**

C'est le point de blocage le plus probable si vous n'avez pas anticipé : il vous faut

- l'**adresse (URL)** du nœud RUDI de votre territoire,
- un **nom d'utilisateur**,
- un **mot de passe**.

Ces trois informations ne sont **pas** fournies par cet outil — elles sont délivrées
par la structure qui héberge et administre le nœud RUDI dont dépend votre commune
(selon les territoires : un établissement intercommunal, un département, une région,
ou toute autre structure porteuse du dispositif). **Sans ces identifiants, l'outil
s'arrêtera proprement à l'étape « test de connexion » — il ne peut rien publier sans
eux.** Si vous ne les avez pas, c'est le moment de les demander, avant de poursuivre.

!!! tip "Fortement recommandé : demandez aussi l'adresse du portail public"
    En plus de l'adresse technique du nœud, demandez l'adresse du **portail** public
    associé (l'adresse du site web sur lequel les données apparaissent). Elle est
    facultative pour publier, mais sans elle vous ne pourrez pas annuler une
    publication de test plus tard (voir [Annuler une publication de
    test](vider.md)) — mieux vaut l'avoir sous la main dès le départ.

## Pense-bête

Avant de lancer l'outil, notez ces quatre informations quelque part (un brouillon de
mail, un post-it) : l'assistant les demande une seule fois et les enregistre pour la
prochaine fois, mais la première saisie va plus vite si vous n'avez pas à chercher en
cours de route.
"""

_PAGE_TELECHARGER = """# Télécharger et lancer l'outil

## Téléchargement

L'outil se télécharge en un seul fichier, sans installation :

```
https://github.com/simon-sg/rudi-commune-starterkit/releases/latest/download/rudi-commune-starterkit.exe
```

Ce lien pointe toujours vers la **dernière version publiée** — pas besoin de vérifier
un numéro de version, enregistrez simplement le fichier `.exe` où vous le retrouverez
(le Bureau ou le dossier Téléchargements conviennent très bien).

## Premier lancement

Double-cliquez sur le fichier téléchargé. Une fenêtre noire (une console) s'ouvre et
affiche :

```text
Chargement des ressources, merci de patienter...
```

Ce message est normal et peut rester affiché plusieurs secondes avant que la première
question n'apparaisse — ce n'est pas un blocage, l'outil charge ce dont il a besoin
avant de commencer.

Avant d'arriver à ce message, Windows affichera presque certainement un ou deux
avertissements de sécurité normaux — voir la page suivante, [Premiers
avertissements](avertissements.md), pour savoir à quoi vous attendre et comment les
franchir en toute connaissance de cause.
"""

_PAGE_AVERTISSEMENTS = """# Premiers avertissements (normaux)

Au tout premier lancement, deux avertissements sont probables. Ils ne signifient pas
que quelque chose a échoué — ils apparaissent parce que ce fichier `.exe` n'est pas
signé numériquement par un éditeur reconnu (une signature coûte un certificat payant,
hors périmètre de cette première version de l'outil).

## « Windows a protégé votre ordinateur » (SmartScreen)

C'est l'avertissement le plus probable. Il s'affiche la première fois qu'on exécute un
fichier téléchargé qui n'a pas encore de réputation connue par Microsoft.

1. Cliquez sur **« Informations complémentaires »**.
2. Un bouton **« Exécuter quand même »** apparaît — cliquez-le.

!!! warning "Vérifiez la provenance du fichier avant de passer cet avertissement"
    Cet avertissement existe pour une bonne raison en général : n'exécutez que le
    fichier téléchargé depuis le lien officiel ci-dessus
    ([Télécharger et lancer l'outil](telecharger.md)), jamais une copie reçue par un
    autre canal (email, clé USB non vérifiée...).

## Alerte antivirus

Un antivirus peut occasionnellement signaler le fichier par précaution — c'est un
comportement connu des programmes construits avec l'outil utilisé ici
(« PyInstaller ») pour assembler un `.exe` autonome non signé, pas un signe réel de
logiciel malveillant. Si votre antivirus d'entreprise bloque complètement
l'exécution plutôt que de simplement avertir, il faudra probablement l'aide du
service informatique de votre structure pour autoriser ce fichier précis.

Une fois ces écrans passés, l'outil démarre normalement — passez à la page suivante,
[Le pas-à-pas, écran par écran](pas-a-pas.md).
"""

_PAGE_PAS_A_PAS = """# Le pas-à-pas, écran par écran

Cette page reprend, dans l'ordre réel, toutes les questions posées par l'assistant au
premier lancement pour une nouvelle commune. Chaque bloc gris reproduit ce qui
s'affiche réellement ; le texte au-dessus explique quoi répondre.

## 1. Code INSEE

```text
Code INSEE de la commune :
```

Tapez le code à 5 caractères réuni à l'étape [Prérequis](prerequis.md). L'outil
affiche alors le nom de la commune qu'il a trouvé :

```text
→ Gévezé (35120), Ille-et-Vilaine (Bretagne), population 7200
```

**Vérifiez que c'est bien votre commune avant de continuer** — un code INSEE mal
recopié pointerait silencieusement vers une autre commune.

## 2. Aperçu de ce qui pourra être publié

```text
Avant de commencer, un aperçu rapide de ce qui pourra être publié pour votre
commune :
  - Entreprises : a priori disponible
  - Associations : a priori disponible
  ... (13 lignes, une par donnée)
```

C'est purement informatif — une ligne « hors couverture » (cela ne concerne
aujourd'hui que les délibérations, hors Bretagne) n'est pas une erreur, juste un
signal que cette donnée particulière ne sera pas publiée pour une raison déjà connue
avant même de commencer.

## 3. Adresses du nœud

```text
URL du nœud RUDI (https://...) — l'adresse transmise par l'administrateur de
votre territoire :
URL catalogue (si l'administrateur de votre territoire vous en a transmis une,
indiquez-la ici ; sinon laissez vide — la déduction automatique ne fonctionne
pas sur tous les nœuds, notamment ceux hébergés par un tiers) [] :
URL du portail (optionnelle, mais recommandée — sans elle, impossible d'annuler
une publication de test plus tard) [] :
```

- La première adresse est **obligatoire** — celle réunie à l'étape
  [Prérequis](prerequis.md).
- La deuxième : si l'administrateur vous en a transmis une, indiquez-la. Sinon,
  laissez vide — mais si le programme vous signale ensuite qu'il n'arrive pas à
  joindre le catalogue, c'est le signe qu'il faut la demander à l'administrateur
  plutôt que de laisser vide.
- La troisième est facultative mais **fortement recommandée** — voir l'encart de la
  page [Prérequis](prerequis.md).

## 4. Identifiants

```text
Nom d'utilisateur (fourni par l'administrateur du nœud) :
Mot de passe (fourni par l'administrateur du nœud) :
```

Les identifiants réunis à l'étape [Prérequis](prerequis.md) — jamais à inventer. Le
mot de passe ne s'affiche pas à l'écran pendant la saisie (aucun caractère, pas même
des étoiles) : c'est normal, il est bien pris en compte.

## 5. Enregistrer le mot de passe ?

```text
Enregistrer ces identifiants pour la prochaine fois (o/N) :
```

Répondre **oui** range le mot de passe dans le gestionnaire sécurisé de Windows (le
« trousseau ») : au prochain lancement, vous n'aurez plus à le ressaisir. Recommandé
sur un poste personnel ou un poste de bureau habituel ; répondez **non** sur un
ordinateur partagé par plusieurs personnes.

## 6. Test de connexion

```text
Test de connexion au nœud…
  OK.
```

Si tout est correct, ce test passe en une seconde. **Cas particulier à connaître** :
si le nœud utilise un certificat de sécurité que Windows ne reconnaît pas (fréquent
sur un nœud de test), l'outil affiche un avertissement détaillé et demande de taper
`ACCEPTER` en toutes lettres pour continuer malgré tout. **N'acceptez que si vous
savez que ce nœud est bien celui de votre territoire** — en cas de doute, arrêtez-vous
et contactez l'administrateur de votre nœud plutôt que de valider à l'aveugle (voir
[En cas de problème](depannage.md)).

## 7. Qui doit apparaître comme auteur de vos données ?

```text
Qui doit être présenté comme l'auteur de vos données sur le portail ?
  1) Toujours la mairie
  2) L'organisme réellement à l'origine de chaque donnée (ex. l'INSEE pour la
     population) — recommandé, par défaut
  3) Je choisis donnée par donnée
Choix [2] :
```

Le choix **2** (celui déjà sélectionné par défaut, appuyez simplement sur Entrée) est
recommandé : il affiche le véritable organisme à l'origine de chaque donnée (l'INSEE
pour la population, la DGFiP pour le budget...), ce qui est plus transparent pour qui
consulte la fiche ensuite. Le choix **1** présente systématiquement la mairie comme
auteure, quelle que soit l'origine réelle de la donnée.

## 8. Email de contact (si la mairie est auteure d'au moins une donnée)

```text
Email de contact de la commune (sera visible publiquement sur les fiches de
données concernées) :
```

Cette question n'apparaît que si vous avez choisi l'option 1 (ou désigné la mairie
pour au moins une donnée à l'option 3). **Cette adresse devient publique**, affichée
sur les fiches concernées — à choisir en connaissance de cause (une adresse de service
plutôt qu'une adresse personnelle, par exemple).

## 9. Republier même sans changement ?

```text
Republier aussi les données qui n'ont pas changé depuis la dernière fois (plus
lent, rarement nécessaire) (o/N) :
```

Laissez la réponse par défaut (**non**) sauf besoin particulier : l'outil republie de
toute façon automatiquement tout ce qui a réellement changé depuis la dernière fois.

## 10. Lancement et rapport final

L'outil publie alors chaque donnée, une par une, et affiche à la fin un rapport :

```text
=== Rapport ===
  publié : Population, Budget communal, Marchés publics, ...
  sauté (inchangé) : Entreprises
  sauté (hors couverture) : Délibérations
```

- **publié** / **mis à jour** : tout s'est bien passé.
- **sauté (inchangé)** : rien à republier, la donnée n'a pas changé depuis la
  dernière fois — normal, pas un problème.
- **sauté (hors couverture)** / **sauté (vide)** : la donnée ne concerne pas votre
  commune ou n'existe pas pour elle à ce jour (ex. délibérations hors Bretagne) — pas
  une erreur à corriger.
- **échec** : voir [En cas de problème](depannage.md).

!!! info "Cas particulier : « en attente de validation »"
    Si c'est la toute première publication pour votre commune, l'outil peut afficher
    qu'une nouvelle organisation a été créée et qu'elle est en attente de validation par l'animateur du portail (la personne qui valide les nouvelles organisations).
    **Ce n'est pas un échec** — c'est un rendez-vous à reprendre une fois cette
    validation faite, pas une erreur à corriger de votre côté. L'outil propose alors
    d'appuyer sur Entrée pour vérifier si l'animateur a validé et reprendre, ou de
    taper `q` pour quitter et relancer plus tard — vos informations déjà saisies sont
    conservées, vous n'aurez rien à ressaisir.

!!! danger "En cas d'échec, lisez le message avant de retaper R pour réessayer"
    Si l'échec survient **après** la création d'une organisation ou la publication
    d'une donnée, l'outil le signale explicitement et conseille de vérifier sur le
    nœud avant de relancer — relancer immédiatement dans ce cas précis peut créer un
    doublon. Ce n'est pas un réflexe à avoir systématiquement, seulement dans ce cas
    précis signalé par l'outil lui-même.
"""

_PAGE_RELANCER = """# Relancer et mettre à jour

L'outil se souvient de chaque commune déjà configurée — vous n'aurez pas à ressaisir
toutes les informations à chaque fois.

## Au lancement suivant

L'assistant affiche directement la liste des communes déjà enregistrées :

```text
Communes déjà enregistrées :
  1) Gévezé (35120) — https://noeud.exemple.fr
  0) Nouvelle commune
  q) Quitter
Reprendre quelle commune [0] :
```

Tapez le numéro de votre commune, puis choisissez :

```text
  1) Publier/mettre à jour les données  2) Annuler une publication de test
  (vider cette commune) — Action [1] :
```

Le choix **1** republie les données — l'outil retrouve automatiquement l'adresse du
nœud et le nom d'utilisateur déjà enregistrés ; seul le mot de passe peut être
redemandé s'il n'a pas été enregistré dans le trousseau (voir l'étape 5 du
[pas-à-pas](pas-a-pas.md)).

## Que fait réellement une mise à jour ?

L'outil republie **seulement ce qui a réellement changé** depuis la dernière fois
(nouvelles données, données corrigées) — il ne republie pas inutilement ce qui est
identique, ce qui rend une relance rapide même avec les 13 données.

## À quelle fréquence relancer ?

Cela dépend de la donnée — la plupart changent rarement (le budget communal, par
exemple, une fois par an), mais relancer une fois par mois convient pour rester à jour
sans y penser. Les marchés publics et les élections, qui évoluent plus vite, profitent
d'une relance plus fréquente si vous le souhaitez — ce n'est jamais obligatoire,
seulement plus à jour.
"""

_PAGE_VIDER = """# Annuler une publication de test

Si vous avez publié des données à titre d'essai et souhaitez les retirer, l'outil
propose de « vider » une commune : cela supprime les données déjà publiées par cet
outil pour cette commune (et, si vous le demandez, l'organisation elle-même).

!!! warning "Nécessite l'adresse du portail renseignée au moment de la publication"
    Cette fonction a besoin de l'adresse du portail notée à l'étape 3 du
    [pas-à-pas](pas-a-pas.md). Si vous ne l'aviez pas renseignée, reprenez le profil
    de la commune (voir [Relancer et mettre à jour](relancer.md)) et ajoutez-la avant
    de continuer — l'assistant propose de corriger ce champ.

## Marche à suivre

1. Relancez l'outil, choisissez votre commune dans la liste.
2. Choisissez l'action **« 2) Annuler une publication de test (vider cette
   commune) »**.
3. L'outil demande :

```text
Supprimer aussi l'organisation de la commune (si aucune autre donnée du nœud ne
s'y réfère encore) (o/N) :
```

   Répondez **oui** si vous souhaitez un nettoyage complet (plus aucune trace de la
   commune sur le nœud) ; **non** si vous préférez ne retirer que les données et
   garder l'organisation en place pour une prochaine publication.

4. Un rapport final indique ce qui a été supprimé, et ce qui, le cas échéant, n'a pas
   pu l'être.

Cette opération est pensée pour un usage de test — elle n'est pas nécessaire dans le
cadre d'un usage normal, où l'on relance simplement l'outil pour mettre à jour (voir
[Relancer et mettre à jour](relancer.md)).
"""

_PAGE_DEPANNAGE = """# En cas de problème

| Ce qui s'affiche | Ce que ça veut dire | Quoi faire |
|---|---|---|
| « Windows a protégé votre ordinateur » | Avertissement normal, fichier non signé | Voir [Premiers avertissements](avertissements.md) |
| Certificat de sécurité (TLS) non reconnu | Le nœud utilise un certificat que Windows ne reconnaît pas (fréquent sur un nœud de test) | N'acceptez (`ACCEPTER`) que si vous êtes certain de l'adresse du nœud ; sinon contactez l'administrateur de votre territoire |
| « Nœud injoignable » | L'adresse du nœud est incorrecte, ou le réseau/internet est indisponible | Vérifiez l'adresse (copier-coller plutôt que recopier à la main) et votre connexion internet |
| Échec sur une seule donnée (ex. marchés publics) pendant que les autres réussissent | La source de cette donnée en particulier est temporairement indisponible | Rien à faire de votre côté — relancez plus tard, les autres données ne sont pas concernées |
| Coupure réseau pendant une donnée volumineuse (ex. valeurs foncières) | Coupure réseau en cours de téléchargement | L'outil retente automatiquement plusieurs fois ; si l'échec persiste, réessayez depuis un réseau plus stable |
| « En attente de validation par l'animateur du portail » | Pas une erreur — une personne doit valider la nouvelle organisation de votre commune | Voir l'encart dédié du [pas-à-pas](pas-a-pas.md#10-lancement-et-rapport-final), étape 10 |
| Mot de passe introuvable dans le trousseau | Les identifiants n'ont pas été enregistrés lors d'un lancement précédent | Ressaisissez le mot de passe quand l'outil le redemande |

Si le problème persiste et n'est pas listé ci-dessus, contactez la structure qui
administre votre nœud RUDI (celle qui vous a fourni les identifiants à l'étape
[Prérequis](prerequis.md)) — elle pourra vérifier l'état du nœud de son côté.
"""

PAGES_GUIDE: dict[str, str] = {
    "prerequis.md": _PAGE_PREREQUIS,
    "telecharger.md": _PAGE_TELECHARGER,
    "avertissements.md": _PAGE_AVERTISSEMENTS,
    "pas-a-pas.md": _PAGE_PAS_A_PAS,
    "relancer.md": _PAGE_RELANCER,
    "vider.md": _PAGE_VIDER,
    "depannage.md": _PAGE_DEPANNAGE,
}

# Citations exactes du wizard (cli.py) reprises dans _PAGE_PAS_A_PAS — vérifiées mot
# pour mot par tests/test_guide.py pour détecter toute dérive future entre le texte
# réel du wizard et ce tutoriel. Ne pas reformuler ici sans reformuler aussi cli.py
# (ou l'inverse), sous peine de faire échouer ce test.
CITATIONS_WIZARD_A_VERIFIER = [
    "Avant de commencer, un aperçu rapide de ce qui pourra être publié pour votre",
    "URL du nœud RUDI (https://...) — l'adresse transmise par l'administrateur",
    "URL catalogue (si l'administrateur de votre territoire vous en a transmis",
    "URL du portail (optionnelle, mais recommandée — sans elle, impossible",
    "Nom d'utilisateur (fourni par l'administrateur du nœud)",
    "Mot de passe (fourni par l'administrateur du nœud)",
    "Enregistrer ces identifiants pour la prochaine fois",
    "Qui doit être présenté comme l'auteur de vos données sur le portail ?",
    "Toujours la mairie",
    "L'organisme réellement à l'origine de chaque donnée (ex. l'INSEE pour",
    "Je choisis donnée par donnée",
    "Email de contact de la commune (sera visible publiquement sur les fiches",
    "Republier aussi les données qui n'ont pas changé depuis la dernière fois",
    "Publier/mettre à jour les données  2) Annuler une publication",
    "Supprimer aussi l'organisation de la commune (si aucune autre donnée du nœud",
    "en attente de validation par l'animateur du portail (la personne qui",
    "pour vérifier si l'animateur a validé et reprendre",
]


# --------------------------------------------------------------------------------------
# Données publiées — introduction de l'index (le reste est généré, voir generer.py)
# --------------------------------------------------------------------------------------

PAGE_DONNEES_INTRO = f"""# Les données publiées

Treize fiches de données peuvent être publiées pour une commune, regroupées ici par
thème. Chacune provient d'une source publique nationale déjà ouverte (INSEE,
data.gouv.fr, DGFiP...) — l'outil ne crée aucune donnée, il la met en forme et la
republie de façon lisible pour la commune concernée.

Les exemples ci-dessous illustrent la forme des fiches pour **{COMMUNE_EXEMPLE['nom']}
({COMMUNE_EXEMPLE['code_insee']})**, à titre d'exemple — le contenu réel dépend de
chaque commune. Pour le détail technique complet d'une donnée réellement publiée
(variables précises, limites de couverture), consultez sa fiche sur le portail RUDI
de votre commune ; chaque fiche y indique aussi un contact pour toute question sur
cette donnée précise.
"""


# --------------------------------------------------------------------------------------
# FAQ
# --------------------------------------------------------------------------------------

PAGE_FAQ = """# Foire aux questions

## C'est quoi, RUDI ?

RUDI est le dispositif technique qui héberge et republie les données décrites par ce
guide. Chaque territoire (commune, intercommunalité, département...) peut avoir son
propre « nœud » RUDI — le serveur qui stocke effectivement les données — relié à un
« portail », le site web public où les données sont consultables.

## Est-ce que mes données personnelles sont publiées ?

Non. Les 13 données décrites dans ce guide sont toutes des données publiques agrégées
ou déjà ouvertes par d'autres administrations (INSEE, DGFiP, data.gouv.fr...) — aucune
donnée personnelle nominative n'est publiée par cet outil. Les coordonnées de contact
qui apparaissent sur certaines fiches sont celles d'un service (la mairie, un
organisme producteur), jamais celles d'une personne privée.

## C'est quoi une « licence ouverte » ?

Une licence ouverte est une autorisation donnée à l'avance : elle précise ce que
quiconque peut faire avec une donnée (la réutiliser, la republier, la croiser avec
d'autres données) sans avoir à demander une permission au cas par cas, généralement en
échange d'une simple mention de la source. Voir la page [Licences et
réutilisation](licences.md) pour le détail.

## Comment demander une correction ou un retrait ?

Chaque fiche de données publiée indique, sur le portail RUDI, un contact pour la
donnée concernée (généralement l'organisme producteur — la mairie pour certaines
données, l'organisme source pour d'autres). C'est le bon point de contact pour
signaler une erreur ou demander une correction. Les données provenant de sources
publiques déjà ouvertes (INSEE, data.gouv.fr...) relèvent par ailleurs des procédures
de ces organismes eux-mêmes pour toute correction à la source.

## L'outil peut-il casser quelque chose en cas d'erreur de ma part ?

L'outil ne modifie jamais une donnée tierce sur le nœud — il ne publie et ne supprime
que les données qu'il a lui-même publiées pour la commune concernée. Une mauvaise
réponse à une question se corrige en relançant l'outil (voir [Relancer et mettre à
jour](guide/relancer.md)) ; une publication de test peut être entièrement annulée
(voir [Annuler une publication de test](guide/vider.md)).

## Je suis à l'aise avec la ligne de commande, puis-je faire autrement ?

Oui — l'exécutable décrit par ce guide est un simple emballage du même outil en ligne
de commande (`pip install` puis `rudi-commune-starterkit`), qui propose aussi un mode
scriptable (sans aucune question posée, pour une automatisation régulière). Voir le
fichier `README.md` du projet sur GitHub pour cette voie technique.
"""


# --------------------------------------------------------------------------------------
# Glossaire
# --------------------------------------------------------------------------------------

PAGE_GLOSSAIRE = """# Glossaire

**RUDI**
: Le dispositif technique (nœud + portail) qui héberge et republie les données
décrites par ce guide.

**Nœud**
: Le serveur technique qui stocke et diffuse réellement les données d'un territoire —
l'adresse demandée à l'étape 3 du [pas-à-pas](guide/pas-a-pas.md).

**Portail**
: Le site web public où les données d'un territoire sont consultables par tous —
distinct, techniquement, du nœud qui les héberge.

**Jeu de données (JDD)**
: Terme technique désignant une « fiche de données » — ex. la fiche Population, la
fiche Budget communal. Ce guide utilise plutôt « donnée » ou « fiche de données ».

**Organisation**
: Sur le portail RUDI, la fiche qui identifie l'auteur d'une donnée (ex. « Commune de
Gévezé », ou « INSEE »). Chaque commune a sa propre organisation, créée automatiquement
lors de la première publication.

**Animateur du portail**
: La personne chargée de valider les nouvelles organisations créées sur le portail —
une étape normale, pas un contrôle de qualité des données elles-mêmes.

**Trousseau**
: Le gestionnaire de mots de passe sécurisé intégré à Windows — l'outil propose d'y
enregistrer votre mot de passe pour ne pas le ressaisir à chaque lancement.

**Code INSEE**
: Le numéro à 5 caractères qui identifie officiellement une commune française.
"""


# --------------------------------------------------------------------------------------
# Licences
# --------------------------------------------------------------------------------------

PAGE_LICENCES = """# Licences et réutilisation

Chaque donnée publiée porte une licence — une autorisation donnée à l'avance qui
précise ce que quiconque peut en faire sans demander de permission au cas par cas. Ce
guide ne republie pas de données au hasard d'une licence inconnue : l'outil échoue
explicitement plutôt que de publier une licence devinée si elle n'a pas pu être
confirmée pour une donnée donnée.

## Les licences rencontrées

La plupart des données publiées par cet outil portent l'une de ces licences ouvertes
françaises courantes :

- **Licence Ouverte / Open Licence (Etalab)** — la licence de référence de l'open data
  français : réutilisation libre, y compris commerciale, en citant la source.
- **ODbL (Open Database License)** — autorise la réutilisation et la modification, à
  condition de republier sous la même licence toute base de données qui en dérive.
- Une licence **spécifique au producteur** (« CUSTOM ») lorsque l'organisme source en
  définit une particulière, distincte des deux précédentes.

## Où trouver la licence d'une donnée précise

La licence exacte d'une donnée est indiquée directement sur sa fiche, sur le portail
RUDI de votre commune — elle peut varier d'une donnée à l'autre (une fiche « SIRENE »
n'a pas forcément la même licence qu'une fiche « DGFiP »), d'où l'absence d'une licence
unique valable pour l'ensemble du socle.

## Puis-je réutiliser ces données pour mon propre usage ?

Oui, dans les conditions prévues par la licence indiquée sur chaque fiche — c'est
justement le principe d'une licence ouverte : la réutilisation est autorisée à
l'avance, sans démarche supplémentaire, dans ces conditions.
"""
