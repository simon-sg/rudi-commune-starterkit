"""Point d'entrée unique pour la licence RUDI de chaque JDD — jamais de repli silencieux
vers Etalab 2.0. Voir le plan (Axe 4) : aucune licence n'est devinée ; une licence non
confirmée pour un JDD lève :class:`LicenceInconnueError` plutôt que d'être absorbée.

Les modules branchés sur ``get_dataset_metadata()`` (``elus``, ``elections``,
``marches_publics``) passent leur licence dynamique (résolue depuis la fiche
data.gouv.fr via ``rudi_harvest_toolkit.pivot.construire_licence()`` +
``LICENCES_DATAGOUV_CONNUES``) ; les 10 autres modules n'ont que la table curée
ci-dessous.
"""

from __future__ import annotations

from . import organisations

_URI_ETALAB_2_0 = "https://www.etalab.gouv.fr/licence-ouverte-open-licence"
_URI_LICENCE_RNE = "https://inpi.fr/sites/default/files/Licence%20donn%C3%A9es%20RNE_2024_0.pdf"

_LICENCE_ETALAB_2_0 = {
    "licence_type": "STANDARD", "licence_label": "etalab-2.0", "licence_uri": _URI_ETALAB_2_0,
}


class LicenceInconnueError(ValueError):
    """Levée quand ni une licence dynamique (source data.gouv) ni une licence curée
    n'existent pour ce JDD — jamais de repli silencieux etalab-2.0."""


def _licence_mixte_sirene_rne() -> dict:
    """entreprises/associations : mélange SIRENE (Licence Ouverte 2.0) + RNE/INPI
    (« Licence données RNE 2024 ») — CUSTOM avec les DEUX URI dans le texte du label
    (une seule URI ne couvrirait que la moitié du périmètre annoncé, fragile face à un
    juriste). La correspondance champ -> licence est publiée dans la description riche
    du JDD (Axe 3), pas seulement dans ce label.
    """
    return {
        "licence_type": "CUSTOM",
        "custom_licence_label": [{
            "lang": "fr",
            "text": (
                f"Licence Ouverte 2.0 (SIRENE/INSEE, {_URI_ETALAB_2_0}) pour les champs "
                "d'identification de l'entreprise, Licence données RNE 2024 (INPI, "
                f"{_URI_LICENCE_RNE}) pour les champs issus du Registre National des "
                "Entreprises — la correspondance champ -> licence est publiée dans la "
                "description riche du JDD, pas seulement dans ce label."
            ),
        }],
        "custom_licence_uri": _URI_LICENCE_RNE,
    }


# Les 13 clés de registre.lister_modules() doivent toutes être présentes (vérifié par
# test de complétude dans test_licences.py) — PAS les clés de organisations.ORGANISATIONS,
# qui contient ENERGIE (sans module) et n'a pas DELIBERATIONS.
LICENCES_CUREES: dict[str, dict] = {
    # elus/elections : repli curé, utile seulement si le chemin dynamique (lov2 déjà
    # confirmé sur les deux datasets en production) devient indisponible, ou pour un
    # test sans mock "license"/"page".
    organisations.ELUS: dict(_LICENCE_ETALAB_2_0),
    organisations.ELECTIONS: dict(_LICENCE_ETALAB_2_0),
    # deliberations : licence_uri pointe vers la LICENCE elle-même (Etalab 2.0), jamais
    # vers le PDF de la note Mégalis 2021 qui justifie ce choix (documentée dans la
    # description du module, pas ici).
    organisations.DELIBERATIONS: dict(_LICENCE_ETALAB_2_0),
    # entreprises/associations : CUSTOM, mention explicite du mélange SIRENE + RNE/INPI.
    organisations.ENTREPRISES: _licence_mixte_sirene_rne(),
    organisations.ASSOCIATIONS: _licence_mixte_sirene_rne(),
    organisations.BUDGET: dict(_LICENCE_ETALAB_2_0),
    organisations.EAU_POTABLE: dict(_LICENCE_ETALAB_2_0),
    organisations.ETABLISSEMENTS_SCOLAIRES: dict(_LICENCE_ETALAB_2_0),
    organisations.ADRESSES: dict(_LICENCE_ETALAB_2_0),
    organisations.IRVE: dict(_LICENCE_ETALAB_2_0),
    organisations.POPULATION: dict(_LICENCE_ETALAB_2_0),
    # marches_publics : lov2 confirmé directement sur le dataset Colin Maudry (source
    # de remplacement, voir Axe 4) — repli curé utile pour les tests, le chemin
    # dynamique le masque en production.
    organisations.MARCHES_PUBLICS: dict(_LICENCE_ETALAB_2_0),
    organisations.IMMOBILIER_DVF: dict(_LICENCE_ETALAB_2_0),
}


def licence_pour_jdd(cle_jdd: str, *, licence_dynamique: dict | None = None) -> dict:
    """Point d'entrée unique : priorité à la licence dynamique (passée explicitement
    par l'appelant data.gouv, résolue via ``construire_licence()`` + le slug source),
    sinon la table curée, sinon :class:`LicenceInconnueError`."""
    if licence_dynamique is not None:
        return licence_dynamique
    try:
        return dict(LICENCES_CUREES[cle_jdd])
    except KeyError:
        raise LicenceInconnueError(
            f"Licence non confirmée pour {cle_jdd!r} — voir BACKLOG.md § licences."
        ) from None


__all__ = ["LICENCES_CUREES", "LicenceInconnueError", "licence_pour_jdd"]
