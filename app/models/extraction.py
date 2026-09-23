"""Modèle de données : extraction documentaire produite par l'agent Documentation."""

from typing import Any

from pydantic import BaseModel, ConfigDict, model_validator

from app.models.base import NOT_DOCUMENTED

# Champs attendus dans la sortie structurée (schéma imposé au LLM).
EXTRACTION_FIELDS = (
    "system_name",
    "system_objective",
    "architecture",
    "components",
    "users",
    "data",
    "interfaces",
    "technologies",
    "dependencies",
    "data_flows",
    "constraints",
    "existing_security_controls",
    "missing_information",
)


class DocumentationExtraction(BaseModel):
    """Résultat d'analyse de l'agent Documentation.

    Règles :
    - aucune information absente n'est inventée → NOT_DOCUMENTED ;
    - `sources` mappe chaque champ à la liste des références (DOC-XXX §...);
    - les champs tolérés en plus (`extra="allow"`) seront vérifiés par
      l'agent critique (Sprint 4).
    """

    model_config = ConfigDict(extra="allow")

    system_name: str = NOT_DOCUMENTED
    system_objective: str = NOT_DOCUMENTED
    architecture: Any = NOT_DOCUMENTED
    components: list[Any] | str = NOT_DOCUMENTED
    users: list[Any] | str = NOT_DOCUMENTED
    data: list[Any] | str = NOT_DOCUMENTED
    interfaces: list[Any] | str = NOT_DOCUMENTED
    technologies: list[Any] | str = NOT_DOCUMENTED
    dependencies: list[Any] | str = NOT_DOCUMENTED
    data_flows: list[Any] | str = NOT_DOCUMENTED
    constraints: list[Any] | str = NOT_DOCUMENTED
    existing_security_controls: list[Any] | str = NOT_DOCUMENTED
    missing_information: list[Any] | str = NOT_DOCUMENTED
    sources: dict = NOT_DOCUMENTED

    @model_validator(mode="before")
    @classmethod
    def _normalize(cls, raw: Any) -> Any:
        """Normalise la sortie LLM : None / "" → NOT_DOCUMENTED,
        valeurs non-listes pour les champs de liste → liste à 1 élément."""
        if not isinstance(raw, dict):
            raise ValueError("l'extraction doit être un objet JSON")
        out = dict(raw)
        list_fields = {
            "components",
            "users",
            "data",
            "interfaces",
            "technologies",
            "dependencies",
            "data_flows",
            "constraints",
            "existing_security_controls",
            "missing_information",
        }
        for key, value in raw.items():
            if value is None or (isinstance(value, str) and not value.strip()):
                out[key] = NOT_DOCUMENTED
            elif key in list_fields and not isinstance(value, list):
                out[key] = [value] if value not in (NOT_DOCUMENTED,) else NOT_DOCUMENTED
        return out

    def field_sources(self, field: str) -> list[str]:
        """Références documentaires d'un champ — jamais inventées."""
        raw = self.sources.get(field) if isinstance(self.sources, dict) else None
        if isinstance(raw, str):
            return [raw]
        if isinstance(raw, list):
            return [str(item) for item in raw if item]
        return []

    def is_missing(self, field: str) -> bool:
        """True si le champ vaut literally NOT_DOCUMENTED."""
        return getattr(self, field) == NOT_DOCUMENTED