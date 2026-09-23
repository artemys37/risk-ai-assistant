"""Tests de l'API REST — cycle de vie complet via HTTP.

La suite utilise une base temporaire (fixture `service`) et un LLM mock :
le module de routes est branché sur ce service isolé.
"""

import pytest
from fastapi.testclient import TestClient

from app.main import app


def _upload(client, content: bytes = None, name: str = "systeme.md"):
    content = content if content is not None else (
        b"## Systeme RH\nApplication web interne. Serveur Linux, PostgreSQL.\n"
    )
    return client.post("/api/analysis", files={"files": (name, content, "text/markdown")})


def test_health_and_meta(client) -> None:
    assert client.get("/api/health").json()["status"] == "ok"
    meta = client.get("/api/meta").json()
    assert meta["human_decision_required"] is True
    assert meta["stages_count"] == 11


def test_create_analysis_imports_documents(client) -> None:
    response = _upload(client)
    assert response.status_code == 201
    body = response.json()
    assert body["analysis_id"].startswith("ANALYSIS-")
    assert body["documents"][0]["id"] == "DOC-001"

    # Import seul : l'analyse n'est pas encore exécutée.
    state = client.get(f"/api/analysis/{body['analysis_id']}").json()
    assert state["status"] == "1. Import de la documentation"
    assert state["risks"] == []


def test_run_and_fetch_full_analysis(client, mock_llm) -> None:
    analysis_id = _upload(client).json()["analysis_id"]
    run = client.post(f"/api/analysis/{analysis_id}/run")
    assert run.status_code == 200
    assert run.json()["status"] == "9. Registre des risques proposé"

    state = client.get(f"/api/analysis/{analysis_id}").json()
    assert state["status"].startswith("9.")
    assert len(state["assets"]) == 3
    assert len(state["risks"]) == 2
    assert state["critic_report"]["status"] in {"PASS", "REVIEW_REQUIRED", "REJECT"}

    audit = client.get(f"/api/analysis/{analysis_id}/audit").json()["audit_log"]
    actions = [entry["action"] for entry in audit]
    assert "CRITIC_REVIEW" in actions
    assert "PROPOSED_REGISTER" in actions


def test_human_validation_flow(client, service, mock_llm) -> None:
    analysis_id = _upload(client).json()["analysis_id"]
    service.run(analysis_id, llm=mock_llm())

    response = client.post(
        f"/api/analysis/{analysis_id}/risks/RSK-001/validate",
        json={"action": "ACCEPT", "user": "analyste-test", "comment": "OK"},
    )
    assert response.status_code == 200
    risk = response.json()["risk"]
    assert risk["status"] == "VALIDÉ PAR HUMAIN"
    assert risk["human_validation"] == "ACCEPTED"

    response = client.post(
        f"/api/analysis/{analysis_id}/risks/RSK-002/validate",
        json={
            "action": "MODIFY",
            "probability": 5,
            "impact": 5,
            "justification": "Données RH critiques : surexposition confirmée.",
        },
    )
    assert response.status_code == 200
    assert response.json()["risk"]["score"] == 25

    # Toutes les décisions humaines prises → registre final.
    state = client.get(f"/api/analysis/{analysis_id}").json()
    assert state["status"] == "11. Registre final"


def test_validation_blocked_without_critic_run(client) -> None:
    analysis_id = _upload(client).json()["analysis_id"]
    response = client.post(
        f"/api/analysis/{analysis_id}/risks/RSK-001/validate",
        json={"action": "ACCEPT"},
    )
    assert response.status_code == 400
    assert "critique" in response.json()["detail"]


def test_bad_extension_rejected(client) -> None:
    response = client.post(
        "/api/analysis",
        files={"files": ("malware.exe", b"MZ", "application/octet-stream")},
    )
    assert response.status_code == 400
    assert "non autorisée" in response.json()["detail"]


def test_register_export_and_delete(client, service, mock_llm) -> None:
    analysis_id = _upload(client).json()["analysis_id"]
    service.run(analysis_id, llm=mock_llm())

    register = client.get(f"/api/analysis/{analysis_id}/register")
    assert register.status_code == 200
    assert len(register.json()["risks"]) == 2

    exported = client.get(f"/api/analysis/{analysis_id}/export")
    assert exported.status_code == 200
    body = exported.json()
    assert body["audit_log"]
    assert len(body["register"]) == 2

    assert client.get("/api/analyses").json()["analyses"]
    assert client.delete(f"/api/analysis/{analysis_id}").status_code == 204
    assert client.get(f"/api/analysis/{analysis_id}").status_code == 404


def test_unknown_analysis_is_404(client) -> None:
    assert client.get("/api/analysis/INCONNUE").status_code == 404