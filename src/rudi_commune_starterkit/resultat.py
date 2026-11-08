"""Type de résultat uniforme retourné par chaque module ``datasets/<x>.py::moissonner()``.

Taxonomie décidée avec l'utilisateur (voir le plan, § Architecture finale) : un JDD
moissonné est toujours dans l'un de ces quatre états, jamais une exception qui remonterait
jusqu'à l'appelant pour un cas normal (hors couverture, 0 résultat).
"""

from __future__ import annotations

from dataclasses import dataclass, field


class StatutConnecteur:
    PUBLIABLE = "publiable"
    HORS_COUVERTURE = "hors_couverture"
    VIDE = "vide"
    ECHEC = "echec"

    TOUS = (PUBLIABLE, HORS_COUVERTURE, VIDE, ECHEC)


@dataclass
class ResultatConnecteur:
    """``statut`` pilote ce que l'appelant (``cli.py``) doit faire du résultat :

    - ``PUBLIABLE``  : ``rudi_metadata``/``fichiers_filtres`` prêts pour
      ``publier_si_configue()``.
    - ``HORS_COUVERTURE`` : ce JDD ne s'applique pas à cette commune (ex. délibérations
      hors Bretagne) — jamais une erreur, annoncé dès le diagnostic de l'assistant.
    - ``VIDE``       : la source a été interrogée avec succès mais ne contient aucune
      donnée pour cette commune — jamais une ressource vide publiée.
    - ``ECHEC``       : erreur réseau/parsing — ``message`` porte le détail.
    """

    statut: str
    rudi_metadata: dict | None = None
    fichiers_filtres: list = field(default_factory=list)
    message: str = ""

    def __post_init__(self) -> None:
        if self.statut not in StatutConnecteur.TOUS:
            raise ValueError(f"statut de connecteur inconnu : {self.statut!r}")
        if self.statut == StatutConnecteur.PUBLIABLE and self.rudi_metadata is None:
            raise ValueError("statut PUBLIABLE sans rudi_metadata")


__all__ = ["ResultatConnecteur", "StatutConnecteur"]
