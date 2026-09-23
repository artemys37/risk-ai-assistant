"""Interface web (Sprint 5) — FastAPI + Jinja2.

Page d'accueil (import), page d'analyse (étapes, agents, registre proposé,
validation humaine), journal d'audit, registre final et export.
"""

from pathlib import Path

from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from app.agents.base import AgentError
from app.orchestration.workflow import Orchestrator, WorkflowStage
from app.services.analysis_service import AnalysisService
from app.services.document_parser import DocumentParseError
from app.services.llm import LLMError

_TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "frontend" / "templates"

web_router = APIRouter()
templates = Jinja2Templates(directory=str(_TEMPLATES_DIR))

_service: AnalysisService | None = None


def service() -> AnalysisService:
    global _service
    if _service is None:
        _service = AnalysisService()
    return _service


def _friendly_error(exc: Exception) -> HTTPException:
    if isinstance(exc, LLMError):
        return HTTPException(
            status_code=503,
            detail=(
                "Le moteur LLM n'est pas joignable. "
                "Démarrer Ollama (http://localhost:11434) ou configurer "
                "LLM_PROVIDER / LLM_MODEL / LLM_API_KEY dans le fichier .env."
            ),
        )
    if isinstance(exc, KeyError):
        return HTTPException(status_code=404, detail=str(exc))
    if isinstance(exc, (AgentError, DocumentParseError, ValueError)):
        return HTTPException(status_code=400, detail=str(exc))
    raise exc


@web_router.get("/", response_class=HTMLResponse)
def index(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={"stages": [stage.value for stage in WorkflowStage]},
    )


@web_router.get("/analyses", response_class=HTMLResponse)
def list_analyses(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(
        request=request,
        name="analyses.html",
        context={"analyses": service().list_summaries()},
    )


@web_router.post("/upload")
async def upload_documents(request: Request, files: list[UploadFile] = File(...)):
    """Importe les documents puis lance l'analyse complète."""
    documents: list[tuple[str, bytes]] = []
    for file in files:
        if not file.filename:
            continue
        documents.append((file.filename, await file.read()))
    if not documents:
        raise HTTPException(status_code=400, detail="aucun fichier sélectionné")
    try:
        state = service().create(documents)
        state = service().run(state.id)
    except Exception as exc:  # noqa: BLE001
        raise _friendly_error(exc) from exc
    return RedirectResponse(
        url=f"/analysis/{state.id}", status_code=303
    )


@web_router.post("/analysis/{analysis_id}/rerun")
def rerun_analysis(analysis_id: str):
    try:
        service().run(analysis_id)
    except Exception as exc:  # noqa: BLE001
        raise _friendly_error(exc) from exc
    return RedirectResponse(url=f"/analysis/{analysis_id}", status_code=303)


def _analysis_context(state) -> dict:
    """Prépare les données d'affichage de la page d'analyse."""
    from app.services.risk_scoring import score_label
    from app.services.analysis_service import risk_public
    from app.models.risk import RiskStatus

    critic = state.critic_report.model_dump(mode="json") if state.critic_report else None
    risks = []
    for risk in state.risks:
        risk_dict = risk_public(risk)
        risk_dict["score_label"] = score_label(risk.score)
        risks.append(risk_dict)

    agents_output = {
        "extraction": (
            state.extraction.model_dump(mode="json") if state.extraction else None
        ),
        "assets": [asset.model_dump(mode="json") for asset in state.assets],
        "threats": [threat.model_dump(mode="json") for threat in state.threats],
        "vulnerabilities": [
            vuln.model_dump(mode="json") for vuln in state.vulnerabilities
        ],
        "scenarios": [
            scenario.model_dump(mode="json") for scenario in state.scenarios
        ],
    }

    stage_index = 0
    for i, stage in enumerate(WorkflowStage):
        if state.status == stage.value:
            stage_index = i + 1
    if state.status == WorkflowStage.FINAL_REGISTER.value:
        stage_index = len(WorkflowStage)

    return {
        "analysis_id": state.id,
        "status": state.status,
        "status_label": _status_hint(state.status),
        "stage_index": stage_index,
        "stages": [stage.value for stage in WorkflowStage],
        "agents_output": agents_output,
        "critic": critic,
        "risks": risks,
        "pending_count": sum(
            1 for r in state.risks if r.status is RiskStatus.PROPOSED_BY_AI
        ),
        "finalized": state.status == WorkflowStage.FINAL_REGISTER.value,
        "audit_count": len(state.audit),
    }


def _status_hint(status: str) -> str:
    return {
        "1. Import de la documentation": "Documents importés — analyse non lancée.",
        "9. Registre des risques proposé": (
            "Registre proposé par l'IA — en attente de validation humaine."
        ),
        "10. Validation humaine": "Validation humaine en cours.",
        "11. Registre final": "Registre final — toutes les décisions sont humaines.",
    }.get(status, status)


@web_router.get("/analysis/{analysis_id}", response_class=HTMLResponse)
def analysis_page(request: Request, analysis_id: str) -> HTMLResponse:
    try:
        state = service().get(analysis_id)
    except Exception as exc:  # noqa: BLE001
        raise _friendly_error(exc) from exc
    context = _analysis_context(state)
    context["error"] = request.query_params.get("error")
    context["flashed"] = request.query_params.get("flashed")
    return templates.TemplateResponse(
        request=request, name="analysis.html", context=context
    )


@web_router.post("/analysis/{analysis_id}/risks/{risk_id}/validate")
def validate_web(
    analysis_id: str,
    risk_id: str,
    action: str = Form(...),
    user: str = Form("analyste-demo"),
    comment: str = Form(""),
    probability: int | None = Form(None),
    impact: int | None = Form(None),
    justification: str = Form(""),
    recommended_measures: str = Form(""),
    owner: str = Form(""),
):
    """Validation humaine via formulaire web (ACCEPT | MODIFY | REJECT)."""
    try:
        service().validate(
            analysis_id,
            risk_id,
            action,
            user=user,
            comment=comment or None,
            probability=probability,
            impact=impact,
            justification=justification or None,
            recommended_measures=recommended_measures or None,
            owner=owner or None,
        )
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=str(exc))
    return RedirectResponse(
        url=f"/analysis/{analysis_id}?flashed=risque+{risk_id}+mis+à+jour",
        status_code=303,
    )


@web_router.get("/analysis/{analysis_id}/audit", response_class=HTMLResponse)
def audit_page(request: Request, analysis_id: str) -> HTMLResponse:
    try:
        entries = service().audit(analysis_id)
    except Exception as exc:  # noqa: BLE001
        raise _friendly_error(exc) from exc
    return templates.TemplateResponse(
        request=request,
        name="audit.html",
        context={"analysis_id": analysis_id, "entries": entries},
    )


@web_router.get("/register/{analysis_id}", response_class=HTMLResponse)
def register_page(request: Request, analysis_id: str) -> HTMLResponse:
    try:
        data = service().export(analysis_id)
    except Exception as exc:  # noqa: BLE001
        raise _friendly_error(exc) from exc
    return templates.TemplateResponse(
        request=request,
        name="register.html",
        context={"analysis_id": analysis_id, "data": data},
    )


@web_router.get("/export/{analysis_id}")
def export_web(analysis_id: str):
    try:
        data = service().export(analysis_id)
    except Exception as exc:  # noqa: BLE001
        raise _friendly_error(exc) from exc
    return JSONResponse(
        content=data,
        headers={"Content-Disposition": f'attachment; filename="registre-{analysis_id}.json"'},
    )