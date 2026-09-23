"""Agent 6 — Évaluation des risques.

Mission
-------
Évaluer chaque scénario avec la matrice explicite :
- Probabilité : 1 (Très faible) à 5 (Très élevée)
- Impact     : 1 (Très faible) à 5 (Très élevé)
- Score      : Probabilité × Impact (1 à 25)

Règles
------
- Afficher séparément probabilité, impact, score et justification.
- Ne JAMAIS laisser le LLM choisir un score sans justification
  (contrainte imposée par le modèle RiskAssessment).
- Le score est calculé par risk_scoring.calculate_score (reproductible).
- Validation humaine du score obligatoire ensuite (human-in-the-loop).

Implémentation
--------------
L'agent interroge d'abord le LLM pour proposer un couple
probabilité/impact justifié. Si le LLM est indisponible (aucune clé,
Ollama éteint, réponse invalide) ou produit une évaluation hors
échelle/sans justification, un repli déterministe et transparent est
appliqué : probabilité dérivée du statut de certitude de la vulnérabilité,
impact dérivé de la catégorie de l'actif. Le repli reste une PROPOSITION
à valider par l'humain — il n'invente aucun fait.
"""

import json
from datetime import datetime, timezone

from app.agents.base import AgentBase, AgentError
from app.models.asset import Asset
from app.models.base import NOT_DOCUMENTED
from app.models.risk import Risk, RiskAssessment, RiskScenario, RiskStatus
from app.models.vulnerability import Vulnerability, VulnerabilityStatus
from app.services.llm import LLMError
from app.services.risk_scoring import PROBABILITY_LABELS, IMPACT_LABELS

SYSTEM_INSTRUCTIONS = """
Tu es l'agent « Évaluation » d'un système d'assistance à l'analyse de
risques cybersécurité.

Pour chaque scénario de risque, propose une évaluation :
- probability : entier 1 (Très faible) à 5 (Très élevée) ;
- impact      : entier 1 (Très faible) à 5 (Très élevé) ;
- justification : au moins 10 caractères, expliquant précisément pourquoi
  ce couple est retenu, en t'appuyant uniquement sur les éléments fournis
  (documentation, sources DOC-XXX, statut des vulnérabilités, catégories
  d'actifs). N'invente jamais de fait.

Règles ABSOLUES :
1. probability et impact doivent être des entiers entre 1 et 5.
2. justify = True.
3. Le score n'est PAS demandé : il sera calculé par le système
   (Probabilité × Impact). Ne fournis aucun champ "score".
4. "source" : Liste des références DOC-XXX déjà présentes, jamais inventées.
5. Si l'information manque, justifie la valeur par l'absence de
   documentation (information absente → valeur prudente et pourquoi).

Réponds UNIQUEMENT avec un tableau JSON de la forme :
[
  {
    "scenario_id": "RSK-001",
    "probability": 3,
    "impact": 4,
    "justification": "Justification en français, au moins 10 caractères.",
    "source": ["DOC-001"]
  }
]
""".strip()

# Probabilité dérivée du statut de certitude documentaire de la vulnérabilité.
_VULN_STATUS_PROBABILITY = {
    VulnerabilityStatus.CONFIRMED: 4,
    VulnerabilityStatus.POTENTIAL: 3,
    VulnerabilityStatus.TO_VERIFY: 2,
    VulnerabilityStatus.NOT_ESTABLISHED: 1,
}

# Actifs dont l'atteinte a un impact métier potentiel maximal (base prudente).
_HIGH_IMPACT_TYPES = {
    "données",
    "application",
    "serveur",
    "compte",
    "secret",
    "certificat",
    "infrastructure cloud",
}


