"""Types partagés entre tous les modèles du domaine d'analyse de risques."""

from enum import Enum

# Constante utilisée chaque fois qu'une information est absente de la
# documentation. Elle ne doit JAMAIS être remplacée par une valeur inventée.
NOT_DOCUMENTED = "Non documenté"

# Statut d'une validation humaine encore non réalisée.
PENDING = "PENDING"


class ConfidenceLevel(str, Enum):
    """Niveau de confiance ESTIMÉ d'un résultat d'agent.

    Il ne s'agit PAS d'une probabilité statistique : c'est un jugement
    argumenté basé sur la présence de sources, la complétude de la
    documentation et la nature de l'affirmation (fait / inférence / hypothèse).
    """

    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


class EvidenceType(str, Enum):
    """Nature épistémique d'une affirmation produite par un agent."""

    DOCUMENTED_FACT = "FAIT DOCUMENTÉ"
    INFERENCE = "INFERENCE"
    HYPOTHESIS = "HYPOTHÈSE"


class HumanValidation(str, Enum):
    """État de la validation humaine d'une proposition d'agent."""

    PENDING = "PENDING"
    ACCEPTED = "ACCEPTED"
    MODIFIED = "MODIFIED"
    REJECTED = "REJECTED"
