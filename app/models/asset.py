"""Modèle de données : actif identifié à partir de la documentation."""

from enum import Enum

from pydantic import BaseModel, Field

from app.models.base import NOT_DOCUMENTED, ConfidenceLevel, EvidenceType


class AssetType(str, Enum):
    """Catégories d'actifs du périmètre d'analyse."""

    DATA = "données"
    APPLICATION = "application"
    SERVER = "serveur"
    CLIENT_WORKSTATION = "poste client"
    NETWORK_EQUIPMENT = "équipement réseau"
    ACCOUNT = "compte"
    SERVICE = "service"
    CLOUD_INFRASTRUCTURE = "infrastructure cloud"
    SECRET = "secret"
    CERTIFICATE = "certificat"
    INTERFACE = "interface"
    PHYSICAL_INFRASTRUCTURE = "infrastructure physique"
    OTHER = "autre"


class Asset(BaseModel):
    """Actif identifié par l'agent Actifs.

    Règle : si owner ou business_value est absent de la documentation,
    la valeur par défaut est NOT_DOCUMENTED — jamais inventée.
    """

    id: str = Field(pattern=r"^ACT-\d{3}$", description="Identifiant unique ACT-XXX")
    name: str = Field(min_length=1, description="Nom de l'actif")
    type: AssetType
    description: str = NOT_DOCUMENTED
    owner: str = NOT_DOCUMENTED
    business_value: str = NOT_DOCUMENTED
    source: list[str] = Field(
        default_factory=list,
        description="Références documentaires (ex. DOC-001, §2.1)",
    )
    confidence: ConfidenceLevel = ConfidenceLevel.MEDIUM
    evidence_type: EvidenceType = EvidenceType.INFERENCE
