"""Agent 7 — Critique / vérification (OBLIGATOIRE).

Mission
-------
Rechercher les erreurs produites par les autres agents :
- Cohérence : le scénario correspond-il à l'actif ? la menace est-elle
  pertinente ? la vulnérabilité est-elle démontrée ? le risque est-il
  cohérent ?
- Hallucinations : informations sans source, technologies inventées,
  vulnérabilités non démontrées, affirmations excessivement certaines.
- Traçabilité : chaque affirmation importante doit avoir source,
  justification ou hypothèse explicitement déclarée.

Résultat (modèle CriticReport) :
status = PASS | REVIEW_REQUIRED | REJECT
issues, missing_information, recommendations.

Implémentation
--------------
Vérifications déterministes et reproductibles sur les sorties des agents
amont. Aucun verdict n'est produit au hasard : chaque contrôle est codé
et traçable (checked_ids). Le rapport est conservé et affiché à l'analyste
avant la validation humaine.
"""

from datetime import datetime, timezone

from app.agents.base import AgentBase
from app.models.asset import Asset
from app.models.base import NOT_DOCUMENTED, ConfidenceLevel, EvidenceType
from app.models.risk import CriticReport, CriticStatus, Risk
from app.models.threat import Threat
from app.models.vulnerability import Vulnerability, VulnerabilityStatus
from app.services import risk_scoring
from app.services.risk_scoring import calculate_score

# Contrôles considérés comme bloquants (incohérence factuelle).
_FATAL_MARKERS = (
    "référence à un actif inconnu",
    "référence à une menace inconnue",
    "référence à une vulnérabilité inconnue",
    "score incohérent avec la matrice",
    "affirmation sans source ni hypothèse",
)


class CriticAgent(AgentBase):
    """Vérification systématique des sorties des autres agents."""

    agent_name = "critic-agent"

    def run(
        self,
        extraction,
        assets: list[Asset],
        threats: list[Threat],
        vulnerabilities: list[Vulnerability],
        risks: list[Risk],
    ) -> CriticReport:
        """Soumet l'analyse complète à la critique (cohérence + hallucinations + traçabilité)."""
        asset_ids = {asset.id for asset in assets}
        threat_ids = {threat.id for threat in threats}
        vuln_ids = {vuln.id for vuln in vulnerabilities}
        vuln_by_id = {vuln.id: vuln for vuln in vulnerabilities}

        issues: list[str] = []
        missing: list[str] = []
        recommendations: set[str] = set()
        checked: list[str] = []
        all_sources: list[str] = []

        for risk in risks:
            checked.append(risk.id)
            all_sources.extend(risk.sources)
            scenario = risk.scenario
            assessment = risk.assessment

            # -- Cohérence des références inter-agents -------------------
            if scenario.asset_id not in asset_ids:
                issues.append(
                    f"{risk.id} : référence à un actif inconnu "
                    f"({scenario.asset_id})."
                )
            if scenario.threat_id not in threat_ids:
                issues.append(
                    f"{risk.id} : référence à une menace inconnue "
                    f"({scenario.threat_id})."
                )
            if scenario.vulnerability_id not in vuln_ids:
                issues.append(
                    f"{risk.id} : référence à une vulnérabilité inconnue "
                    f"({scenario.vulnerability_id})."
                )

            # -- Traçabilité / hallucinations ----------------------------
            if not risk.sources and not scenario.hypotheses:
                issues.append(
                    f"{risk.id} : affirmation sans source ni hypothèse déclarée."
                )
            if not assessment.justification.strip() or len(assessment.justification) < 10:
                issues.append(f"{risk.id} : justification de score absente ou trop courte.")

            try:
                computed = calculate_score(assessment.probability, assessment.impact)
                if assessment.score != computed:
                    issues.append(
                        f"{risk.id} : score incohérent avec la matrice "
                        f"(prob{assessment.probability} × impact{assessment.impact} "
                        f"≠ score {assessment.score})."
                    )
            except risk_scoring.ScaleError as exc:
                issues.append(f"{risk.id} : échelle invalide ({exc}).")

            # -- Affirmation trop certaine -------------------------------
            vuln = vuln_by_id.get(scenario.vulnerability_id)
            if (
                vuln is not None
                and vuln.status is VulnerabilityStatus.CONFIRMED
                and vuln.evidence_type is not EvidenceType.DOCUMENTED_FACT
            ):
                issues.append(
                    f"{risk.id} : vulnérabilité « {vuln.name} » déclarée CONFIRMÉE "
                    "sans fait documenté."
                )

            # -- Informations manquantes (non bloquantes) ----------------
            if not risk.scenario.consequences:
                missing.append(f"{risk.id} : conséquences non documentées.")
            if scenario.hypotheses:
                missing.append(f"{risk.id} : repose sur des hypothèses à vérifier.")
            asset = next((a for a in assets if a.id == scenario.asset_id), None)
            if asset is not None:
                if asset.owner == NOT_DOCUMENTED:
                    missing.append(f"{risk.id} : propriétaire de l'actif {asset.id} non documenté.")
                if asset.business_value == NOT_DOCUMENTED:
                    missing.append(
                        f"{risk.id} : valeur métier de l'actif {asset.id} non documentée."
                    )
            if (
                scenario.vulnerability_id in vuln_ids
                and vuln is not None
                and vuln.status is VulnerabilityStatus.NOT_ESTABLISHED
            ):
                missing.append(
                    f"{risk.id} : vulnérabilité « {vuln.name} » non établie "
                    "(aucun élément)."
                )

        checked_ids = sorted(
            {
                *checked,
                *asset_ids,
                *threat_ids,
                *vuln_ids,
                *(r.scenario.id for r in risks),
            }
        )

        if missing and not issues:
            recommendations.add(
                "Compléter la documentation manquante puis relancer la validation."
            )
        if issues:
            recommendations.add("Corriger les points relevés avant validation.")

        fatal_issues = [
            issue
            for issue in issues
            if any(marker in issue for marker in _FATAL_MARKERS)
        ]

        if not issues and not missing:
            status = CriticStatus.PASS
            confidence = ConfidenceLevel.HIGH
        elif fatal_issues:
            status = CriticStatus.REJECT
            confidence = ConfidenceLevel.LOW
        else:
            status = CriticStatus.REVIEW_REQUIRED
            confidence = ConfidenceLevel.MEDIUM

        return CriticReport(
            status=status,
            issues=issues,
            missing_information=list(dict.fromkeys(missing)),
            recommendations=sorted(recommendations),
            checked_ids=checked_ids,
            source=list(dict.fromkeys(all_sources)),
            confidence=confidence,
        )


def now_iso() -> str:
    """Horodatage ISO 8601 UTC (repris par l'orchestrateur)."""
    return datetime.now(timezone.utc).isoformat()


__all__ = ["CriticAgent"]