"""Tests de l'interface web (Sprint 5) — pages rendues par Jinja2."""

CONTENT = b"## Systeme RH\nApplication web interne. Serveur Linux, PostgreSQL.\n"


def _setup(client, service) -> str:
    """Importe + analyse via API/back et retourne l'identifiant."""
    response = client.post(
        "/api/analysis", files={"files": ("systeme.md", CONTENT, "text/markdown")}
    )
    analysis_id = response.json()["analysis_id"]
    service.run(analysis_id)
    return analysis_id


def _upload_redirect(client):
    return client.post(
        "/upload",
        files={"files": ("systeme.md", CONTENT, "text/markdown")},
        follow_redirects=False,
    )


def test_index_page_renders(client) -> None:
    response = client.get("/")
    assert response.status_code == 200
    assert "Importez la documentation" in response.text
    assert "Workflow en 11 étapes" in response.text


def test_upload_redirects_to_analysis(client) -> None:
    response = _upload_redirect(client)
    assert response.status_code == 303
    assert "/analysis/" in response.headers["location"]


def test_analysis_page_renders(client, service) -> None:
    analysis_id = _setup(client, service)
    page = client.get(f"/analysis/{analysis_id}")
    assert page.status_code == 200
    assert "Registre des risques proposés" in page.text
    assert f"Analyse {analysis_id}" in page.text


def test_web_validation_form(client, service) -> None:
    analysis_id = _setup(client, service)
    page = client.post(
        f"/analysis/{analysis_id}/risks/RSK-001/validate",
        data={"action": "REJECT", "comment": "Non justifié."},
        follow_redirects=False,
    )
    assert page.status_code == 303
    state = client.get(f"/api/analysis/{analysis_id}").json()
    assert state["risks"][0]["status"] == "REJETÉ PAR HUMAIN"


def test_audit_page_renders(client, service) -> None:
    analysis_id = _setup(client, service)
    page = client.get(f"/analysis/{analysis_id}/audit")
    assert page.status_code == 200
    assert "Journal d'audit" in page.text
    assert "DOCUMENT_EXTRACTION" in page.text


def test_register_page_renders(client, service) -> None:
    analysis_id = _setup(client, service)
    page = client.get(f"/register/{analysis_id}")
    assert page.status_code == 200
    assert "Registre des risques" in page.text


def test_export_download(client, service) -> None:
    analysis_id = _setup(client, service)
    response = client.get(f"/export/{analysis_id}")
    assert response.status_code == 200
    assert response.json()["analysis_id"] == analysis_id


def test_message_when_upload_fails_without_file(client) -> None:
    response = client.post("/upload", files={})
    assert response.status_code in (400, 422)