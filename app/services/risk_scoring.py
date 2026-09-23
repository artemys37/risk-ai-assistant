"""Service de cotation des risques — matrice explicite et reproductible.

Risque = Probabilité × Impact
- Probabilité : 1 (Très faible) à 5 (Très élevée)
- Impact     : 1 (Très faible) à 5 (Très élevé)
- Score      : 1 à 25

Aucun score ne peut être produit sans justification (contrôlé au niveau
du modèle RiskAssessment).
"""

from app.models.risk import RiskAssessment

MIN_SCALE = 1
MAX_SCALE = 5
MAX_SCORE = MAX_SCALE * MAX_SCALE  # 25

PROBABILITY_LABELS = {
    1: "Très faible",
    2: "Faible",
    3: "Moyenne",
    4: "Élevée",
    5: "Très élevée",
}

IMPACT_LABELS = {
    1: "Très faible",
    2: "Faible",
    3: "Moyen",
    4: "Élevé",
    5: "Très élevé",
}


class ScaleError(ValueError):
    """Levement levé si probabilité/impact hors échelle 1-5."""


def calculate_score(probability: int, impact: int) -> int:
    """Calcule le score de risque. Reproductible et purement déterministe."""
    for name, value in (("probabilité", probability), ("impact", impact)):
        if not isinstance(value, int) or not (MIN_SCALE <= value <= MAX_SCALE):
            raise ScaleError(
                f"{name} hors échelle : {value!r} (attendu entier {MIN_SCALE}-{MAX_SCALE})"
            )
    return probability * impact


def build_assessment(
    probability: int,
    impact: int,
    justification: str,
    source: list[str] | None = None,
) -> RiskAssessment:
    """Construit une évaluation validée avec score calculé."""
    return RiskAssessment(
        probability=probability,
        impact=impact,
        justification=justification,
        score=calculate_score(probability, impact),
        source=source or [],
    )


def score_label(score: int) -> str:
    """Libellé indicatif du score pour l'affichage (tranche explicite)."""
    if score <= 4:
        return "Faible"
    if score <= 9:
        return "Modéré"
    if score <= 14:
        return "Important"
    if score <= 19:
        return "Élevé"
    return "Critique"
