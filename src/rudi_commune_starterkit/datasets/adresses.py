"""JDD « Voies et adresses » — Base Adresse Nationale (BAN), fichier CSV départemental.

Confirmé le 2026-11-07 : ``adresse.data.gouv.fr/data/ban/adresses/latest/csv/
adresses-{dep}.csv.gz`` (17 Mo gzippé pour l'Ille-et-Vilaine) contient **toutes** les
adresses du département, jamais une seule commune — fichier national/départemental à
filtrer localement, jamais pré-filtré par la source : **FILE copie**, pas FILE hybride
(voir le plan, § Modèle de média). Colonne de filtrage : ``code_insee`` (nom déjà présent
dans l'en-tête, délimiteur ``;``).

En-têtes déjà lisibles (``nom_voie``, ``code_postal``, ``nom_commune``...) — republiés
tels quels, aucune traduction nécessaire.

Le fichier départemental est mis en cache (``rudi_harvest_toolkit.download_cache``) pour
ne pas le retélécharger à chaque run tant qu'il n'a pas changé.
"""

from __future__ import annotations

import csv
import os

from rudi_harvest_toolkit.download_cache import telecharger
from rudi_harvest_toolkit.http import session
from rudi_harvest_toolkit.pivot import construire_rudi_metadata, media_filtre
from rudi_harvest_toolkit.tabular import lire_csv_filtre

from .. import organisations
from ..resultat import ResultatConnecteur, StatutConnecteur
from ._commun import contacts_pour_producer, local_id_jdd

CLE = organisations.ADRESSES
THEME = "location"
TITRE = "Voies et adresses"
SYNOPSIS_PATRON = "Adresses de la commune de {commune} ({code_insee}) - Base Adresse Nationale"
DESCRIPTION_PATRON = (
    "Voies et adresses de la commune de {commune} ({code_insee}), extraites du fichier "
    "départemental de la Base Adresse Nationale (BAN), sourcée auprès du consortium "
    "IGN / La Poste / DINUM (sous l'égide d'Etalab). Instantané figé à la date de moisson."
)
FREQUENCE_MAJ = "mensuelle"

_BAN_URL_PATRON = "https://adresse.data.gouv.fr/data/ban/adresses/latest/csv/adresses-{dep}.csv.gz"


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
    session_http = session_http or session
    dep = commune.get("code_departement") or code_insee[:2]
    url_dep = _BAN_URL_PATRON.format(dep=dep)

    try:
        chemin_cache = telecharger(
            url_dep, dossier=os.path.join(dossier_sortie, ".cache_ban"),
            session_http=session_http,
        )
        lignes, entetes = lire_csv_filtre(chemin_cache, "code_insee", code_insee)
    except Exception as e:  # noqa: BLE001
        return ResultatConnecteur(StatutConnecteur.ECHEC, message=str(e))

    if not lignes:
        return ResultatConnecteur(StatutConnecteur.VIDE)

    local_id = local_id_jdd(CLE, code_insee)
    nom_fichier = f"adresses_{code_insee}.csv"
    chemin = os.path.join(dossier_sortie, nom_fichier)
    os.makedirs(dossier_sortie, exist_ok=True)
    with open(chemin, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=entetes, delimiter=";")
        writer.writeheader()
        writer.writerows(lignes)

    producer = organisations.resoudre_producer(
        CLE, mode_producer, commune, description_commune=description_commune,
    )
    contacts = contacts_pour_producer(CLE, producer, commune, email_commune=contact_email_commune)

    media = media_filtre(
        local_id, nom_fichier, commune["nom"],
        caption=f"Voies et adresses - {commune['nom']} (CSV)",
    )

    rudi_metadata = construire_rudi_metadata(
        local_id=local_id,
        titre=f"{TITRE} - {commune['nom']} ({code_insee})",
        synopsis=SYNOPSIS_PATRON.format(commune=commune["nom"], code_insee=code_insee)[:150],
        description=DESCRIPTION_PATRON.format(commune=commune["nom"], code_insee=code_insee),
        theme=THEME,
        keywords=["adresses", "voies", "BAN", commune["nom"], "IGN"],
        producer=producer,
        url_source=url_dep,
        url_fiche="https://adresse.data.gouv.fr/base-adresse-nationale",
        medias=[media],
        contacts_source=contacts,
    )

    return ResultatConnecteur(
        StatutConnecteur.PUBLIABLE, rudi_metadata=rudi_metadata, fichiers_filtres=[chemin],
    )


__all__ = ["CLE", "DESCRIPTION_PATRON", "FREQUENCE_MAJ", "SYNOPSIS_PATRON", "THEME", "TITRE", "moissonner"]
