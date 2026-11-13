"""Description réelle d'une commune (Wikipédia), avec repli explicite vers la phrase
générique déjà utilisée par ``organisations.organisation_commune()`` quand Wikipédia
échoue — jamais un simple « pas de résultat », pour que l'appelant sache ce qui a
réellement été publié.

Code neuf propre à ce socle (orchestration + repli), pas une brique générique : la
résolution Wikidata/Wikipédia elle-même vit dans
``rudi_harvest_toolkit.wikipedia.resumer_commune_wikipedia()``.
"""

from __future__ import annotations

from rudi_harvest_toolkit.rne import maire_actuel
from rudi_harvest_toolkit.wikipedia import resumer_commune_wikipedia

_LICENCE_CC_BY_SA = "https://creativecommons.org/licenses/by-sa/4.0/deed.fr"

# Limite constatée côté nœud RUDI (HTTP 400 « La description de l'organisation
# est trop longue ( > 800 caractères) »), pas documentée dans l'API — reproduite
# en conditions réelles sur Abilly (37001, intro Wikipédia + patrimoine → 1182
# caractères) via starterkit-tester le 2026-11-13.
_LONGUEUR_MAX_ORGANIZATION_SUMMARY = 800


def _tronquer_sur_mot(texte: str, longueur_max: int) -> str:
    """Tronque ``texte`` à ``longueur_max`` caractères sans couper un mot, suffixé
    par « … ». Ne coupe jamais l'attribution CC BY-SA (appelant : toujours sur la
    partie Wikipédia seule, avant concaténation avec l'attribution)."""
    if len(texte) <= longueur_max:
        return texte
    tronque = texte[: longueur_max - 1]
    dernier_espace = tronque.rfind(" ")
    if dernier_espace > 0:
        tronque = tronque[:dernier_espace]
    return tronque.rstrip(".,;: \n") + "…"


def _paragraphe_complementaire(
    code_insee: str, resume: dict, *, session_http, dossier_cache_rne: str | None,
) -> str | None:
    """Second paragraphe (maire/gentilé/superficie) complétant l'intro Wikipédia,
    souvent courte pour une petite commune (retour utilisateur sur Acigné, 192
    caractères — un intro réel et court n'est pas une ébauche, voir wikipedia.py).

    Le maire vient du RNE (``rudi_harvest_toolkit.rne``), **pas** de Wikidata (P6) :
    Wikidata reste affiché indéfiniment sans signal d'obsolescence après une élection
    non répercutée (constaté sur Acigné — dernière mise à jour Wikidata 2014, RNE à
    jour au 2026-03-20). Gentilé/superficie (Wikidata, déjà résolus par
    ``resumer_commune_wikipedia()``) restent omis s'ils sont absents — jamais devinés.
    Retourne ``None`` si aucune des trois informations n'est disponible (pas de
    paragraphe vide publié).
    """
    phrases = []
    maire = maire_actuel(code_insee, session_http=session_http, dossier_cache=dossier_cache_rne)
    if maire and maire.get("nom") and maire.get("prenom"):
        phrase = f"Le maire actuel est {maire['prenom']} {maire['nom']}"
        date_debut = maire.get("date_debut_fonction") or ""
        if len(date_debut) >= 4:
            phrase += f" (depuis {date_debut[:4]})"
        phrases.append(phrase + ".")
    gentile = resume.get("gentile")
    if gentile:
        phrases.append(f"Ses habitants sont appelés les {gentile}.")
    superficie_km2 = resume.get("superficie_km2")
    if superficie_km2:
        valeur_fr = f"{superficie_km2:.2f}".replace(".", ",")
        phrases.append(f"Sa superficie est de {valeur_fr} km².")
    return " ".join(phrases) if phrases else None


def construire_description_commune(
    commune: dict, *, session_http=None, dossier_cache: str | None = None,
    dossier_cache_rne: str | None = None,
) -> dict:
    """``{"organization_summary": str, "source": "wikipedia"|"repli_generique",
    "url": str|None}``.

    L'attribution CC BY-SA du texte Wikipédia est intégrée **dans** le texte publié
    (pas seulement via ``organization_url``, qui identifie l'organisation mais n'est
    pas une attribution du texte) — nomme explicitement la licence et son texte, pas
    seulement la source, comme l'exige CC BY-SA.

    Repli explicite sur la phrase générique déjà utilisée par
    ``organisations.organisation_commune()`` si Wikipédia échoue/est indisponible.
    ``source`` n'est pas un champ mort : ``cli.py`` l'utilise pour avertir quand le
    repli générique a été utilisé.
    """
    resume = resumer_commune_wikipedia(
        commune["code_insee"], session_http=session_http, dossier_cache=dossier_cache,
    )
    if resume:
        paragraphe2 = _paragraphe_complementaire(
            commune["code_insee"], resume,
            session_http=session_http, dossier_cache_rne=dossier_cache_rne,
        )
        texte = resume["summary"]
        if paragraphe2:
            texte += f"\n\n{paragraphe2}"
        attribution = (
            f"\n\nTexte issu de Wikipédia ({resume['url']}), sous licence CC BY-SA 4.0 "
            f"({_LICENCE_CC_BY_SA})."
        )
        # L'attribution CC BY-SA n'est jamais tronquée (obligation de licence) ; seul
        # le texte Wikipédia variable l'est, sur le budget restant.
        budget_texte = _LONGUEUR_MAX_ORGANIZATION_SUMMARY - len(attribution)
        texte = _tronquer_sur_mot(texte, budget_texte)
        texte += attribution
        return {"organization_summary": texte, "source": "wikipedia", "url": resume["url"]}
    return {
        "organization_summary": (
            f"Collectivité territoriale, commune de {commune['nom']}"
            f" ({commune.get('code_insee', '')})."
        ),
        "source": "repli_generique",
        "url": None,
    }


__all__ = ["construire_description_commune"]
