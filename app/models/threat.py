"""Modèle de données : menace identifiée par l'agent Menaces."""

from pydantic import BaseModel, Field

from app.models.base import ConfidenceLevel, EvidenceType

# Catégories STRIDE utilisées pour catégoriser les menaces.
STRIDE_CATEGORIES = (
    "Spoofing",
    "Tampering",
    "Repudiation",
    "Information Disclosure",
    "Denial of Service",
    "Elevation of Privilege",
)


class Threat(BaseModel):
    """Menace proposée par l'agent Menaces.

    Chaque menace doit être justifiée (rationale) et distinguée
    en fait documenté / inférence / hypothèse.
    """

    id: str = Field(pattern=r"^THR-\d{3}$", description="Identifiant unique THR-XXX")
    name: str = Field(min_length=1)
    description: str = Field(min_length=1)
    target_assets: list[str] = Field(
        min_length=1,
        description="Identifiants des actifs visés (ACT-XXX)",
    )
    rationale: str = Field(
        min_length=1,
        description="Justification de la pertinence de cette menace",
    )
    evidence: list[str] = Field(
        default_factory=list,
        description="Éléments de preuve / références documentaires",
    )
    stride_category: str | None = Field(
        default=None,
        description="Catégorie STRIDE si applicable",
    )
    source: list[str] = Field(default_factory=list)
    confidence: ConfidenceLevel = ConfidenceLevel.MEDIUM
    evidence_type: EvidenceType = EvidenceType.HYPOTHESIS
