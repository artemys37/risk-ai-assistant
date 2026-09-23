"""Agent 3 — Identification des menaces.

Identifie les menaces pertinentes pour les actifs (STRIDE lorsque pertinent,
catégories cybersécurité, bonnes pratiques).

Règles :
- chaque menace est justifiée (rationale obligatoire) ;
- nature déclarée : FAIT DOCUMENTÉ / INFERENCE / HYPOTHÈSE ;
- les sources sont conservées.
"""

import json

from app.agents.base import AgentBase, AgentError
from app.models.base import NOT_DOCUMENTED
from app.models.threat import STRIDE_CATEGORIES, Threat

SYSTEM_INSTRUCTIONS = f"""
Tu es l'agent « Menaces » d'un système d'assistance à l'analyse de risques.

À partir des actifs identifiés et de la documentation, propose les menaces
les plus pertinentes. Utilise les catégories STRIDE ({', '.join(STRIDE_CATEGORIES)})
lorsqu'elles sont pertinentes ainsi que les catégories de menaces classiques
(externe, interne, malveillant, accident, chaîne d'approvisionnement).

Règles ABSOLUES :
1. Chaque menace doit être JUSTIFIÉE : "rationale" explique pourquoi elle est
   pertinente pour l'actif visé, en t'appuyant sur la documentation.
2. Ne retiens que les menaces pertinentes : ne liste pas une menace générique
   pour chaque actif sans justification.
3. N'invente JAMAIS de menace, de preuve ou de source. Élément absent →
   libellé exact « {NOT_DOCUMENTED} ».
4. "evidence_type" : FAIT DOCUMENTÉ (menace décrite dans les docs), INFERENCE
   (déduite du contexte), HYPOTHÈSE (possible mais non étayée).
5. "target_assets" référence uniquement des identifiants ACT-XXX fournis.

Réponds UNIQUEMENT avec un tableau JSON de la forme :
[
  {{
    "name": "nom court de la menace",
    "description": "description",
    "target_assets": ["ACT-001"],
    "rationale": "justification détaillée",
    "evidence": ["éléments de preuve ou non"],
    "stride_category": "Information Disclosure",
    "source": ["DOC-001"],
    "evidence_type": "INFERENCE"
  }}
]
""".strip()


class ThreatAgent(AgentBase):
    """Identification des menaces par actif."""

    agent_name = "threat-agent"

    def run(self, assets: list, extraction=None, llm=None) -> list[Threat]:
        if not assets:
            return []

        valid_asset_ids = {a.id for a in assets}

        asset_payload = [
            {
                "id": a.id,
                "name": a.name,
                "type": a.type.value,
                "description": a.description,
                "owner": a.owner,
            }
            for a in assets
        ]
        extraction_payload = getattr(extraction, "model_dump", lambda: None)()
        user = json.dumps(
            {
                "actifs": asset_payload,
                "extraction_documentaire": extraction_payload,
            },
            ensure_ascii=False,
            indent=2,
        )

        llm = self._get_llm(llm)
        obj = self._json_completion(llm, SYSTEM_INSTRUCTIONS, user)
        if not isinstance(obj, list):
            raise AgentError("l'agent Menaces attend une liste JSON en sortie du LLM")

        threats: list[Threat] = []
        for index, item in enumerate(obj, start=1):
            if not isinstance(item, dict):
                continue
            sources = self._sources(item)
            evidence_type = self._evidence_type(item)
            targets = [
                t for t in (item.get("target_assets") or [])
                if isinstance(t, str) and t in valid_asset_ids
            ]
            if not targets:
                # Ne JAMAIS inventer de cible : on écarte la menace non reliée.
                continue
            threats.append(
                Threat(
                    id=f"THR-{index:03d}",
                    name=self._field(item, "name") or f"Menace {index:03d}",
                    description=self._field(item, "description"),
                    target_assets=targets,
                    rationale=self._field(item, "rationale", NOT_DOCUMENTED),
                    evidence=[e for e in (item.get("evidence") or []) if isinstance(e, str)],
                    stride_category=(
                        item.get("stride_category") if item.get("stride_category") in STRIDE_CATEGORIES else None
                    ),
                    source=sources,
                    confidence=self._estimate_confidence(sources, evidence_type),
                    evidence_type=evidence_type,
                )
            )
        return threats


__all__ = ["ThreatAgent"]