"""Modèles de données : scénarios de risque, évaluation, risque, critique."""

from enum import Enum

from pydantic import BaseModel, Field, model_validator

from app.models.base import PENDING, ConfidenceLevel, EvidenceType

PROBABILITY_SCALE = "1=Très faible, 2=Faible, 3=Moyenne, 4=Élevée, 5=Très élevée"
IMPACT_SCALE = "1=Très faible, 2=Faible, 3=Moyen, 4=Élevé, 5=Très élevé"


class RiskStatus(str, Enum):
    """Cycle de vie d'un risque — distingue clairement proposition IA
    et décision humaine."""

    PROPOSED_BY_AI = "PROPOSÉ PAR IA"
    VALIDATED_BY_HUMAN = "VALIDÉ PAR HUMAIN"
    MODIFIED_BY_HUMAN = "MODIFIÉ PAR HUMAIN"
    REJECTED_BY_HUMAN = "REJETÉ PAR HUMAIN"


class CriticStatus(str, Enum):
    """Verdict de l'agent critique."""

    PASS = "PASS"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"
    REJECT = "REJECT"


class RiskScenario(BaseModel):
    """Scénario de risque : Actif + Menace + Vulnérabilité + Contexte.

    Doit être compréhensible par un analyste sans lecture du code.
    """

    id: str = Field(pattern=r"^RSK-\d{3}$", description="Identifiant unique RSK-XXX")
    description: str = Field(
        min_length=1,
        description="Phrase narrative du scénario de risque",
    )
    threat_actor: str = Field(
        min_length=1,
        description="Acteur / source de menace (ex. attaquant externe)",
    )
    feared_event: str = Field(min_length=1, description="Événement redouté")
    asset_id: str = Field(pattern=r"^ACT-\d{3}$")
    threat_id: str = Field(pattern=r"^THR-\d{3}$")
    vulnerability_id: str = Field(pattern=r"^VUL-\d{3}$")
    consequences: list[str] = Field(min_length=1)
    evidence: list[str] = Field(default_factory=list)
    hypotheses: list[str] = Field(
        default_factory=list,
        description="Hypothèses explicitement déclarées (jamais présentées comme des faits)",
    )
    source: list[str] = Field(default_factory=list)
    confidence: ConfidenceLevel = ConfidenceLevel.MEDIUM
    evidence_type: EvidenceType = EvidenceType.HYPOTHESIS


class RiskAssessment(BaseModel):
    """Évaluation Probabilité × Impact.

    Le score est TOUJOURS calculé (jamais choisi arbitrairement)
    et ne peut pas exister sans justification.
    """

    probability: int = Field(ge=1, le=5, description=PROBABILITY_SCALE)
    impact: int = Field(ge=1, le=5, description=IMPACT_SCALE)
    justification: str = Field(
        min_length=10,
        description="Justification obligatoire du couple probabilité/impact",
    )
    score: int | None = Field(default=None, description="Score = Probabilité × Impact (1-25)")
    source: list[str] = Field(default_factory=list)
    confidence: ConfidenceLevel = ConfidenceLevel.MEDIUM

    @model_validator(mode="after")
    def _compute_score(self) -> "RiskAssessment":
        """Calcule systématiquement le score et valide la justification."""
        computed = self.probability * self.impact
        if self.score is not None and self.score != computed:
            raise ValueError(
                f"score incohérent : attendu {computed} "
                f"(probabilité {self.probability} × impact {self.impact}), "
                f"reçu {self.score}"
            )
        self.score = computed
        if not self.justification.strip():
            raise ValueError("une justification est obligatoire pour tout score")
        return self


class CriticReport(BaseModel):
    """Résultat de l'agent critique / vérification (obligatoire)."""

    status: CriticStatus
    issues: list[str] = Field(default_factory=list)
    missing_information: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    checked_ids: list[str] = Field(
        default_factory=list,
        description="Identifiants des éléments vérifiés",
    )
    source: list[str] = Field(default_factory=list)
    confidence: ConfidenceLevel = ConfidenceLevel.MEDIUM


class Risk(BaseModel):
    """Risque complet tel qu'il apparaît dans le registre.

    status commence toujours à PROPOSÉ PAR IA :
    un risque ne devient final que par décision humaine.
    """

    id: str = Field(pattern=r"^RSK-\d{3}$")
    scenario: RiskScenario
    assessment: RiskAssessment
    status: RiskStatus = RiskStatus.PROPOSED_BY_AI
    human_validation: str = PENDING
    analyst_comment: str | None = None
    existing_measures: str = "Non documenté"
    recommended_measures: str = "Non documenté"
    residual_risk: str | None = None
    owner: str = "Non documenté"
    created_by: str = Field(
        default="risk-assessment-agent",
        description="Agent ayant produit la proposition initiale",
    )
    created_at: str | None = None
    updated_at: str | None = None
    critic_report: CriticReport | None = None

    @property
    def sources(self) -> list[str]:
        """Sources agrégées : scénario + évaluation."""
        seen: dict[str, None] = {}
        for src in [*self.scenario.source, *self.assessment.source]:
            seen.setdefault(src, None)
        return list(seen)

    @property
    def score(self) -> int:
        return self.assessment.score  # type: ignore[return-value]
