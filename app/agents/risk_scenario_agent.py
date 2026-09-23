"""Agent 5 — Construction des scénarios de risques.

Mission
-------
Construire les scénarios à partir de : Actif + Menace + Vulnérabilité +
Contexte = Scénario de risque.

Chaque scénario (modèle RiskScenario) précise :
acteur / source de menace, événement redouté, actif impacté,
vulnérabilité exploitée, conséquences possibles, éléments de preuve,
hypothèses (déclarées comme telles, jamais présentées comme des faits).

Implémentation
--------------
Assemblage déterministe et traçable des triplets Actif × Menace ×
Vulnérabilité cohérents : aucune information n'est inventée, toutes les
valeurs proviennent des éléments déjà produits par les agents amont
(actifs, menaces, vulnérabilités) et les sources (DOC-XXX) sont conservées
de bout en bout. Le niveau de confiance et la nature de l'affirmation
sont dérivés selon un principe de conservatisme (une hypothèse domine une
inférence qui domine un fait documenté).
"""

from app.agents.base import AgentBase
from app.models.asset import Asset
from app.models.base import ConfidenceLevel, EvidenceType
from app.models.risk import RiskScenario
from app.models.threat import Threat
from app.models.vulnerability import Vulnerability

CONFIDENCE_RANK = {
    ConfidenceLevel.HIGH: 3,
    ConfidenceLevel.MEDIUM: 2,
    ConfidenceLevel.LOW: 1,
}


def _dedup(values: list[str]) -> list[str]:
    """Dédoublonne en conservant l'ordre d'apparition."""
    seen: dict[str, None] = {}
    for value in values:
        if value and value not in seen:
            seen[value] = None
    return list(seen)


def _worst_confidence(*levels: ConfidenceLevel) -> ConfidenceLevel:
    """Retourne le niveau de confiance le plus faible (conservatisme)."""
    if not levels:
        return ConfidenceLevel.LOW
    return min(levels, key=lambda level: CONFIDENCE_RANK.get(level, 1))


def _worst_evidence(*types: EvidenceType) -> EvidenceType:
    """Retourne la nature la plus incertaine (conservatisme)."""
    if any(t is EvidenceType.HYPOTHESIS for t in types):
        return EvidenceType.HYPOTHESIS
    if any(t is EvidenceType.INFERENCE for t in types):
        return EvidenceType.INFERENCE
    return EvidenceType.DOCUMENTED_FACT


def _derive_actor(threat: Threat) -> str:
    """Déduit un acteur/source de menace à partir des seules données existantes.

    Si aucun indice ne permet de qualifier l'acteur, le nom réel de la
    menace est reporté (jamais une invention).
    """
    text = f"{threat.name} {threat.description} {threat.rationale}".lower()
    for token, label in (
        ("ext", "Acteur extérieur"),
        ("interne", "Acteur interne"),
        ("initié", "Acteur interne"),
        ("employé", "Acteur interne"),
        ("malveillant", "Acteur malveillant"),
        ("attaquant", "Acteur malveillant"),
        ("accident", "Acte accidentel"),
        ("erreur", "Acte accidentel"),
        ("négligence", "Acte accidentel"),
        ("fournisseur", "Vecteur de la chaîne d'approvisionnement"),
        ("chaîne d'approvisionnement", "Vecteur de la chaîne d'approvisionnement"),
    ):
        if token in text:
            return label
    return f"Source de menace « {threat.name} »"


class RiskScenarioAgent(AgentBase):
    """Assemblage des scénarios de risques cohérents.

    Chaque scénario relie une menace à un actif via une vulnérabilité
    exploitée. Un triplet n'est construit que si la menace et la
    vulnérabilité partagent une cible commune (cohérence inter-agents).
    """

    agent_name = "risk-scenario-agent"

    def run(
        self,
        assets: list[Asset],
        threats: list[Threat],
        vulnerabilities: list[Vulnerability],
        extraction=None,
        llm=None,
    ) -> list[RiskScenario]:
        """Construit les scénarios Actif + Menace + Vulnérabilité + Contexte."""
        if not assets or not threats or not vulnerabilities:
            return []

        asset_by_id = {asset.id: asset for asset in assets}

        scenarios: list[RiskScenario] = []
        seen: set[tuple[str, str, str]] = set()

        for index, (vuln, threat, asset_id) in enumerate(
            self._candidate_triples(threats, vulnerabilities), start=1
        ):
            asset = asset_by_id.get(asset_id)
            if asset is None:
                continue
            triple = (asset.id, threat.id, vuln.id)
            if triple in seen:
                continue
            seen.add(triple)

            sources = _dedup([*asset.source, *threat.source, *vuln.source])
            evidence = _dedup([*threat.evidence, *vuln.references])

            hypotheses: list[str] = []
            if (
                vuln.evidence_type is EvidenceType.HYPOTHESIS
                or threat.evidence_type is EvidenceType.HYPOTHESIS
            ):
                hypotheses.append(
                    "Scénario construit sur des hypothèses non documentées : à valider."
                )
            if not threat.evidence:
                hypotheses.append(
                    "Aucun élément de preuve documenté pour cette menace."
                )

            consequences = (
                [*threat.evidence, threat.description]
                if threat.evidence
                else [threat.description]
            )

            actor = _derive_actor(threat)

            scenarios.append(
                RiskScenario(
                    id=f"RSK-{index:03d}",
                    description=(
                        f"{actor} exploite « {vuln.name} » pour atteindre l'actif "
                        f"« {asset.name} » (événement redouté : {threat.description})."
                    ),
                    threat_actor=actor,
                    feared_event=threat.description,
                    asset_id=asset.id,
                    threat_id=threat.id,
                    vulnerability_id=vuln.id,
                    consequences=_dedup(consequences),
                    evidence=evidence,
                    hypotheses=hypotheses,
                    source=sources,
                    confidence=_worst_confidence(
                        asset.confidence, threat.confidence, vuln.confidence
                    ),
                    evidence_type=_worst_evidence(
                        asset.evidence_type, threat.evidence_type, vuln.evidence_type
                    ),
                )
            )
        return scenarios

    @staticmethod
    def _candidate_triples(
        threats: list[Threat],
        vulnerabilities: list[Vulnerability],
    ) -> list[tuple[Vulnerability, Threat, str]]:
        """Énumère les triplets (vulnérabilité, menace, actif) cohérents.

        Une vulnérabilité et une menace ne se combinent que si elles
        partagent au moins un actif cible commun, ou si la vulnérabilité
        référence explicitement la menace (related_threats).
        """
        triples: list[tuple[Vulnerability, Threat, str]] = []
        for vuln in vulnerabilities:
            vuln_targets = set(vuln.target_assets)
            for threat in threats:
                threat_targets = set(threat.target_assets)
                common = sorted(vuln_targets & threat_targets)
                if not common and (vuln.related_threats and threat.id in vuln.related_threats):
                    common = sorted(vuln_targets or threat_targets)
                for asset_id in sorted(set(common)):
                    triples.append((vuln, threat, asset_id))
        return triples


__all__ = ["RiskScenarioAgent"]