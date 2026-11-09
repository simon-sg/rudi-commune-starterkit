"""Description réelle d'une commune (Wikipédia), avec repli explicite vers la phrase
générique déjà utilisée par ``organisations.organisation_commune()`` quand Wikipédia
échoue — jamais un simple « pas de résultat », pour que l'appelant sache ce qui a
réellement été publié.

Code neuf propre à ce socle (orchestration + repli), pas une brique générique : la
résolution Wikidata/Wikipédia elle-même vit dans
``rudi_harvest_toolkit.wikipedia.resumer_commune_wikipedia()``.
"""

from __future__ import annotations

from rudi_harvest_toolkit.wikipedia import resumer_commune_wikipedia

_LICENCE_CC_BY_SA = "https://creativecommons.org/licenses/by-sa/4.0/deed.fr"


def construire_description_commune(
    commune: dict, *, session_http=None, dossier_cache: str | None = None,
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
        texte = (
            f"{resume['summary']}\n\n"
            f"Texte issu de Wikipédia ({resume['url']}), sous licence CC BY-SA 4.0 "
            f"({_LICENCE_CC_BY_SA})."
        )
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
