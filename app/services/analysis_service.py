"""Service métier : cycle de vie d'une analyse, utilisé par l'API et le web.

Import des documents → analyse (orchestrateur) → registre proposé →
validation humaine → registre final, avec persistance SQLite à chaque étape.
"""

import uuid
from datetime import datetime, timezone

from app.agents.base import AgentError
from app.models.audit import AuditEntry
from app.models.risk import Risk
from app.orchestration.workflow import Orchestrator, AnalysisState
from app.services.document_parser import load_documents
from app.services.storage import Storage


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def risk_public(risk: Risk) -> dict:
    """Représentation JSON d'un risque incluant score et sources calculés."""
    data = risk.model_dump(mode="json")
    data["score"] = risk.score
    data["sources"] = risk.sources
    return data


class AnalysisService:
    """Opérations métier sur les analyses (persistées en SQLite)."""

    def __init__(self, storage: Storage | None = None) -> None:
        self.storage = storage or Storage()
        self.orchestrator = Orchestrator()

    # ------------------------------------------------------------------
    # Cycle de vie
    # ------------------------------------------------------------------

    def create(self, files: list[tuple[str, bytes]]) -> AnalysisState:
        """Importe les documents et crée une analyse (étape 1 uniquement)."""
        documents = load_documents(files)
        if not documents:
            raise AgentError("aucun document importé")

        now = _now()
        state = AnalysisState(
            id=f"ANALYSIS-{uuid.uuid4().hex[:8]}",
            documents=documents,
            created_at=now,
            updated_at=now,
        )
        state.audit.append(
            AuditEntry(
                timestamp=now,
                agent="orchestrator",
                action="DOCUMENT_IMPORT",
                input=[doc["id"] for doc in documents],
                output=f"{len(documents)} document(s) importé(s)",
                source=[doc["id"] for doc in documents],
            )
        )
        self.storage.save_analysis(self.orchestrator.to_dict(state))
        return state

    def run(self, analysis_id: str, llm=None) -> AnalysisState:
        """Lance (ou relance) l'analyse complète d'une analyse importée.

        L'état est persisté après chaque étape : l'interface affiche
        l'avancement en temps réel (barre de progression).
        """
        state = self.get(analysis_id)

        def _save(partial: AnalysisState) -> None:
            self.storage.save_analysis(self.orchestrator.to_dict(partial))

        analysis = self.orchestrator.run(
            state.documents, analysis_id=analysis_id, llm=llm, progress=_save
        )
        self.storage.save_analysis(self.orchestrator.to_dict(analysis))
        return analysis

    def get(self, analysis_id: str) -> AnalysisState:
        data = self.storage.load_analysis(analysis_id)
        if data is None:
            raise KeyError(f"analyse inconnue : {analysis_id}")
        return self.orchestrator.from_dict(data)

    def list_summaries(self) -> list[dict]:
        return self.storage.list_analyses()

    def delete(self, analysis_id: str) -> None:
        self.storage.delete_analysis(analysis_id)

    def validate(
        self,
        analysis_id: str,
        risk_id: str,
        action: str,
        *,
        user: str = "analyste-demo",
        comment: str | None = None,
        probability: int | None = None,
        impact: int | None = None,
        justification: str | None = None,
        recommended_measures: str | None = None,
        existing_measures: str | None = None,
        residual_risk: str | None = None,
        owner: str | None = None,
    ) -> AnalysisState:
        state = self.get(analysis_id)
        state = self.orchestrator.human_validate(
            state,
            risk_id,
            action,
            user=user,
            comment=comment,
            probability=probability,
            impact=impact,
            justification=justification,
            recommended_measures=recommended_measures,
            existing_measures=existing_measures,
            residual_risk=residual_risk,
            owner=owner,
        )
        self.storage.save_analysis(self.orchestrator.to_dict(state))
        if state.status == Orchestrator.stages[-1].value:
            self.storage.save_register(analysis_id, self.export(analysis_id))
        return state

    # ------------------------------------------------------------------
    # Sorties
    # ------------------------------------------------------------------

    def proposed_register(self, analysis_id: str) -> dict:
        state = self.get(analysis_id)
        return {
            "analysis_id": analysis_id,
            "status": state.status,
            "critic_report": (
                state.critic_report.model_dump(mode="json")
                if state.critic_report
                else None
            ),
            "risks": [risk_public(risk) for risk in state.risks],
        }

    def get_risk(self, analysis_id: str, risk_id: str) -> dict:
        state = self.get(analysis_id)
        for risk in state.risks:
            if risk.id == risk_id:
                return risk_public(risk)
        raise KeyError(f"risque inconnu : {risk_id}")

    def audit(self, analysis_id: str) -> list[dict]:
        state = self.get(analysis_id)
        return [entry.model_dump(mode="json") for entry in state.audit]

    def export(self, analysis_id: str) -> dict:
        """Registre (final si possible) + journal d'audit + état."""
        state = self.get(analysis_id)
        return {
            "analysis_id": analysis_id,
            "status": state.status,
            "exported_at": state.updated_at,
            "documents": [doc["id"] for doc in state.documents],
            "critic_report": (
                state.critic_report.model_dump(mode="json")
                if state.critic_report
                else None
            ),
            "register": [risk_public(risk) for risk in state.risks],
            "audit_log": [entry.model_dump(mode="json") for entry in state.audit],
        }


__all__ = ["AnalysisService"]