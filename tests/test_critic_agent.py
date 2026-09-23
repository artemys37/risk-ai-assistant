"""Tests de l'agent Critique (Sprint 4) — vérifications déterministes."""

from app.agents.critic_agent import CriticAgent
from app.models.asset import Asset, AssetType
from app.models.base import NOT_DOCUMENTED, EvidenceType
from app.models.risk import (
    CriticStatus,
    Risk,
    RiskScenario,
)
from app.models.threat import Threat
from app.models.vulnerability import Vulnerability, VulnerabilityStatus
from app.services.risk_scoring import build_assessment


def _linked_parts() -> dict:
    asset = Asset(
        id="ACT-001", name="Serveur API", type=AssetType.INTERFACE,
        owner="DSI", business_value="Données RH", source=["DOC-001"],
    )
    threat = Threat(
        id="THR-001", name="Accès non autorisé",
        description="Accès illégitime aux données.",
        target_assets=["ACT-001"], rationale="Exposition documentée.",
        evidence=["DOC-001"], source=["DOC-001"],
    )
    vuln = Vulnerability(
        id="VUL-001", name="Contrôle d'accès API non documenté",
        description="Autorisation non précisée.",
        status=VulnerabilityStatus.TO_VERIFY, target_assets=["ACT-001"],
        related_threats=["THR-001"], rationale="Non documenté.",
        source=["DOC-001"],
    )
    scenario = RiskScenario(
        id="RSK-001",
        description="Un acteur exploite une vulnérabilité pour atteindre un actif.",
        threat_actor="Acteur extérieur", feared_event="Accès non autorisé",
        asset_id="ACT-001", threat_id="THR-001", vulnerability_id="VUL-001",
        consequences=["Perte de confidentialité"], source=["DOC-001"],
    )
    risk = Risk(
        id="RSK-001", scenario=scenario,
        assessment=build_assessment(3, 4, "Interface exposée : probabilité moyenne, impact élevé.", ["DOC-001"]),
    )
    return {"asset": asset, "threat": threat, "vuln": vuln, "risk": risk}


def test_pass_when_fully_coherent() -> None:
    parts = _linked_parts()
    report = CriticAgent().run(
        {}, [parts["asset"]], [parts["threat"]], [parts["vuln"]], [parts["risk"]]
    )
    assert report.status is CriticStatus.PASS
    assert "RSK-001" in report.checked_ids


def test_reject_when_reference_unknown() -> None:
    parts = _linked_parts()
    parts["risk"].scenario.asset_id = "ACT-999"
    report = CriticAgent().run(
        {}, [parts["asset"]], [parts["threat"]], [parts["vuln"]], [parts["risk"]]
    )
    assert report.status is CriticStatus.REJECT
    assert any("actif inconnu" in issue for issue in report.issues)


def test_review_required_when_information_missing() -> None:
    parts = _linked_parts()
    parts["asset"].owner = NOT_DOCUMENTED
    parts["asset"].business_value = NOT_DOCUMENTED
    report = CriticAgent().run(
        {}, [parts["asset"]], [parts["threat"]], [parts["vuln"]], [parts["risk"]]
    )
    assert report.status is CriticStatus.REVIEW_REQUIRED
    assert report.missing_information


def test_reject_without_source_or_hypothesis() -> None:
    parts = _linked_parts()
    parts["risk"].scenario.source = []
    parts["risk"].assessment.source = []
    parts["risk"].scenario.hypotheses = []
    report = CriticAgent().run(
        {}, [parts["asset"]], [parts["threat"]], [parts["vuln"]], [parts["risk"]]
    )
    assert report.status is CriticStatus.REJECT
    assert any("source ni hypothèse" in issue for issue in report.issues)


def test_reject_for_unjustified_score() -> None:
    parts = _linked_parts()
    # Évaluation volontairement sans source : l'agent critique doit exiger
    # une traçabilité de la cotation (score = 12 sans source reliée).
    parts["risk"].scenario.source = []
    parts["risk"].assessment.source = []
    parts["risk"].scenario.hypotheses = []
    report = CriticAgent().run(
        {}, [parts["asset"]], [parts["threat"]], [parts["vuln"]], [parts["risk"]]
    )
    assert report.status is CriticStatus.REJECT
    assert any("source ni hypothèse" in issue for issue in report.issues)


def test_review_required_when_vulnerability_too_certain() -> None:
    """Une vulnérabilité CONFIRMÉE sans fait documenté doit être signalée."""
    parts = _linked_parts()
    parts["vuln"].status = VulnerabilityStatus.CONFIRMED
    parts["vuln"].evidence_type = EvidenceType.INFERENCE
    report = CriticAgent().run(
        {}, [parts["asset"]], [parts["threat"]], [parts["vuln"]], [parts["risk"]]
    )
    assert report.status is CriticStatus.REVIEW_REQUIRED
    assert any("CONFIRMÉE" in issue for issue in report.issues)


def test_empty_analysis_returns_pass() -> None:
    report = CriticAgent().run(None, [], [], [], [])
    assert report.status is CriticStatus.PASS
    assert report.checked_ids == []