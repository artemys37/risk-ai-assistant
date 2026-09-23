"""Routes API — cycle de vie complet d'une analyse de risques.

- Import documentaire
- Lancement de l'analyse multi-agents
- Registre proposé + critique automatique
- Validation humaine (bloquante) → registre final
- Journal d'audit et export
"""

from fastapi import APIRouter, File, HTTPException, UploadFile
from pydantic import BaseModel, Field

from app import __version__
from app.agents.base import AgentError
from app.models.base import NOT_DOCUMENTED
from app.orchestration.workflow import Orchestrator, WorkflowStage
from app.services.analysis_service import AnalysisService
from app.services.document_parser import DocumentParseError
from app.services.llm import LLMError

router = APIRouter(prefix="/api")

_service: AnalysisService | None = None


def service() -> AnalysisService:
    global _service
    if _service is None:
        _service = AnalysisService()
    return _service


def _http_error(exc: Exception) -> HTTPException:
    if isinstance(exc, KeyError):
        return HTTPException(status_code=404, detail=str(exc))
    if isinstance(exc, LLMError):
        return HTTPException(
            status_code=503,
            detail=(
                f"{exc}. Vérifier la configuration LLM (.env) ou démarrer "
                "Ollama localement (LLM_PROVIDER/LLM_MODEL/LLM_BASE_URL)."
            ),
        )
    if isinstance(exc, (AgentError, DocumentParseError, ValueError)):
        return HTTPException(status_code=400, detail=str(exc))
    raise exc


# ---------------------------------------------------------------------------
# Métadonnées
# ---------------------------------------------------------------------------


@router.get("/health")
def health() -> dict:
    """Point de contrôle : l'application répond."""
    return {"status": "ok", "version": __version__}


@router.get("/workflow")
def workflow_stages() -> dict:
    """Retourne les étapes du workflow (visibles dans l'interface)."""
    return {"stages": [stage.value for stage in WorkflowStage]}


@router.get("/meta")
def meta() -> dict:
    """Métadonnées du prototype (état d'avancement)."""
    return {
        "name": "SPRINT — Assistant multi-agents d'analyse de risques",
        "version": __version__,
        "sprint": 5,
        "principle": "IA = ASSISTANCE + TRAÇABILITÉ + VALIDATION HUMAINE",
        "human_decision_required": True,
        "not_documented_marker": NOT_DOCUMENTED,
        "stages_count": len(list(Orchestrator().stages)),
    }


# ---------------------------------------------------------------------------
# Analyse — cycle de vie
# ---------------------------------------------------------------------------


@router.post("/analysis", status_code=201)
async def create_analysis(files: list[UploadFile] = File(...)) -> dict:
    """Importe un ou plusieurs documents et crée une analyse (étape 1)."""
    documents: list[tuple[str, bytes]] = []
    for file in files:
        if not file.filename:
            raise HTTPException(status_code=400, detail="fichier sans nom")
        documents.append((file.filename, await file.read()))
    try:
        state = service().create(documents)
    except Exception as exc:  # noqa: BLE001 — conversion en HTTP
        raise _http_error(exc) from exc
    return {"analysis_id": state.id, "documents": state.documents}


@router.get("/analyses")
def list_analyses() -> dict:
    """Liste des analyses persistées."""
    return {"analyses": service().list_summaries()}


@router.post("/analysis/{analysis_id}/run")
def run_analysis(analysis_id: str) -> dict:
    """Lance le pipeline complet jusqu'au registre proposé."""
    try:
        state = service().run(analysis_id)
    except Exception as exc:  # noqa: BLE001 — conversion en HTTP
        raise _http_error(exc) from exc
    return {"analysis_id": state.id, "status": state.status}


@router.get("/analysis/{analysis_id}")
def get_analysis(analysis_id: str) -> dict:
    """État complet d'une analyse (agents + audit + statut)."""
    try:
        state = service().get(analysis_id)
    except Exception as exc:  # noqa: BLE001
        raise _http_error(exc) from exc
    return Orchestrator.to_dict(state)


@router.delete("/analysis/{analysis_id}", status_code=204)
def delete_analysis(analysis_id: str) -> None:
    try:
        service().delete(analysis_id)
    except Exception as exc:  # noqa: BLE001
        raise _http_error(exc) from exc


# ---------------------------------------------------------------------------
# Registre et validation humaine
# ---------------------------------------------------------------------------


@router.get("/analysis/{analysis_id}/register")
def proposed_register(analysis_id: str) -> dict:
    """Registre des risques proposés + rapport de l'agent critique."""
    try:
        return service().proposed_register(analysis_id)
    except Exception as exc:  # noqa: BLE001
        raise _http_error(exc) from exc


class ValidationRequest(BaseModel):
    """Décision humaine sur un risque proposé."""

    action: str = Field(description="ACCEPT | MODIFY | REJECT")
    user: str = "analyste-demo"
    comment: str | None = None
    probability: int | None = Field(default=None, ge=1, le=5)
    impact: int | None = Field(default=None, ge=1, le=5)
    justification: str | None = None
    recommended_measures: str | None = None
    existing_measures: str | None = None
    residual_risk: str | None = None
    owner: str | None = None


@router.post("/analysis/{analysis_id}/risks/{risk_id}/validate")
def validate_risk(analysis_id: str, risk_id: str, request: ValidationRequest) -> dict:
    """Validation humaine d'un risque (étape 10, bloquante)."""
    try:
        state = service().validate(
            analysis_id,
            risk_id,
            request.action,
            user=request.user,
            comment=request.comment,
            probability=request.probability,
            impact=request.impact,
            justification=request.justification,
            recommended_measures=request.recommended_measures,
            existing_measures=request.existing_measures,
            residual_risk=request.residual_risk,
            owner=request.owner,
        )
    except Exception as exc:  # noqa: BLE001
        raise _http_error(exc) from exc
    risk = service().get_risk(analysis_id, risk_id)
    return {
        "analysis_id": analysis_id,
        "risk_id": risk_id,
        "status": state.status,
        "risk": risk,
    }


# ---------------------------------------------------------------------------
# Transparence
# ---------------------------------------------------------------------------


@router.get("/analysis/{analysis_id}/audit")
def get_audit(analysis_id: str) -> dict:
    """Journal d'audit complet de l'analyse."""
    try:
        entries = service().audit(analysis_id)
    except Exception as exc:  # noqa: BLE001
        raise _http_error(exc) from exc
    return {"analysis_id": analysis_id, "audit_log": entries}


@router.get("/analysis/{analysis_id}/export")
def export(analysis_id: str) -> dict:
    """Export complet (registre + critique + audit) en JSON."""
    try:
        return service().export(analysis_id)
    except Exception as exc:  # noqa: BLE001
        raise _http_error(exc) from exc