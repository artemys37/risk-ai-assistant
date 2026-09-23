"""Tests de bout en bout Sprint 3-4 : orchestration complète + validation humaine.

Documents → extraction → actifs → menaces → vulnérabilités → scénarios →
évaluation → critique → registre proposé → décision humaine → registre final.
Vérifie aussi le blocage de l'étape 10 (critique obligatoire).
"""

import pytest

from app.agents.base import AgentError
from app.models.base import HumanValidation
from app.models.risk import RiskStatus
from app.orchestration.workflow import Orchestrator, WorkflowStage, AnalysisState
from app.services.llm import LLMClient
from tests.helpers import canned_responder


def sample_documents() -> list[dict]:
    from app.services.document_parser import load_documents

    text = (
        "## Système Gestion RH\n"
        "Application web interne utilisée par les employés du service RH.\n"
        "Données : salaires, contrats, évaluations.\n"
        "Serveur : Linux, base PostgreSQL, authentification Active Directory.\n"
        "Une API interne expose des données RH aux autres applications.\n"
        "Un pare-feu protège le réseau. Les sauvegardes sont quotidiennes.\n"
    )
    return load_documents([("systeme.md", text.encode())])


def test_full_pipeline_to_proposed_register(service, mock_llm) -> None:
    orchestrator = Orchestrator()
    state = orchestrator.run(sample_documents(), llm=mock_llm())

    assert state.id.startswith("ANALYSIS-")
    assert state.status == WorkflowStage.PROPOSED_REGISTER.value
    assert state.extraction is not None
    assert state.assets
    assert state.threats
    assert state.vulnerabilities
    assert state.scenarios
    assert state.risks
    assert state.critic_report is not None

    # Chaque risque est une proposition IA en attente d'humain.
    for risk in state.risks:
        assert risk.status is RiskStatus.PROPOSED_BY_AI
        assert risk.human_validation == HumanValidation.PENDING.value

    # Traçabilité : le journal couvre les étapes clés.
    actions = [entry.action for entry in state.audit]
    assert "DOCUMENT_EXTRACTION" in actions
    assert "ASSET_IDENTIFICATION" in actions
    assert "THREAT_IDENTIFICATION" in actions
    assert "VULNERABILITY_IDENTIFICATION" in actions
    assert "RISK_SCENARIO_BUILD" in actions
    assert "RISK_ASSESSMENT" in actions
    assert "CRITIC_REVIEW" in actions
    assert "PROPOSED_REGISTER" in actions


def test_pipeline_matches_scenario_ids(mock_llm) -> None:
    """Les identifiants des scénarios RSK-001/RSK-002 sont stables
    (déterministes) et repris dans les risques."""
    orchestrator = Orchestrator()
    state = orchestrator.run(sample_documents(), llm=mock_llm())
    assert [r.id for r in state.risks] == ["RSK-001", "RSK-002"]
    assert state.risks[0].score == 12
    assert state.risks[1].score == 20


def test_human_validation_accept_and_modify(mock_llm) -> None:
    orchestrator = Orchestrator()
    state = orchestrator.run(sample_documents(), llm=mock_llm())

    state = orchestrator.human_validate(
        state, "RSK-001", "ACCEPT", user="analyste-test", comment="Conforme."
    )
    risk = next(r for r in state.risks if r.id == "RSK-001")
    assert risk.status is RiskStatus.VALIDATED_BY_HUMAN
    assert risk.human_validation == HumanValidation.ACCEPTED.value
    assert risk.analyst_comment == "Conforme."

    state = orchestrator.human_validate(
        state,
        "RSK-002",
        "MODIFY",
        user="analyste-test",
        probability=5,
        impact=5,
        justification="Données RH critiques : surexposition confirmée.",
        recommended_measures="Chiffrement + contrôle d'accès renforcé.",
    )
    risk = next(r for r in state.risks if r.id == "RSK-002")
    assert risk.status is RiskStatus.MODIFIED_BY_HUMAN
    assert risk.score == 25
    assert risk.recommended_measures == "Chiffrement + contrôle d'accès renforcé."

    assert state.status == WorkflowStage.FINAL_REGISTER.value

    audit_tail = [e for e in state.audit if e.action == "RISK_VALIDATION"]
    assert len(audit_tail) == 2
    assert all(e.agent == "human-analyst" for e in audit_tail)


def test_human_validate_reject(mock_llm) -> None:
    orchestrator = Orchestrator()
    state = orchestrator.run(sample_documents(), llm=mock_llm())
    state = orchestrator.human_validate(state, "RSK-001", "REJECT", user="a")
    risk = next(r for r in state.risks if r.id == "RSK-001")
    assert risk.status is RiskStatus.REJECTED_BY_HUMAN
    assert risk.human_validation == HumanValidation.REJECTED.value


def test_human_validation_is_blocked_without_critic() -> None:
    """L'étape 10 est bloquante : pas de décision humaine sans critique."""
    from app.services.document_parser import load_documents
    from app.models.risk import Risk, RiskAssessment, RiskScenario
    from app.models.asset import Asset, AssetType
    from app.models.threat import Threat
    from app.models.vulnerability import Vulnerability, VulnerabilityStatus

    documents = load_documents([("x.md", b"Contenu.")])
    state = AnalysisState(
        id="ANALYSIS-TEST-BLOCK",
        documents=documents,
        created_at="2026-09-23T00:00:00Z",
        updated_at="2026-09-23T00:00:00Z",
        critic_report=None,  # critique jamais passée
    )
    scenario = RiskScenario(
        id="RSK-001", description="Scénario minimal.",
        threat_actor="Acteur", feared_event="Événement",
        asset_id="ACT-001", threat_id="THR-001", vulnerability_id="VUL-001",
        consequences=["Conséquence"], source=["DOC-001"],
    )
    state.risks = [
        Risk(
            id="RSK-001",
            scenario=scenario,
            assessment=RiskAssessment(
                probability=3, impact=3,
                justification="Justification minimale valide.",
                source=["DOC-001"],
            ),
        )
    ]
    with pytest.raises(AgentError, match="critique n'a pas tourné"):
        Orchestrator().human_validate(state, "RSK-001", "ACCEPT", user="a")


def test_run_rejects_empty_documents() -> None:
    llm = LLMClient(provider="mock", responder=canned_responder({}))
    with pytest.raises(AgentError, match="aucun document"):
        Orchestrator().run([], llm=llm)