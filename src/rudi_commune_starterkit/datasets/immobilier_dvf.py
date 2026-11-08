"""JDD « Valeurs foncières (DVF) » — archive géolocalisée par département, plusieurs années.

Confirmé le 2026-11-07 : ``files.data.gouv.fr/geo-dvf/latest/csv/{année}/departements/
{dep}.csv.gz`` (motif publié et stable de l'écosystème DVF, pas une URL de ressource
dataset — exception assumée, voir le plan) ; **délimiteur virgule**, pas point-virgule
(contrairement à la plupart des autres sources de ce socle). Millésimes 2021 à 2025
disponibles au moment de la vérification, 2020 et antérieurs en `404` propre — la
disponibilité réelle est donc **sondée à l'exécution** (``HEAD``) plutôt que supposée sur
une liste d'années figée en dur, pour ne jamais casser silencieusement quand une nouvelle
année est publiée ou qu'une ancienne est retirée.

**Harmonisation de schéma explicite avant concaténation** (point de vigilance identifié
par le plan, pas une hypothèse) : le header réel s'est révélé identique sur les 3 millésimes
testés (2021/2023/2025), mais le code ne le suppose pas pour autant — l'en-tête final est
l'**union** des colonnes vues sur les millésimes effectivement récupérés, une colonne
absente d'un millésime donné restant vide pour les lignes de cette année plutôt que de
faire planter l'écriture ou de perdre une colonne apparue plus tard.
"""

from __future__ import annotations

import csv
import datetime
import os

from rudi_harvest_toolkit.download_cache import telecharger
from rudi_harvest_toolkit.http import session
from rudi_harvest_toolkit.pivot import construire_rudi_metadata, media_filtre
from rudi_harvest_toolkit.tabular import lire_csv_filtre

from .. import organisations
from ..resultat import ResultatConnecteur, StatutConnecteur
from ._commun import contacts_pour_producer, local_id_jdd

CLE = organisations.IMMOBILIER_DVF
THEME = "housing"
TITRE = "Valeurs foncières (DVF)"
SYNOPSIS_PATRON = "Transactions immobilières (DVF) à {commune} ({code_insee})"
DESCRIPTION_PATRON = (
    "Valeurs foncières (DVF) des transactions immobilières réalisées sur la commune de "
    "{commune} ({code_insee}), sur les millésimes disponibles ({annees}), sourcées auprès "
    "de la DGFiP. Chaque ligne porte le millésime d'archive dont elle provient "
    "(colonne 'annee_millesime_dvf', ajoutée à la concaténation, absente de la source)."
)
FREQUENCE_MAJ = "annuelle"

_DVF_URL_PATRON = "https://files.data.gouv.fr/geo-dvf/latest/csv/{annee}/departements/{dep}.csv.gz"
_COLONNE_COMMUNE = "code_commune"
NB_ANNEES_A_SONDER = 6
_COLONNE_MILLESIME = "annee_millesime_dvf"


def _annees_candidates() -> list[int]:
    annee_courante = datetime.date.today().year
    return list(range(annee_courante - 1, annee_courante - 1 - NB_ANNEES_A_SONDER, -1))


def moissonner(
    code_insee: str,
    commune: dict,
    *,
    dossier_sortie: str,
    mode_producer: str = "source",
    contact_email_commune: str | None = None,
    session_http=None,
) -> ResultatConnecteur:
    session_http = session_http or session
    dep = commune.get("code_departement") or code_insee[:2]

    entetes_union: list[str] = []
    vus: set[str] = set()
    lignes_combinees: list[dict] = []
    annees_trouvees: list[int] = []

    for annee in _annees_candidates():
        url = _DVF_URL_PATRON.format(annee=annee, dep=dep)
        try:
            tete = session_http.head(url, allow_redirects=True, timeout=15)
        except Exception as e:  # noqa: BLE001
            return ResultatConnecteur(StatutConnecteur.ECHEC, message=str(e))
        if tete.status_code == 404:
            continue
        try:
            tete.raise_for_status()
            chemin_cache = telecharger(
                url, dossier=os.path.join(dossier_sortie, ".cache_dvf"),
                session_http=session_http,
            )
            lignes, entetes_annee = lire_csv_filtre(
                chemin_cache, _COLONNE_COMMUNE, code_insee, delimiter=",",
            )
        except Exception as e:  # noqa: BLE001
            return ResultatConnecteur(StatutConnecteur.ECHEC, message=str(e))

        for colonne in entetes_annee:
            if colonne not in vus:
                vus.add(colonne)
                entetes_union.append(colonne)
        for ligne in lignes:
            ligne[_COLONNE_MILLESIME] = str(annee)
            lignes_combinees.append(ligne)
        annees_trouvees.append(annee)

    if not lignes_combinees:
        return ResultatConnecteur(StatutConnecteur.VIDE)

    entetes_union.append(_COLONNE_MILLESIME)

    local_id = local_id_jdd(CLE, code_insee)
    nom_fichier = f"immobilier_dvf_{code_insee}.csv"
    chemin = os.path.join(dossier_sortie, nom_fichier)
    os.makedirs(dossier_sortie, exist_ok=True)
    with open(chemin, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=entetes_union, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(lignes_combinees)

    producer = organisations.resoudre_producer(CLE, mode_producer, commune)
    contacts = contacts_pour_producer(CLE, producer, commune, email_commune=contact_email_commune)

    media = media_filtre(
        local_id, nom_fichier, commune["nom"],
        caption=f"Valeurs foncières (DVF), {min(annees_trouvees)}-{max(annees_trouvees)} - {commune['nom']} (CSV)",
    )

    annees_texte = ", ".join(str(a) for a in sorted(annees_trouvees))
    rudi_metadata = construire_rudi_metadata(
        local_id=local_id,
        titre=f"{TITRE} - {commune['nom']} ({code_insee})",
        synopsis=SYNOPSIS_PATRON.format(commune=commune["nom"], code_insee=code_insee)[:150],
        description=DESCRIPTION_PATRON.format(
            commune=commune["nom"], code_insee=code_insee, annees=annees_texte,
        ),
        theme=THEME,
        keywords=["DVF", "valeurs foncières", "immobilier", commune["nom"], "DGFiP"],
        producer=producer,
        url_source=_DVF_URL_PATRON.format(annee=max(annees_trouvees), dep=dep),
        url_fiche="https://www.data.gouv.fr/fr/datasets/demandes-de-valeurs-foncieres/",
        medias=[media],
        contacts_source=contacts,
    )

    return ResultatConnecteur(
        StatutConnecteur.PUBLIABLE, rudi_metadata=rudi_metadata, fichiers_filtres=[chemin],
    )


__all__ = [
    "CLE", "DESCRIPTION_PATRON", "FREQUENCE_MAJ", "NB_ANNEES_A_SONDER",
    "SYNOPSIS_PATRON", "THEME", "TITRE", "moissonner",
]
