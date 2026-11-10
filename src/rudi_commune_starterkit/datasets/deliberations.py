"""JDD « Délibérations » — Mégalis Bretagne, filtré par SIREN de la commune.

Confirmé le 2026-11-07 : ``data-publication.megalis.bretagne.bzh/mq_apis/actes/v1/search``
accepte ``siren`` et pagine par curseur opaque (``page_suivante``, **jamais** un numéro de
page) — 1039 actes pour Gévezé sur un seul run. **Piège trouvé en testant** : le jeton de
curseur contient des caractères (``+``/``=``) qui cassent silencieusement la pagination
s'ils ne sont pas correctement pourcent-encodés dans l'URL (une requête `curl` brute
renvoyait la même page indéfiniment) — ``requests``/``session.get(..., params=...)`` encode
correctement, mais c'est un piège à connaître pour toute ré-implémentation.

Chaque acte référence un PDF déjà public à une URL stable (``data.megalis.bretagne.bzh``) :
pas question de retélécharger/réheberger 1000+ PDF nous-mêmes. Le **FILE combiné** est donc
un index JSON (date, objet, classification, URL du PDF par acte), pas une fusion de
contenu — une seule requête ne suffit jamais (pagination), donc jamais un FILE hybride.

**Hors Bretagne, Mégalis ne couvre rien** — détecté sans aucun appel réseau
(``commune["code_region"]``), avant même de résoudre le SIREN.

**Producteur toujours la commune, jamais Mégalis** (voir ``organisations.py`` —
``resoudre_producer()`` retourne systématiquement :func:`organisation_commune` pour cette
clé, quel que soit ``mode_producer``) : Mégalis n'est qu'une plateforme de republication,
la commune est déjà la productrice réelle de ses propres délibérations.
"""

from __future__ import annotations

import csv
import os

from rudi_harvest_toolkit.commune import resoudre_siren_commune
from rudi_harvest_toolkit.description import construire_description_structuree
from rudi_harvest_toolkit.http_dates import parser_date_iso_stricte
from rudi_harvest_toolkit.pivot import construire_rudi_metadata, media_filtre
from rudi_harvest_toolkit.http import session

from .. import licences, organisations
from ..resultat import ResultatConnecteur, StatutConnecteur
from ._commun import contacts_pour_producer, geography_pour_commune, local_id_jdd

CLE = organisations.DELIBERATIONS
THEME = "citizenship"
TITRE = "Délibérations"
SYNOPSIS_PATRON = "Index des délibérations de la commune de {commune} ({code_insee})"
DESCRIPTION_PATRON = (
    "Index des délibérations du conseil municipal de la commune de {commune} "
    "({code_insee}), diffusées via la plateforme Mégalis Bretagne - chaque entrée pointe "
    "vers le document PDF original, hébergé par Mégalis, jamais recopié ici. Instantané "
    "figé à la date de moisson - pas une vue live ni mise à jour en continu."
)
FREQUENCE_MAJ = "mensuelle"

_MEGALIS_API = "https://data-publication.megalis.bretagne.bzh/mq_apis/actes/v1/search"
CODE_REGION_BRETAGNE = "53"
PLAFOND_PAGES_DEFAUT = 500

_CHAMPS_ACTE = (
    "id", "date_acte", "date_publication", "objet", "classification_code",
    "classification_libelle", "typologie", "content_type", "url",
)


def _simplifier_acte(acte: dict) -> dict:
    return {champ: acte.get(champ) for champ in _CHAMPS_ACTE}


def _date_plus_recente_actes(actes: list[dict]) -> str | None:
    """MAX(date_acte, date_publication) sur tous les actes déjà chargés — aucune
    requête supplémentaire. None si aucun acte n'a de date exploitable (jamais
    deviné)."""
    dates = [
        iso
        for acte in actes
        for champ in ("date_acte", "date_publication")
        if (iso := parser_date_iso_stricte(acte.get(champ)))
    ]
    return max(dates) if dates else None