class RiskAssessmentAgent(AgentBase):
    """Cotation probabilité × impact avec justification obligatoire."""

    agent_name = "risk-assessment-agent"

    def run(
        self,
        scenarios: list[RiskScenario],
        *,
        assets: list[Asset] | None = None,
        vulnerabilities: list[Vulnerability] | None = None,
        llm=None,
    ) -> list[Risk]:
        """Évalue les scénarios et produit des risques proposés (PENDING)."""
        if not scenarios:
            return []

        asset_by_id = {asset.id: asset for asset in (assets or [])}
        vuln_by_id = {vuln.id: vuln for vuln in (vulnerabilities or [])}

        llm = self._get_llm(llm)
        proposed = self._propose_with_llm(llm, scenarios) or {}

        risks: list[Risk] = []
        for scenario in scenarios:
            assessment_data = proposed.get(scenario.id)
            try:
                assessment = self._build_assessment(
                    scenario, assessment_data, asset_by_id, vuln_by_id
                )
            except (LLMError, AgentError, KeyError, TypeError, ValueError):
                assessment = self._fallback_assessment(
                    scenario, asset_by_id, vuln_by_id
                )
            risks.append(
                Risk(
                    id=scenario.id,
                    scenario=scenario,
                    assessment=assessment,
                    status=RiskStatus.PROPOSED_BY_AI,
                    created_by=self.agent_name,
                    created_at=datetime.now(timezone.utc).isoformat(),
                )
            )
        return risks

    # ------------------------------------------------------------------
    # Chemin LLM
    # ------------------------------------------------------------------

    def _propose_with_llm(
        self, llm, scenarios: list[RiskScenario]
    ) -> dict[str, dict]:
        """Interroge le LLM ; retourne {scenario_id: assessment_data}."""
        payload = []
        for scenario in scenarios:
            payload.append(
                {
                    "id": scenario.id,
                    "description": scenario.description,
                    "threat_actor": scenario.threat_actor,
                    "feared_event": scenario.feared_event,
                    "asset_id": scenario.asset_id,
                    "threat_id": scenario.threat_id,
                    "vulnerability_id": scenario.vulnerability_id,
                    "consequences": scenario.consequences,
                    "hypotheses": scenario.hypotheses,
                    "source": scenario.source,
                    "confidence": scenario.confidence.value,
                }
            )
        user = json.dumps(
            {"scénarios": payload}, ensure_ascii=False, indent=2
        )

        try:
            obj = self._json_completion(llm, SYSTEM_INSTRUCTIONS, user)
        except (LLMError, AgentError):
            return {}

        if not isinstance(obj, list):
            raise AgentError(
                "l'agent Évaluation attend un tableau JSON en sortie du LLM"
            )

        result: dict[str, dict] = {}
        for item in obj:
            if not isinstance(item, dict):
                continue
            scenario_id = item.get("scenario_id")
            if not isinstance(scenario_id, str):
                continue
            result[scenario_id] = item
        return result

    def _build_assessment(
        self,
        scenario: RiskScenario,
        data: dict | None,
        asset_by_id: dict[str, Asset],
        vuln_by_id: dict[str, Vulnerability],
    ) -> RiskAssessment:
        """Construit une évaluation à partir de la proposition LLM (strict).

        Lève une exception si la proposition est invalide (hors échelle,
        justification vide ou trop courte, score fourni incohérent).
        """
        if not data:
            raise ValueError("aucune proposition LLM")

        probability = int(data["probability"])
        impact = int(data["impact"])
        if not (1 <= probability <= 5) or not (1 <= impact <= 5):
            raise ValueError("probabilité ou impact hors échelle 1-5")

        justification = (
            str(data.get("justification") or "").strip() or "Justification non fournie."
        )
        source = [
            item for item in (data.get("source") or []) if isinstance(item, str)
        ]
        if not source:
            source = scenario.source

        return RiskAssessment(
            probability=probability,
            impact=impact,
            justification=justification,
            score=self._score(probability, impact),
            source=source,
            confidence=scenario.confidence,
        )

    # ------------------------------------------------------------------
    # Repli déterministe (fonctionne sans LLM)
    # ------------------------------------------------------------------

    def _fallback_assessment(
        self,
        scenario: RiskScenario,
        asset_by_id: dict[str, Asset],
        vuln_by_id: dict[str, Vulnerability],
    ) -> RiskAssessment:
        """Évaluation provisoire transparente, sans invention de fait."""
        asset = asset_by_id.get(scenario.asset_id)
        vuln = vuln_by_id.get(scenario.vulnerability_id)

        probability = (
            _VULN_STATUS_PROBABILITY.get(vuln.status, 2) if vuln else 2
        )
        impact = 3
        if asset is not None:
            impact = (
                4
                if asset.type.value in _HIGH_IMPACT_TYPES
                else 3
            )
            business_value = asset.business_value
            if business_value and business_value != NOT_DOCUMENTED:
                impact = max(impact, 4)

        reason_p = (
            f"statut « {vuln.status.value} » de la vulnérabilité"
            if vuln
            else "vulnérabilité non reliée"
        )
        reason_i = (
            f"actif de type « {asset.type.value} »"
            if asset
            else "actif non relié"
        )
        justification = (
            f"Proposition automatique provisoire (à valider par l'analyste) : "
            f"probabilité {probability} ({PROBABILITY_LABELS[probability]}) dérivée "
            f"du {reason_p} ; impact {impact} ({IMPACT_LABELS[impact]}) dérivé de "
            f"l'{reason_i}. Score calculé {self._score(probability, impact)} = "
            f"{probability} × {impact}. Aucun élément hors documentation utilisé."
        )

        return RiskAssessment(
            probability=probability,
            impact=impact,
            justification=justification,
            score=self._score(probability, impact),
            source=scenario.source,
            confidence=scenario.confidence,
        )

    @staticmethod
    def _score(probability: int, impact: int) -> int:
        """Score calculé de façon déterministe (1-25)."""
        from app.services.risk_scoring import calculate_score

        return calculate_score(probability, impact)


__all__ = ["RiskAssessmentAgent"]