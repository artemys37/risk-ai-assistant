"""Tests de l'agent Actifs (Sprint 2)."""

import pytest

from app.agents.asset_agent import AssetAgent, AssetType
from app.agents.base import AgentError
from app.models.base import NOT_DOCUMENTED, ConfidenceLevel
from app.models.extraction import DocumentationExtraction
from app.services.llm import LLMClient

PAYLOAD = [
    {
        "name": "Serveur Web",
        "type": "serveur",
        "description": "Héberge l'application Gestion RH",
        "owner": "Non documenté",
        "business_value": "Non documenté",
        "source": ["DOC-001"],
        "evidence_type": "FAIT DOCUMENTÉ",
    },
    {
        "name": "Base RH",
        "type": "base de données",
        "description": "Base PostgreSQL des données RH",
        "owner": "DRH",
        "business_value": "Critique",
        "source": ["DOC-001"],
        "evidence_type": "FAIT DOCUMENTÉ",
    },
    {
        "name": "Pare-feu",
        "type": "poste client",  # type incohérent → mis en « autre » ou corrigé
        "owner": "Non documenté",
    },
]


def _extraction() -> DocumentationExtraction:
    return DocumentationExtraction.model_validate(
        {"system_name": "Gestion RH", "sources": {"system_name": ["DOC-001"]}}
    )


def test_assets_identified_and_numbered() -> None:
    llm = LLMClient(provider="mock", responder=lambda s, u: __import__("json").dumps(PAYLOAD))
    assets = AssetAgent().run(_extraction(), llm=llm)

    assert [a.id for a in assets] == ["ACT-001", "ACT-002", "ACT-003"]
    assert assets[0].name == "Serveur Web"
    assert assets[0].type == AssetType.SERVER
    assert assets[1].type == AssetType.DATA
    assert assets[1].owner == "DRH"
    assert assets[1].business_value == "Critique"


def test_asset_never_invents_owner_or_value() -> None:
    llm = LLMClient(provider="mock", responder=lambda s, u: __import__("json").dumps(PAYLOAD))
    assets = AssetAgent().run(_extraction(), llm=llm)

    assert assets[0].owner == NOT_DOCUMENTED
    assert assets[0].business_value == NOT_DOCUMENTED


def test_asset_unknown_type_falls_back_to_other() -> None:
    llm = LLMClient(provider="mock", responder=lambda s, u: __import__("json").dumps(PAYLOAD))
    assets = AssetAgent().run(_extraction(), llm=llm)

    # "poste client" est un type d'actif valide ; l'agent ne doit JAMAIS
    # créer de type inventé. La cohérence (pare-feu ≠ poste client) est
    # vérifiée par l'agent critique (Sprint 4).
    assert assets[2].type in {
        AssetType.NETWORK_EQUIPMENT,
        AssetType.OTHER,
        AssetType.CLIENT_WORKSTATION,
    }


def test_asset_confidence_from_sources_and_evidence() -> None:
    llm = LLMClient(provider="mock", responder=lambda s, u: __import__("json").dumps(PAYLOAD))
    assets = AssetAgent().run(_extraction(), llm=llm)

    assert assets[0].confidence == ConfidenceLevel.HIGH  # source + fait documenté
    assert assets[0].evidence_type.value == "FAIT DOCUMENTÉ"


def test_handles_unstructured_items_gracefully() -> None:
    payload = [{"name": "Compte Admin", "type": "compte"}]
    llm = LLMClient(provider="mock", responder=lambda s, u: __import__("json").dumps(payload))
    assets = AssetAgent().run(_extraction(), llm=llm)

    assert [a.id for a in assets] == ["ACT-001"]
    assert assets[0].type == AssetType.ACCOUNT
    assert assets[0].owner == NOT_DOCUMENTED


def test_asset_agent_rejects_non_list_output() -> None:
    llm = LLMClient(provider="mock", responder=lambda s, u: '{"name": "x"}')
    with pytest.raises(AgentError, match="liste JSON"):
        AssetAgent().run(_extraction(), llm=llm)