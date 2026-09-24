"""Orchestrateur — gestion du workflow multi-agents.

Workflow global (11 étapes) :

 1. Import de la documentation
 2. Extraction documentaire          → documentation-agent
 3. Identification des actifs        → asset-agent
 4. Identification des menaces       → threat-agent
 5. Identification des vulnérabilités→ vulnerability-agent
 6. Construction des scénarios       → risk-scenario-agent
 7. Évaluation P × I                 → risk-assessment-agent
 8. Critique automatique             → critic-agent
 9. Registre des risques proposé     → statut PROPOSÉ PAR IA
10. Validation humaine               → ACCEPTER / MODIFIER / REJETER
11. Registre final                   → statut VALIDÉ / MODIFIÉ / REJETÉ PAR HUMAIN

Chaque étape est identifiée et journalisée (AuditEntry).
L'étape 10 est BLOQUANTE : aucun risque ne devient final sans l'humain.
"""

import uuid
from collections.abc import Callable
from datetime import datetime, timezone
from enum import Enum

from pydantic import BaseModel, Field

from app.agents.asset_agent import AssetAgent
from app.agents.critic_agent import CriticAgent
from app.agents.documentation_agent import DocumentationAgent
from app.agents.risk_assessment_agent import RiskAssessmentAgent
from app.agents.risk_scenario_agent import RiskScenarioAgent
from app.agents.threat_agent import ThreatAgent
from app.agents.vulnerability_agent import VulnerabilityAgent
from app.agents.base import AgentError
from app.models.asset import Asset
from app.models.audit import AuditEntry
from app.models.base import HumanValidation
from app.models.extraction import DocumentationExtraction
from app.models.risk import CriticReport, Risk, RiskStatus, RiskAssessment, RiskScenario
from app.models.threat import Threat
from app.models.vulnerability import Vulnerability
from app.services.risk_scoring import build_assessment


class WorkflowStage(str, Enum):
    """Étapes du workflow — utilisable tel quel dans l'interface."""

    IMPORT = "1. Import de la documentation"
    EXTRACTION = "2. Extraction documentaire"
    ASSETS = "3. Identification des actifs"
    THREATS = "4. Identification des menaces"
    VULNERABILITIES = "5. Identification des vulnérabilités"
    SCENARIOS = "6. Construction des scénarios"
    ASSESSMENT = "7. Évaluation Probabilité × Impact"
    CRITIQUE = "8. Critique automatique"
    PROPOSED_REGISTER = "9. Registre des risques proposé"
    HUMAN_VALIDATION = "10. Validation humaine"
    FINAL_REGISTER = "11. Registre final"


