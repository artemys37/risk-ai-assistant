"""Base commune des agents : appels LLM JSON, retry, confiance estimée.

Principes transverses :
- le contenu des documents est toujours injecté comme donnée NON FIABLE,
  jamais comme instruction ;
- chaque sortie est validée par Pydantic ;
- le niveau de confiance est ESTIMÉ (critères : sources + nature de
  l'affirmation), jamais présenté comme une probabilité statistique ;
- en cas de réponse LLM invalide, une seule tentative de correction
  est réalisée avant d'échouer.
"""

import json

from app.models.base import (
    NOT_DOCUMENTED,
    ConfidenceLevel,
    EvidenceType,
    HumanValidation,
)
from app.services.llm import LLMClient, LLMError, extract_json
from app.services.source_tracker import SourceTracker


class AgentError(Exception):
    """Erreur d'un agent (LLM, validation, données insuffisantes)."""


def _as_list(value: object) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        return [item for item in value if isinstance(item, str) and item]
    return []


class AgentBase:
    """Fournit les helpers communs à tous les agents."""

    agent_name = "base-agent"
    # Nature par défaut si le LLM ne la déclare pas : HYPOTHÈSE (prudence).
    default_evidence_type = EvidenceType.HYPOTHESIS

    def _get_llm(self, llm: LLMClient | None) -> LLMClient:
        return llm or LLMClient()

    def _json_completion(self, llm: LLMClient, system: str, user: str) -> object:
        """Appelle le LLM et retourne le JSON parsé (objet ou tableau)."""
        text = llm.complete(system, user)
        obj = extract_json(text)
        if obj is not None:
            return obj
        # Une seule tentative de réparation.
        correction = llm.complete(
            system,
            f"{user}\n\nTa réponse précédente n'était pas du JSON valide. "
            f"Réponds uniquement avec un JSON valide conforme au schéma demandé.",
        )
        obj = extract_json(correction)
        if obj is None:
            raise AgentError(
                f"{self.agent_name}: réponse LLM sans JSON exploitable. "
                "Vérifier LLM_MODEL/LLM_API_KEY ou relancer."
            )
        return obj

    # ------------------------------------------------------------------
    # Helper de construction des objets métier
    # ------------------------------------------------------------------

    def _sources(self, item: dict) -> list[str]:
        return _as_list(item.get("source") or item.get("sources"))

    def _evidence_type(self, item: dict) -> EvidenceType:
        raw = str(item.get("evidence_type", "")).strip().upper()
        for candidate in EvidenceType:
            if raw == candidate.value.upper() or raw == candidate.name:
                return candidate  # type: ignore[return-value]
        return self.default_evidence_type

    def _estimate_confidence(self, sources: list[str], evidence_type: EvidenceType) -> ConfidenceLevel:
        return SourceTracker.estimate_confidence(sources, evidence_type.value)

    def _field(self, item: dict, name: str, default: str = NOT_DOCUMENTED) -> str:
        value = item.get(name)
        if isinstance(value, str) and value.strip():
            return value.strip()
        return default

    @staticmethod
    def _dump(payload: object) -> str:
        return json.dumps(payload, ensure_ascii=False, indent=2)

    # ------------------------------------------------------------------
    # Journalisation minimale (sera enrichie par l'audit log Sprint 4)
    # ------------------------------------------------------------------

    def log(self, action: str, input_: object, output: object) -> dict:
        return {
            "timestamp": None,  # horodatage réel au Sprint 4
            "agent": self.agent_name,
            "action": action,
            "input": input_ if isinstance(input_, (str, list, dict)) else repr(input_),
            "output": output if isinstance(output, (str, list, dict)) else repr(output),
            "human_validation": HumanValidation.PENDING.value,
        }


__all__ = [
    "AgentBase",
    "AgentError",
    "LLMError",
    "_as_list",
]