"""Tests de l'agent Menaces (Sprint 2)."""

from app.agents.threat_agent import ThreatAgent
from app.models.asset import Asset, AssetType
from app.services.llm import LLMClient
from tests.helpers import canned_responder

SERVER_ASSET = Asset(id="ACT-001", name="Serveur Web", type=AssetType.SERVER)

PAYLOAD = [
    {
        "name": "Accès non autorisé",
        "description": "Un attaquant externe exploite le service exposé.",
        "target_assets": ["ACT-001"],
        "rationale": "Le serveur est exposé sur Internet, la doc ne mentionne aucun WAF.",
        "evidence": ["DOC-001"],
        "stride_category": "Information Disclosure",
        "source": ["DOC-001"],
        "evidence_type": "INFERENCE",
    },
    {
        "name": "Menace orpheline",
        "description": "Aucune cible ACT-XXX valide.",
        "target_assets": ["ACT-999", "chose"],
        "rationale": "Sans cible.",
    },
]


def test_threats_with_rationale_and_assets() -> None:
    llm = LLMClient(provider="mock", responder=canned_responder(PAYLOAD))
    threats = ThreatAgent().run([SERVER_ASSET], llm=llm)

    assert len(threats) == 1  # la menace orpheline (cible invalide) est écartée
    assert threats[0].id == "THR-001"
    assert threats[0].target_assets == ["ACT-001"]
    assert threats[0].rationale  # justification obligatoire
    assert threats[0].stride_category == "Information Disclosure"


def test_threat_does_not_invent_evidence() -> None:
    payload = [
        {
            "name": "DoS",
            "description": "d",
            "target_assets": ["ACT-001"],
            "rationale": "Le service est critique et la doc ne mentionne pas de limitation.",
        }
    ]
    llm = LLMClient(provider="mock", responder=canned_responder(payload))
    threats = ThreatAgent().run([SERVER_ASSET], llm=llm)
    # éléments de preuve non fournis → liste vide (jamais inventée)
    assert threats[0].evidence == []


def test_empty_assets_returns_no_threats() -> None:
    assert ThreatAgent().run([]) == []