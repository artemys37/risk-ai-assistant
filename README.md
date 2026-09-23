# SPRINT — Système multi-agents IA pour l'analyse de risques cybersécurité

## Problématique

Une analyse de risques classique nécessite beaucoup de documentation, comporte de
nombreuses étapes répétitives, requiert des compétences spécialisées et peut prendre
plusieurs jours. Elle doit être mise à jour à chaque évolution du système.

## Objectif

Prototype multi-agents capable de : collecter et analyser la documentation, identifier
actifs / menaces / vulnérabilités, construire des scénarios, évaluer les risques
(Probabilité × Impact), produire un registre argumenté — **avec validation humaine
obligatoire et traçabilité complète**.

> **Principe fondamental : IA = ASSISTANCE + TRAÇABILITÉ + VALIDATION HUMAINE.**
> Le système est un assistant. Il ne présente jamais ses résultats comme des vérités
> définitives. L'humain reste responsable de la validation finale.

## Architecture (aperçu)

```
Utilisateur (analyste)
        │
        ▼
 Orchestrateur ──► Agent Documentation ─► Agent Actifs ─► Agent Menaces
                                                              │
        ┌─────────────────────────────────────────────────────┘
        ▼
 Agent Vulnérabilités ─► Agent Scénarios ─► Agent Évaluation ─► Agent Critique
                                                                  │
                                                                  ▼
                                                    Registre PROPOSÉ (statut IA)
                                                                  │
                                                                  ▼
                                                    VALIDATION HUMAINE (bloquante)
                                                                  │
                                                                  ▼
                                                    Registre FINAL + journal d'audit
```

Détails complets : [docs/architecture.md](docs/architecture.md)
Méthodologie : [docs/methodology.md](docs/methodology.md)

## Technologies utilisées

| Catégorie | Choix |
|---|---|
| Langage | Python 3.11+ |
| Backend | FastAPI + Uvicorn |
| Modèles | Pydantic v2 |
| Framework multi-agents | Orchestrateur explicite 11 étapes (Python pur) |
| LLM | Configurable via `.env` (`LLM_PROVIDER`, `LLM_MODEL`, `LLM_API_KEY`) |
| Base de données | SQLite (stdlib `sqlite3`, migrable PostgreSQL) |
| Frontend | FastAPI + Jinja2 (Sprint 5) |
| Tests | pytest |

Aucune clé API n'est présente dans le dépôt. Configuration via `.env` (modèle : `.env.example`).

## Installation

```bash
git clone <votre-depot>/risk-ai-assistant.git
cd risk-ai-assistant

python -m venv .venv
source .venv/bin/activate        # Windows : .venv\Scripts\activate

pip install -r requirements.txt
cp .env.example .env             # puis renseigner LLM_* si nécessaire
```

## Lancement

```bash
uvicorn app.main:app --env-file .env
```

- Interface web (import, analyse, validation humaine, registre final) : http://127.0.0.1:8000/
- API interactive : http://127.0.0.1:8000/docs
- Santé : http://127.0.0.1:8000/api/health

## Tests

```bash
pytest -v
```

## Exemple d'utilisation

**État : Sprints 1-5 opérationnels.** Le pipeline complet tourne de bout en
bout : import → extraction → actifs → menaces → vulnérabilités → scénarios →
cotation (P × I) → critique automatique → registre proposé → **validation
humaine obligatoire** → registre final + journal d'audit.

### Sans clé API (mode démo)

L'exécution la plus rapide sans aucun secret : un LLM *mock* joué par les
tests, ou Ollama en local (`LLM_PROVIDER=ollama`,
`LLM_BASE_URL=http://localhost:11434`, `LLM_MODEL=llama3.1`). L'évaluation des
risques dispose d'un **repli déterministe** (probabilité dérivée du statut de
certitude, impact dérivé de la catégorie d'actif) : si le LLM est injoignable,
la cotation reste proposée et traçable — la validation humaine décide.

### Utilisation programmatique

