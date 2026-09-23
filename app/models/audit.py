"""Modèle de données : journal d'audit (traçabilité des décisions IA et humaines)."""

from pydantic import BaseModel, Field

from app.models.base import PENDING, ConfidenceLevel


class AuditEntry(BaseModel):
    """Entrée du journal d'audit.

    Chaque décision importante (proposition d'agent, validation ou
    modification humaine) produit une entrée horodatée.
    """

    timestamp: str = Field(description="ISO 8601 UTC")
    agent: str = Field(description="Nom de l'agent ou 'human-analyst'")
    action: str = Field(
        description="Type d'action (ex. THREAT_IDENTIFICATION, RISK_MODIFICATION)",
    )
    input: str | list | dict | None = None
    output: str | list | dict | None = None
    source: list[str] = Field(default_factory=list)
    confidence: ConfidenceLevel | float | None = None
    human_validation: str = PENDING
    user: str | None = Field(default=None, description="Analyste humain si applicable")
    comment: str | None = Field(default=None, description="Commentaire de l'analyste")
