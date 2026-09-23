"""Point d'entrée FastAPI — SPRINT, assistant multi-agents d'analyse de risques.

Lancement :
    uvicorn app.main:app --reload --env-file .env
"""

from fastapi import FastAPI

from app import __version__
from app.api.routes import router
from app.web import web_router

app = FastAPI(
    title="SPRINT — Assistant multi-agents d'analyse de risques",
    description=(
        "Système multi-agents IA d'assistance à l'analyse de risques "
        "cybersécurité. L'IA propose, l'humain décide : aucune décision "
        "finale n'est prise sans validation humaine."
    ),
    version=__version__,
)

app.include_router(web_router)
app.include_router(router)


@app.get("/api")
def api_root() -> dict:
    return {
        "name": "SPRINT — Risk AI Assistant",
        "version": __version__,
        "api_docs": "/docs",
        "health": "/api/health",
        "web": "/",
    }