def _description_enrichie(commune: dict, code_insee: str) -> str:
    return construire_description_structuree(
        quoi=(
            f"Index des délibérations et actes du conseil municipal de {commune['nom']} "
            f"({code_insee}), diffusés via la plateforme Mégalis Bretagne."
        ),
        comment_construit=(
            "Chaque entrée pointe vers le document PDF original, hébergé par Mégalis "
            "Bretagne, jamais recopié ici (ce JDD est un index, pas une archive de "
            "documents). Récupéré par pagination par curseur sur l'API de recherche "
            "d'actes de Mégalis, filtrée par SIREN de la commune."
        ),
        structure_variables=[
            "Identifiant et dates (id, date_acte, date_publication)",
            "Objet et classification (objet, classification_code, "
            "classification_libelle, typologie)",
            "URL du document PDF original (url, content_type)",
        ],
        frequence_maj=FREQUENCE_MAJ,
        source_label="Mégalis Bretagne",
        url_source="https://data-publication.megalis.bretagne.bzh/",
    )


def moissonner(
    code_insee: str,
    commune: dict,
    *,
    dossier_sortie: str,
    mode_producer: str = "source",
    contact_email_commune: str | None = None,
    session_http=None,
    description_commune: dict | None = None,
) -> ResultatConnecteur:
    if commune.get("code_region") != CODE_REGION_BRETAGNE:
        return ResultatConnecteur(
            StatutConnecteur.HORS_COUVERTURE,
            message="Mégalis Bretagne ne couvre que les communes de la région Bretagne.",
        )

    session_http = session_http or session

    try:
        siren = resoudre_siren_commune(code_insee, session_http=session_http)
    except Exception as e:  # noqa: BLE001
        return ResultatConnecteur(StatutConnecteur.ECHEC, message=str(e))

    actes: list[dict] = []
    page_suivante: str | None = None
    try:
        for _ in range(PLAFOND_PAGES_DEFAUT):
            params = {"siren": siren}
            if page_suivante:
                params["page_suivante"] = page_suivante
            reponse = session_http.get(_MEGALIS_API, params=params, timeout=30)
            reponse.raise_for_status()
            donnees = reponse.json()
            resultats = donnees.get("resultats", [])
            actes.extend(_simplifier_acte(a) for a in resultats)
            nb_resultats = donnees.get("nb_resultats", len(actes))
            page_suivante = donnees.get("page_suivante")
            if not resultats or not page_suivante or len(actes) >= nb_resultats:
                break
    except Exception as e:  # noqa: BLE001
        return ResultatConnecteur(StatutConnecteur.ECHEC, message=str(e))

    if not actes:
        return ResultatConnecteur(StatutConnecteur.VIDE)

    local_id = local_id_jdd(CLE, code_insee)
    nom_fichier = f"deliberations_{code_insee}.csv"
    chemin = os.path.join(dossier_sortie, nom_fichier)
    os.makedirs(dossier_sortie, exist_ok=True)
    with open(chemin, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=_CHAMPS_ACTE, delimiter=";")
        writer.writeheader()
        writer.writerows(actes)

    producer = organisations.resoudre_producer(
        CLE, mode_producer, commune, description_commune=description_commune,
    )
    contacts = contacts_pour_producer(CLE, producer, commune, email_commune=contact_email_commune)

    media = media_filtre(
        local_id, nom_fichier, commune["nom"],
        caption=f"Index des délibérations - {commune['nom']} (CSV)",
    )

    try:
        licence = licences.licence_pour_jdd(CLE)
    except licences.LicenceInconnueError as e:
        return ResultatConnecteur(StatutConnecteur.ECHEC, message=str(e))

    rudi_metadata = construire_rudi_metadata(
        local_id=local_id,
        titre=f"{TITRE} - {commune['nom']} ({code_insee})",
        synopsis=SYNOPSIS_PATRON.format(commune=commune["nom"], code_insee=code_insee)[:150],
        description=_description_enrichie(commune, code_insee),
        theme=THEME,
        keywords=[
            "délibérations", "conseil municipal", "actes administratifs",
            commune["nom"], "Mégalis Bretagne",
        ],
        producer=producer,
        url_source=f"{_MEGALIS_API}?siren={siren}",
        url_fiche="https://data-publication.megalis.bretagne.bzh/",
        date_source=_date_plus_recente_actes(actes),
        medias=[media],
        contacts_source=contacts,
        geography=geography_pour_commune(commune),
        licence=licence,
    )

    return ResultatConnecteur(
        StatutConnecteur.PUBLIABLE, rudi_metadata=rudi_metadata, fichiers_filtres=[chemin],
    )


__all__ = [
    "CLE", "CODE_REGION_BRETAGNE", "DESCRIPTION_PATRON", "FREQUENCE_MAJ",
    "PLAFOND_PAGES_DEFAUT", "SYNOPSIS_PATRON", "THEME", "TITRE", "moissonner",
]
