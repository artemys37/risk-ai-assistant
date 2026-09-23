# Architecture technique

## 1. Architecture globale

```
                    ┌──────────────────────┐
                    │      UTILISATEUR     │
                    │  Analyste sécurité   │
                    └──────────┬───────────┘
                               │
                               ▼
                    ┌──────────────────────┐
                    │   INTERFACE WEB      │
                    │  FastAPI + Jinja2    │
                    └──────────┬───────────┘
                               │
                               ▼
                    ┌──────────────────────┐      ┌─────────────────┐
                    │    ORCHESTRATEUR     │◄────►│  SQLite /       │
                    │  workflow.py (11     │      │  Journal audit  │
                    │  étapes)             │      └─────────────────┘
                    └──────────┬───────────┘
                               │
        ┌──────────────────────┼────────────────────────┐
        │                      │                        │
        ▼                      ▼                        ▼
┌───────────────┐      ┌────────────────┐      ┌────────────────┐
│ Agent         │      │ Agent          │      │ Agent          │
│ Documentation │────► │ Actifs         │────► │ Menaces        │
└───────┬───────┘      └───────┬────────┘      └───────┬────────┘
        │                      │                       │
        └──────────────────────┼───────────────────────┘
                               ▼
                     ┌────────────────────┐
                     │ Agent Vulnérabilités│
                     └──────────┬─────────┘
                                ▼
                     ┌────────────────────┐
                     │ Agent Scénarios    │
                     └──────────┬─────────┘
                                ▼
                     ┌────────────────────┐
                     │ Agent Évaluation   │
                     └──────────┬─────────┘
                                ▼
                     ┌────────────────────┐      ┌─────────────────┐
                     │ Agent Critique     │◄────►│ Source Tracker  │
                     │ (obligatoire)      │      └─────────────────┘
                     └──────────┬─────────┘
                                ▼
                     ┌────────────────────┐
                     │ REGISTRE PROPOSÉ   │  statut : PROPOSÉ PAR IA
                     │ human_validation=  │  human_validation : PENDING
                     │ PENDING            │
                     └──────────┬─────────┘
                                ▼
                     ┌────────────────────┐
                     │ VALIDATION HUMAINE │  ACCEPTER / MODIFIER / REJETER
                     │ (bloquante)        │
                     └──────────┬─────────┘
                                ▼
                     ┌────────────────────┐
                     │ REGISTRE FINAL     │  + journal d'audit complet
                     └────────────────────┘

     ┌──────────────────────────────────────────────────┐
     │  LLM (fournisseur configurable via .env)         │
     │  LLM_PROVIDER / LLM_MODEL / LLM_API_KEY          │
     │  appelé uniquement par les agents, jamais par    │
     │  l'interface directement                         │
     └──────────────────────────────────────────────────┘

     ┌──────────────────────────────────────────────────┐
     │  DOCUMENTS IMPORTÉS (PDF/TXT/DOCX/MD/JSON/CSV)   │
     │  traités comme DONNÉES NON FIABLES               │
     │  (protection prompt injection)                   │
     └──────────────────────────────────────────────────┘
```

## 2. Rôle de chaque agent

| # | Agent | Fichier | Entrée | Sortie | Sprint |
|---|---|---|---|---|---|
| 1 | Documentation | `app/agents/documentation_agent.py` | Documents bruts | Extraction structurée + sources (`DOC-XXX`) | 2 |
| 2 | Actifs | `app/agents/asset_agent.py` | Extraction | `list[Asset]` (`ACT-XXX`) | 2 |
| 3 | Menaces | `app/agents/threat_agent.py` | Assets + extraction | `list[Threat]` (`THR-XXX`) | 2 |
| 4 | Vulnérabilités | `app/agents/vulnerability_agent.py` | Assets + menaces | `list[Vulnerability]` (`VUL-XXX`) | 2 |
| 5 | Scénarios | `app/agents/risk_scenario_agent.py` | Actif + menace + vuln. | `list[RiskScenario]` (`RSK-XXX`) | 3 |
| 6 | Évaluation | `app/agents/risk_assessment_agent.py` | Scénarios | `list[Risk]` (score = P × I) | 3 |
| 7 | Critique | `app/agents/critic_agent.py` | Analyse complète | `CriticReport` (PASS / REVIEW_REQUIRED / REJECT) | 4 |

### Règles transversales à tous les agents

1. **Ne jamais inventer** de faits, de sources ou de technologies.
2. Information absente → `Non documenté` (`NOT_DOCUMENTED`).
3. Chaque affirmation porte un `evidence_type` : `FAIT DOCUMENTÉ` / `INFERENCE` / `HYPOTHÈSE`.
4. Chaque résultat porte un `confidence` : `HIGH` / `MEDIUM` / `LOW` (niveau estimé, pas une probabilité statistique).
5. Les sources (`DOC-XXX`) sont conservées de bout en bout.
6. Tout résultat finit par l'**agent critique** avant d'atteindre le registre proposé.

## 3. Communication entre agents

- **Sprint 1** : contrats typés via Pydantic — chaque agent reçoit et retourne
  des modèles validés.
