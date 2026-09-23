"""Tests de l'agent Évaluation (Sprint 3) — chemin LLM et repli déterministe."""

from app.agents.risk_assessment_agent import RiskAssessmentAgent
from app.models.asset import Asset, AssetType
from app.models.risk import RiskScenario, RiskStatus
from app.models.vulnerability import Vulnerability, VulnerabilityStatus
from app.services.llm import LLMClient
from tests.helpers import canned_responder


def _scenario(scenario_id: str = "RSK-001") -> RiskScenario:
    return RiskScenario(
        id=scenario_id,
        description="Un acteur exploite une vulnérabilité pour atteindre un actif.",
        threat_actor="Acteur extérieur",
        feared_event="Accès non autorisé aux données",
        asset_id="ACT-001",
        threat_id="THR-001",
        vulnerability_id="VUL-001",
        consequences=["Perte de confidentialité"],
        source=["DOC-001"],
    )


def _vuln(status: VulnerabilityStatus = VulnerabilityStatus.TO_VERIFY) -> Vulnerability:
    return Vulnerability(
        id="VUL-001",
        name="Contrôle d'accès API non documenté",
        description="La documentation ne précise pas d'autorisation sur l'API.",
        status=status,
        target_assets=["ACT-001"],
        rationale="Information absente de la documentation.",
        source=["DOC-001"],
    )


def _asset() -> Asset:
    return Asset(id="ACT-001", name="Serveur API", type=AssetType.INTERFACE, source=["DOC-001"])


def test_fallback_without_llm_produces_valid_risk() -> None:
    scenario = _scenario()
    risks = RiskAssessmentAgent().run(
        [scenario], assets=[_asset()], vulnerabilities=[_vuln()]
    )
    assert len(risks) == 1
    risk = risks[0]
    assert risk.id == scenario.id
    assert risk.status is RiskStatus.PROPOSED_BY_AI
    assert 1 <= risk.assessment.probability <= 5
    assert 1 <= risk.assessment.impact <= 5
    assert risk.score == risk.assessment.probability * risk.assessment.impact
    assert len(risk.assessment.justification) >= 10


def test_fallback_probability_tracks_vuln_status() -> None:
    scenarios = [_scenario()]
    confident_risk = RiskAssessmentAgent().run(
        scenarios, assets=[_asset()], vulnerabilities=[_vuln(VulnerabilityStatus.CONFIRMED)]
    )[0]
    weak_risk = RiskAssessmentAgent().run(
        scenarios, assets=[_asset()], vulnerabilities=[_vuln(VulnerabilityStatus.NOT_ESTABLISHED)]
    )[0]
    assert confident_risk.assessment.probability > weak_risk.assessment.probability


def test_llm_proposal_is_used_when_valid() -> None:
    payload = [
        {
            "scenario_id": "RSK-001",
            "probability": 2,
            "impact": 5,
            "justification": "Interface exposée : probabilité faible, impact très élevé.",
            "source": ["DOC-001"],
        }
    ]
    llm = LLMClient(provider="mock", responder=canned_responder(payload))
    risk = RiskAssessmentAgent().run([_scenario()], assets=[_asset()], vulnerabilities=[_vuln()], llm=llm)[0]
    assert risk.assessment.probability == 2
    assert risk.assessment.impact == 5
    assert risk.score == 10
    assert risk.created_by == "risk-assessment-agent"


def test_invalid_llm_proposal_falls_back() -> None:
    # probabilité hors échelle ⇒ repli déterministe sûr
    payload = [
        {
            "scenario_id": "RSK-001",
            "probability": 9,
            "impact": 2,
            "justification": "invalide",
        }
    ]
    llm = LLMClient(provider="mock", responder=canned_responder(payload))
    risk = RiskAssessmentAgent().run(
        [_scenario()], assets=[_asset()], vulnerabilities=[_vuln()], llm=llm
    )[0]
    assert 1 <= risk.assessment.probability <= 5
    assert 1 <= risk.assessment.impact <= 5
    assert risk.score == risk.assessment.probability * risk.assessment.impact


def test_empty_scenarios_return_empty_list() -> None:
    assert RiskAssessmentAgent().run([]) == []