```python
from app.services.analysis_service import AnalysisService
from app.orchestration.workflow import Orchestrator

service = AnalysisService()
state   = service.create([("systeme.md", CONTENU_BYTES)])   # étape 1 : import
state   = service.run(state.id)                              # étapes 2-9 : pipeline complet

# Registre proposé + rapport de l'agent critique
register = service.proposed_register(state.id)

# Validation humaine (étape 10, bloquante)
state = service.validate(state.id, "RSK-001", "ACCEPT", user="analyste", comment="Conforme.")
state = service.validate(state.id, "RSK-002", "MODIFY",
                         probability=4, impact=5,
                         justification="Risque surexposé : surestimation à revoir à la hausse.")

# Registre final + export
final   = service.export(state.id)
audit   = service.audit(state.id)
```

Usage par agent (LLM injecté, sinon config `.env`) :

```python
from app.services.document_parser import load_documents
from app.services.llm import LLMClient
from app.agents.documentation_agent import DocumentationAgent
from app.agents.asset_agent import AssetAgent
from app.agents.threat_agent import ThreatAgent
from app.agents.vulnerability_agent import VulnerabilityAgent

documents = load_documents([("systeme.md", CONTENU_BYTES)])
llm = LLMClient()  # configure via .env (LLM_PROVIDER, LLM_MODEL, LLM_API_KEY)

extraction  = DocumentationAgent().run(documents, llm=llm)
assets      = AssetAgent().run(extraction, llm=llm)
threats     = ThreatAgent().run(assets, extraction, llm=llm)
vulns       = VulnerabilityAgent().run(assets, threats, extraction, llm=llm)
```

Chaque actif contient une référence `source=["DOC-001"]` ; une information
absente vaut `Non documenté` ; les vulnérabilités portent un statut de
certitude (`CONFIRMÉE` / `POTENTIELLE` / `À VÉRIFIER` / `NON ÉTABLIE`) ;
chaque risque est crée avec le statut `PROPOSÉ PAR IA` et la validation
`PENDING`.

## Limites du système (v1)

- L'IA peut se tromper : hallucinations, interprétation erronée, manque de
  contexte métier — d'où l'agent critique et la validation humaine obligatoires.
- Aucun score n'est produit sans justification ; toute information absente est
  marquée `Non documenté`.
- Le contenu des documents analysés est non fiable (protection prompt injection) :
  aucune instruction issue d'un document n'est exécutée.
- Le prototype utilise des données de démonstration non sensibles.

## Responsabilité humaine

Toute proposition d'agent est créée avec le statut `PROPOSÉ PAR IA` et la
validation `PENDING`. Seul un analyste humain peut accepter, modifier ou rejeter
un risque ; chaque décision est journalisée (timestamp, agent, action, sources,
confiance, validation humaine).

## Structure du projet

```
risk-ai-assistant/
├── app/
│   ├── main.py                  # Point d'entrée FastAPI
│   ├── web.py                   # Interface web (import, validation, registre)
│   ├── agents/                  # 7 agents spécialisés
│   ├── orchestration/workflow.py# Orchestrateur (11 étapes) + validation humaine
│   ├── models/                  # Modèles de domaine (Pydantic)
│   ├── services/                # Parsing, cotation, sources, persistance, service
│   └── api/routes.py            # Routes HTTP (import, analyse, validation, audit)
├── frontend/
│   ├── templates/               # Pages Jinja2 (index, analyse, audit, registre)
│   └── README.md
├── tests/                       # pytest (147 tests)
├── docs/                        # architecture, méthodologie, évaluation, sécurité
├── examples/example_system/     # Jeu de démonstration (systeme.md)
└── data/                        # SQLite local (data/risk_ai.db, ignoré par Git)
```

## Outils et technologies utilisés

- **Langage** : Python 3.11+
- **Backend** : FastAPI, Uvicorn
- **Multi-agents** : orchestrateur Python explicite (11 étapes, sans dép.
  supplémentaire)
- **LLM** : configurable (OpenAI / Anthropic / Ollama… via variables
  d'environnement)
- **Base de données** : SQLite (stdlib `sqlite3`)
- **Traitement documentaire** : pypdf, python-docx
- **Frontend** : FastAPI + Jinja2
- **Tests** : pytest, httpx
