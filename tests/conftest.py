"""Aides partagées : stockage temporaire, LLM mock complet du pipeline.

Chaque test utilise sa propre base SQLite temporaire : la base réelle
(data/risk_ai.db) n'est jamais touchée par la suite de tests.
"""

import pytest
from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app as APP_APP
from app.services.llm import LLMClient
from tests.helpers import dispatch_responder

MOCK_SYSTEM = "agent « Documentation »"
MOCK_ASSETS = "agent « Actifs »"
MOCK_THREATS = "agent « Menaces »"
MOCK_VULNS = "agent « Vulnérabilités »"
MOCK_ASSESSMENT = "agent « Évaluation »"


@pytest.fixture
def tmp_db_path(tmp_path: Path) -> Path:
    return tmp_path / "test.db"


@pytest.fixture
def service(tmp_db_path: Path):
    """Service d'analyse branché sur une base temporaire."""
    from app.services.analysis_service import AnalysisService
    from app.services.storage import Storage

    return AnalysisService(storage=Storage(tmp_db_path))


@pytest.fixture
def mock_llm():
    """LLM mock répondant à tous les agents du pipeline (prompts distincts)."""
    from tests.test_pipeline_sprint2 import (
        EXTRACTION,
        ASSETS,
        THREATS,
        VULNERABILITIES,
    )

    assessment_payload = [
        {
            "scenario_id": "RSK-001",
            "probability": 3,
            "impact": 4,
            "justification": "Accès à l'API non maîtrisé : probabilité moyenne, "
            "impact élevé sur les données RH.",
            "source": ["DOC-001"],
        },
        {
            "scenario_id": "RSK-002",
            "probability": 4,
            "impact": 5,
            "justification": "Base RH exposée à une menace documentée : "
            "probabilité élevée, impact très élevé sur la confidentialité.",
            "source": ["DOC-001"],
        },
    ]
    responder = dispatch_responder(
        {
            MOCK_SYSTEM: EXTRACTION,
            MOCK_ASSETS: ASSETS,
            MOCK_THREATS: THREATS,
            MOCK_VULNS: VULNERABILITIES,
            MOCK_ASSESSMENT: assessment_payload,
        }
    )
    return lambda: LLMClient(provider="mock", responder=responder)


@pytest.fixture
def client(service, mock_llm, monkeypatch):
    """Client HTTP branché sur une base temporaire et un LLM mock partout.

    Le LLM par défaut (utilisé par les endpoints /run) est remplacé par le
    mock : aucun appel réseau n'est réalisé pendant les tests.
    """
    import app.api.routes as api_routes
    import app.web as web_mod
    from app.services.analysis_service import AnalysisService
    from app.services.storage import Storage

    api_routes._service = service
    web_mod._service = service

    builder = mock_llm

    class _MockLLM:
        def __new__(cls):
            return builder()

    monkeypatch.setattr("app.agents.base.LLMClient", _MockLLM)

    with TestClient(APP_APP) as c:
        yield c