class AnalysisState(BaseModel):
    """État partagé du workflow, tel qu'il est persisté et présenté."""

    id: str = Field(description="Identifiant de l'analyse (ANALYSIS-XXX)")
    documents: list[dict] = Field(default_factory=list)
    extraction: DocumentationExtraction | None = None
    assets: list[Asset] = Field(default_factory=list)
    threats: list[Threat] = Field(default_factory=list)
    vulnerabilities: list[Vulnerability] = Field(default_factory=list)
    scenarios: list[RiskScenario] = Field(default_factory=list)
    risks: list[Risk] = Field(default_factory=list)
    critic_report: CriticReport | None = None
    audit: list[AuditEntry] = Field(default_factory=list)
    status: str = WorkflowStage.IMPORT.value
    created_at: str = Field(description="ISO 8601 UTC")
    updated_at: str = Field(description="ISO 8601 UTC")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class Orchestrator:
    """Coordonne les agents dans l'ordre du workflow, journalise chaque
    étape et bloque la validation finale tant que l'humain n'a pas décidé."""

    stages: list[WorkflowStage] = list(WorkflowStage)

    def stage_index(self, stage: WorkflowStage) -> int:
        return self.stages.index(stage)

    def next_stage(self, current: WorkflowStage | None) -> WorkflowStage | None:
        """Retourne l'étape suivante, ou None si le workflow est terminé."""
        if current is None:
            return self.stages[0]
        index = self.stage_index(current)
        if index + 1 >= len(self.stages):
            return None
        return self.stages[index + 1]

    # ------------------------------------------------------------------
    # Exécution du pipeline complet (étapes 1 à 9)
    # ------------------------------------------------------------------

    def run(
        self,
        documents: list[dict],
        *,
        analysis_id: str | None = None,
        llm=None,
        progress: Callable[["AnalysisState"], None] | None = None,
    ) -> AnalysisState:
        """Exécute le workflow complet et retourne le registre proposé.

        `progress` (optionnel) est appelé après chaque étape avec l'état
        courant, permettant de persister l'avancement pour l'interface.
        """
        if not documents:
            raise AgentError("aucun document : importer au moins un fichier")

        def _emit() -> None:
            if progress is not None:
                state.updated_at = _now()
                progress(state)

        created = _now()
        state = AnalysisState(
            id=analysis_id or f"ANALYSIS-{uuid.uuid4().hex[:8]}",
            documents=documents,
            created_at=created,
            updated_at=created,
            status=WorkflowStage.IMPORT.value,
        )
        self._audit(
            state,
            action="DOCUMENT_IMPORT",
            agent="orchestrator",
            input_=[doc["id"] for doc in documents],
            output=f"{len(documents)} document(s) importé(s)",
            source=[doc["id"] for doc in documents],
        )

        # Étape 2 — Extraction documentaire
        extraction = DocumentationAgent().run(documents, llm=llm)
        state.extraction = extraction
        state.status = WorkflowStage.EXTRACTION.value
        self._audit(
            state,
            action="DOCUMENT_EXTRACTION",
            agent="documentation-agent",
            input_=f"{len(documents)} document(s)",
            output=extraction.system_name,
            source=extraction.field_sources("system_name"),
        )
        _emit()

        # Étape 3 — Identification des actifs
        assets = AssetAgent().run(extraction, llm=llm)
        state.assets = assets
        state.status = WorkflowStage.ASSETS.value
        self._audit(
            state,
            action="ASSET_IDENTIFICATION",
            agent="asset-agent",
            input_=extraction.system_name,
            output=[asset.id for asset in assets],
            source=[s for asset in assets for s in asset.source],
        )
        _emit()

        # Étape 4 — Identification des menaces
        threats = ThreatAgent().run(assets, extraction=extraction, llm=llm)
        state.threats = threats
        state.status = WorkflowStage.THREATS.value
        self._audit(
            state,
            action="THREAT_IDENTIFICATION",
            agent="threat-agent",
            input_=[asset.id for asset in assets],
            output=[threat.id for threat in threats],
            source=[s for threat in threats for s in threat.source],
        )
        _emit()

        # Étape 5 — Identification des vulnérabilités
        vulnerabilities = VulnerabilityAgent().run(
            assets, threats, extraction=extraction, llm=llm
        )
        state.vulnerabilities = vulnerabilities
        state.status = WorkflowStage.VULNERABILITIES.value
        self._audit(
            state,
            action="VULNERABILITY_IDENTIFICATION",
            agent="vulnerability-agent",
            input_=[threat.id for threat in threats],
            output=[vuln.id for vuln in vulnerabilities],
            source=[s for vuln in vulnerabilities for s in vuln.source],
        )
        _emit()

        # Étape 6 — Construction des scénarios
        scenarios = RiskScenarioAgent().run(
            assets, threats, vulnerabilities, extraction=extraction, llm=llm
        )
        state.scenarios = scenarios
        state.status = WorkflowStage.SCENARIOS.value
        self._audit(
            state,
            action="RISK_SCENARIO_BUILD",
            agent="risk-scenario-agent",
            input_={
                "assets": [a.id for a in assets],
                "threats": [t.id for t in threats],
                "vulnerabilities": [v.id for v in vulnerabilities],
            },
            output=[scenario.id for scenario in scenarios],
            source=[s for scenario in scenarios for s in scenario.source],
        )
        _emit()

        # Étape 7 — Évaluation Probabilité × Impact
        risks = RiskAssessmentAgent().run(
            scenarios, assets=assets, vulnerabilities=vulnerabilities, llm=llm
        )
        state.risks = risks
        state.status = WorkflowStage.ASSESSMENT.value
        self._audit(
            state,
            action="RISK_ASSESSMENT",
            agent="risk-assessment-agent",
            input_=[scenario.id for scenario in scenarios],
            output=[f"{risk.id}:{risk.score}" for risk in risks],
            source=[s for risk in risks for s in risk.sources],
        )
        _emit()

        # Étape 8 — Critique automatique (obligatoire avant registre)
        report = CriticAgent().run(
            extraction, assets, threats, vulnerabilities, risks
        )
        state.critic_report = report
        state.status = WorkflowStage.CRITIQUE.value
        self._audit(
            state,
            action="CRITIC_REVIEW",
            agent="critic-agent",
            input_=[risk.id for risk in risks],
            output={
                "status": report.status.value,
                "issues": report.issues,
                "missing_information": report.missing_information,
            },
            source=report.source,
        )
        _emit()

        # Étape 9 — Registre proposé
        for risk in state.risks:
            risk.critic_report = report
        state.status = WorkflowStage.PROPOSED_REGISTER.value
        state.updated_at = _now()
        self._audit(
            state,
            action="PROPOSED_REGISTER",
            agent="orchestrator",
            input_=None,
            output=[risk.id for risk in state.risks],
            source=[s for risk in state.risks for s in risk.sources],
        )
        return state

    # ------------------------------------------------------------------
    # Étape 10 — Validation humaine (bloquante)
    # ------------------------------------------------------------------

    def human_validate(
        self,
        state: AnalysisState,
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
        """Applique la décision humaine à un risque du registre proposé.

        - La critique automatique doit avoir tourné (étape bloquante) ;
        - `action` : ACCEPT | MODIFY | REJECT ;
        - toute modification recrée une évaluation via build_assessment
          (score recalculé, justification obligatoire ≥ 10 caractères).
        """
        if state.critic_report is None:
            raise AgentError(
                "validation humaine impossible : l'agent critique n'a pas tourné"
            )

        risk = self._find_risk(state, risk_id)
        if risk.status is not RiskStatus.PROPOSED_BY_AI:
            raise AgentError(
                f"risque {risk_id} déjà décidé ({risk.status.value}) : "
                "pas de seconde validation sans nouvelle analyse."
            )

        normalized = action.strip().upper()
        if normalized not in {"ACCEPT", "MODIFY", "REJECT"}:
            raise AgentError(
                f"action invalide : {action!r} (attendu ACCEPT | MODIFY | REJECT)"
            )

        if normalized == "MODIFY":
            if probability is None or impact is None or not justification:
                raise AgentError(
                    "pour MODIFER un risque, fournir probability, impact et justification"
                )
            risk.assessment = build_assessment(
                probability,
                impact,
                justification.strip(),
                risk.assessment.source,
            )

        if normalized == "ACCEPT":
            risk.human_validation = HumanValidation.ACCEPTED.value
            risk.status = RiskStatus.VALIDATED_BY_HUMAN
        elif normalized == "MODIFY":
            risk.human_validation = HumanValidation.MODIFIED.value
            risk.status = RiskStatus.MODIFIED_BY_HUMAN
        else:
            risk.human_validation = HumanValidation.REJECTED.value
            risk.status = RiskStatus.REJECTED_BY_HUMAN

        risk.analyst_comment = comment
        if recommended_measures is not None:
            risk.recommended_measures = recommended_measures
        if existing_measures is not None:
            risk.existing_measures = existing_measures
        if residual_risk is not None:
            risk.residual_risk = residual_risk
        if owner is not None:
            risk.owner = owner
        risk.updated_at = _now()

        self._audit(
            state,
            action="RISK_VALIDATION",
            agent="human-analyst",
            input_=risk_id,
            output={
                "action": normalized,
                "status": risk.status.value,
                "validation": risk.human_validation,
                "score": risk.score,
            },
            source=risk.sources,
            user=user,
            comment=comment,
            human_validation=risk.human_validation,
        )

        all_decided = all(
            r.status is not RiskStatus.PROPOSED_BY_AI for r in state.risks
        )
        if all_decided:
            state.status = WorkflowStage.FINAL_REGISTER.value
        else:
            state.status = WorkflowStage.PROPOSED_REGISTER.value
        state.updated_at = _now()
        return state

    # ------------------------------------------------------------------
    # Aides
    # ------------------------------------------------------------------

    @staticmethod
    def _find_risk(state: AnalysisState, risk_id: str) -> Risk:
        for risk in state.risks:
            if risk.id == risk_id:
                return risk
        raise AgentError(f"risque inconnu : {risk_id}")

    @staticmethod
    def _audit(
        state: AnalysisState,
        *,
        action: str,
        agent: str,
        input_: object,
        output: object,
        source: list[str] | None = None,
        user: str | None = None,
        comment: str | None = None,
        human_validation: str = "PENDING",
    ) -> None:
        state.audit.append(
            AuditEntry(
                timestamp=_now(),
                agent=agent,
                action=action,
                input=input_ if isinstance(input_, (str, list, dict)) else repr(input_),
                output=output if isinstance(output, (str, list, dict)) else repr(output),
                source=list(dict.fromkeys(source or [])),
                human_validation=human_validation,
                user=user,
                comment=comment,
            )
        )

    # ------------------------------------------------------------------
    # Sérialisation
    # ------------------------------------------------------------------

    @staticmethod
    def to_dict(state: AnalysisState) -> dict:
        """État sérialisable (JSON) pour la persistance / l'API."""
        return state.model_dump(mode="json")

    @classmethod
    def from_dict(cls, data: dict) -> AnalysisState:
        """Reconstruit un état analysé depuis sa représentation JSON."""
        return AnalysisState.model_validate(data)


__all__ = ["Orchestrator", "WorkflowStage", "AnalysisState"]