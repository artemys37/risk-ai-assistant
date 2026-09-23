"""Tests de l'agent Scénarios (Sprint 3) — assemblage déterministe."""

from app.agents.risk_scenario_agent import RiskScenarioAgent, _derive_actor
from app.models.asset import Asset, AssetType
from app.models.base import ConfidenceLevel, EvidenceType
from app.models.threat import Threat
from app.models.vulnerability import Vulnerability, VulnerabilityStatus


def _base_asset(asset_id: str = "ACT-001", name: str = "Serveur API") -> Asset:
    return Asset(id=asset_id, name=name, type=AssetType.INTERFACE, source=["DOC-001"])


def make(threats, vulnerabilities, assets=None) -> tuple:
    assets = assets or [_base_asset()]
    scenarios = RiskScenarioAgent().run(assets, threats, vulnerabilities)
    return scenarios


def _threat() -> Threat:
    return Threat(
        id="THR-001",
        name="Accès non autorisé",
        description="Accès illégitime aux données via l'interface exposée.",
        target_assets=["ACT-001"],
        rationale="Interface exposée sur le réseau.",
        evidence=["DOC-001"],
        source=["DOC-001"],
    )


def _vuln() -> Vulnerability:
    return Vulnerability(
        id="VUL-001",
        name="Contrôle d'accès API non documenté",
        description="La documentation ne précise pas d'autorisation sur l'API.",
        status=VulnerabilityStatus.TO_VERIFY,
        target_assets=["ACT-001"],
        related_threats=["THR-001"],
        rationale="Information absente de la documentation.",
        source=["DOC-001"],
        evidence_type=EvidenceType.HYPOTHESIS,
    )


def test_empty_inputs_return_empty_list() -> None:
    assert RiskScenarioAgent().run([], [], []) == []


def test_scenario_built_from_coherent_triple() -> None:
    scenarios = make([_threat()], [_vuln()])
    assert len(scenarios) == 1
    scenario = scenarios[0]
    assert scenario.id == "RSK-001"
    assert scenario.asset_id == "ACT-001"
    assert scenario.threat_id == "THR-001"
    assert scenario.vulnerability_id == "VUL-001"
    assert scenario.feared_event  # événement redouté non vide


def test_no_scenario_without_shared_target() -> None:
    threat = _threat()
    vuln = _vuln()
    vuln.target_assets = ["ACT-099"]  # aucune cible commune
    scenarios = make([threat], [vuln])
    assert scenarios == []


def test_sources_and_evidence_preserved() -> None:
    scenario = make([_threat()], [_vuln()])[0]
    assert "DOC-001" in scenario.source
    assert "DOC-001" in scenario.evidence


def test_conservative_evidence_type() -> None:
    # vulnérabilité en HYPOTHÈSE → le scénario est au plus HYPOTHÈSE
    scenario = make([_threat()], [_vuln()])[0]
    assert scenario.evidence_type is EvidenceType.HYPOTHESIS


def test_conservative_confidence() -> None:
    scenario = make([_threat()], [_vuln()])[0]
    assert scenario.confidence is ConfidenceLevel.MEDIUM


def test_actor_derivation_falls_back_to_threat_name() -> None:
    threat = _threat()
    threat.description = "phénomène neutre sans acteur"
    threat.rationale = "élément sans qualificatif"
    assert "Accès non autorisé" in _derive_actor(threat)


def test_actor_detects_external_actor() -> None:
    threat = _threat()
    threat.rationale = "Attaquant externe documenté dans l'exposition réseau."
    assert "extérieur" in _derive_actor(threat).lower()


def test_duplicates_are_deduplicated() -> None:
    # même triplet via cibles communes + related_threats → un seul scénario
    assets = [_base_asset(), _base_asset("ACT-002", name="Second serveur")]
    threat = _threat()
    threat.target_assets = ["ACT-001", "ACT-002"]
    vulnerabilities = [
        _vuln(),
        Vulnerability(
            id="VUL-002",
            name="Échappement réseau",
            description="Exposition réseau non documentée.",
            status=VulnerabilityStatus.TO_VERIFY,
            target_assets=["ACT-002"],
            related_threats=["THR-001"],
            rationale="Élément indéterminé.",
            source=["DOC-001"],
        ),
    ]
    scenarios = RiskScenarioAgent().run(assets, [threat], vulnerabilities)
    pairs = {(s.asset_id, s.threat_id, s.vulnerability_id) for s in scenarios}
    assert len(pairs) == len(scenarios)  # aucune redondance