- **Sprints 2-5 (implémenté)** : enchaînement explicite par un orchestrateur
  Python (`app/orchestration/workflow.py`) :
  - un nœud = un agent, dans l'ordre des 11 étapes ;
  - l'état partagé (`AnalysisState`) porte documents, extraction, assets,
    threats, vulnerabilities, scenarios, risks, critic_report, audit ;
  - la validation humaine est **bloquante** (étape 10) : aucun risque ne
    devient final sans décision de l'analyste ;
  - chaque étape est journalisée (`AuditEntry`) et l'état est persisté en
    SQLite (`app/services/storage.py`).

### Choix d'implémentation (vs LangGraph, CrewAI, AutoGen)

| Critère du cahier des charges | Orchestrateur Python | LangGraph | CrewAI | AutoGen |
|---|---|---|---|---|
| Contrôle précis des étapes | ✅ explicite, aucune dépendance | ✅ graphe explicite | ⚠️ implicite | ⚠️ conversation libre |
| Interruption / human-in-the-loop natif | ✅ humain bloquant intégré | ✅ `interrupt` | ⚠️ à bricoler | ⚠️ à bricoler |
| Traçabilité par nœud | ✅ state + audit | ✅ state + checkpointing | ⚠️ limité | ⚠️ limité |
| Charge technique du prototype | ✅ stdlib + Pydantic | nécessite LangGraph | nécessite CrewAI | nécessite AutoGen |

Le cahier des charges privilégie « une architecture permettant de contrôler
précisément les étapes et les validations ». Pour le prototype, un
orchestrateur Python explicite est retenu : le graphe reste trivial (11 nœuds
séquentiels), et aucun outil externe n'est requis. Une migration vers
LangGraph reste possible sans refonte des agents (contrats Pydantic identiques).

## 4. Orchestration

Fichier : `app/orchestration/workflow.py`

```python
class WorkflowStage(str, Enum):
    IMPORT                = "1. Import de la documentation"
    EXTRACTION            = "2. Extraction documentaire"
    ASSETS                = "3. Identification des actifs"
    THREATS               = "4. Identification des menaces"
    VULNERABILITIES       = "5. Identification des vulnérabilités"
    SCENARIOS             = "6. Construction des scénarios"
    ASSESSMENT            = "7. Évaluation Probabilité × Impact"
    CRITIQUE              = "8. Critique automatique"
    PROPOSED_REGISTER     = "9. Registre des risques proposé"
    HUMAN_VALIDATION      = "10. Validation humaine"
    FINAL_REGISTER        = "11. Registre final"
```

Responsabilités de l'orchestrateur :

- enchaîner les agents dans l'ordre ;
- **journaliser chaque étape** (`AuditEntry` : timestamp, agent, action, input,
  output, source, confidence, human_validation) ;
- **bloquer** le passage au registre final tant que l'étape 10 n'est pas décidée
  par un humain ;
- persister l'état (SQLite, migrable PostgreSQL via SQLAlchemy).

## 5. Human-in-the-loop

```
Risque proposé (PROPOSÉ PAR IA, PENDING)
       ↓
Vérification IA (agent critique → PASS / REVIEW_REQUIRED / REJECT)
       ↓
Validation analyste : ACCEPTER | MODIFIER | REJETER
       ↓
Modification éventuelle (proba, impact, justification, commentaire)
       ↓
Validation finale → VALIDÉ / MODIFIÉ / REJETÉ PAR HUMAIN + entrée audit
```

L'interface (Sprint 5) rend obligatoire cette étape : aucun endpoint ne permet
de passer un risque de `PROPOSÉ PAR IA` à un statut final sans action humaine
explicite.

## 6. Flux de données et stockage

| Donnée | Lieu | Format |
|---|---|---|
| Documents importés | `uploads/` (hors Git) | fichiers bruts |
| Extraction, actifs, menaces, vuln., scénarios, risques | `data/risk_ai.db` | SQLite → PostgreSQL |
| Journal d'audit | table `audit_log` | `AuditEntry` (JSON serializable) |
| Registre final | export CSV / JSON | colonnes du §12 du cahier des charges |
| Configuration | `.env` (jamais Git) | variables d'environnement |

## 7. Séparation des contextes LLM (prompt injection)

Quatre zones strictement séparées dans chaque appel LLM :

1. **SYSTEM INSTRUCTIONS** — règles du projet (écrites par nous) ;
2. **USER INSTRUCTIONS** — demande de l'analyste ;
3. **DOCUMENT CONTENT** — contenu des documents, délimité par
   `<<<DEBUT_DOCUMENT_NON_FIABLE>>>` / `<<<FIN_DOCUMENT_NON_FIABLE>>>`
   (voir `app/services/document_parser.py`) ;
4. **AGENT OUTPUT** — JSON structuré validé par Pydantic.

Aucune instruction provenant d'un document n'est exécutée.

## 8. Stack technique résumée

- Python 3.11+, FastAPI, Uvicorn, Pydantic v2
- Orchestrateur Python explicite (agents, Sprints 2-5) — migration LangGraph possible
- LLM configurable : `LLM_PROVIDER` / `LLM_MODEL` / `LLM_API_KEY` / `LLM_BASE_URL`
- SQLite (stdlib `sqlite3`) — SQLAlchemy + Alembic en migration PostgreSQL
- pypdf + python-docx (parsing, Sprint 2)
- FastAPI + Jinja2 (frontend démonstration, Sprint 5)
- pytest + httpx (tests)
