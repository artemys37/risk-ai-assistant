"""Agent 2 — Identification des actifs.

À partir de l'extraction de l'agent Documentation, identifie les actifs
(données, applications, serveurs, postes, réseau, comptes, services, cloud,
secrets, certificats, interfaces, infrastructure physique).

Règles :
- ne JAMAIS inventer un propriétaire ou une valeur métier → NOT_DOCUMENTED ;
- les sources sont conservées (DOC-XXX) ;
- type inconnu → catégorie existing "autre", jamais un type inventé.
"""

import json

from app.agents.base import AgentBase, AgentError
from app.models.asset import Asset, AssetType

SYSTEM_INSTRUCTIONS = """
Tu es l'agent « Actifs » d'un système d'assistance à l'analyse de risques.

À partir de l'extraction documentaire fournie, identifie les actifs du
système dans ces catégories : données, application, serveur, poste client,
équipement réseau, compte, service, infrastructure cloud, secret,
certificat, interface, infrastructure physique, autre.

Règles ABSOLUES :
1. N'invente JAMAIS un actif, un propriétaire, une valeur métier ni une
   source. Une information absente → libellé exact « Non documenté ».
2. "type" doit être une des catégories listées ci-dessus.
3. "source" référence les documents DOC-XXX fournis, section si possible.
4. "evidence_type" vaut l'un de : FAIT DOCUMENTÉ, INFERENCE, HYPOTHÈSE.
5. "business_value" ne doit être rempli que si la documentation l'explicite.

Réponds UNIQUEMENT avec un tableau JSON d'objets de la forme :
[
  {
    "name": "nom de l'actif",
    "type": "serveur",
    "description": "description ou Non documenté",
    "owner": "propriétaire ou Non documenté",
    "business_value": "valeur métier ou Non documenté",
    "source": ["DOC-001"],
    "evidence_type": "INFERENCE"
  }
]
""".strip()


class AssetAgent(AgentBase):
    """Identification des actifs à partir de l'extraction documentaire."""

    agent_name = "asset-agent"

    def run(self, extraction, llm=None) -> list[Asset]:
        payload = (
            extraction.model_dump()
            if hasattr(extraction, "model_dump")
            else {"extraction": extraction}
        )

        llm = self._get_llm(llm)
        obj = self._json_completion(llm, SYSTEM_INSTRUCTIONS, json.dumps(payload, ensure_ascii=False, indent=2))
        if not isinstance(obj, list):
            raise AgentError("l'agent Actifs attend une liste JSON en sortie du LLM")

        assets: list[Asset] = []
        for index, item in enumerate(obj, start=1):
            if not isinstance(item, dict):
                continue
            sources = self._sources(item)
            evidence_type = self._evidence_type(item)
            asset = Asset(
                id=f"ACT-{index:03d}",
                name=self._field(item, "name") or f"Actif {index:03d}",
                type=self._coerce_type(self._field(item, "type")),
                description=self._field(item, "description"),
                owner=self._field(item, "owner"),
                business_value=self._field(item, "business_value"),
                source=sources,
                confidence=self._estimate_confidence(sources, evidence_type),
                evidence_type=evidence_type,
            )
            assets.append(asset)
        return assets

    @staticmethod
    def _coerce_type(raw: str) -> AssetType:
        """Mappe le type fourni vers une catégorie existante, sinon 'autre'."""
        normalized = raw.lower()
        if not normalized or normalized == "non documenté":
            return AssetType.OTHER
        for candidate in AssetType:
            if normalized == candidate.value.lower() or normalized == candidate.name.lower():
                return candidate
        if "poste" in normalized or "client" in normalized:
            return AssetType.CLIENT_WORKSTATION
        if "réseau" in normalized or "reseau" in normalized or "firewall" in normalized:
            return AssetType.NETWORK_EQUIPMENT
        if "compte" in normalized:
            return AssetType.ACCOUNT
        if "base de données" in normalized or "database" in normalized or "bd" in normalized:
            return AssetType.DATA
        if "certificat" in normalized:
            return AssetType.CERTIFICATE
        if "cloud" in normalized:
            return AssetType.CLOUD_INFRASTRUCTURE
        if "api" in normalized or "interface" in normalized:
            return AssetType.INTERFACE
        if "secret" in normalized or "clé" in normalized or "cle" in normalized:
            return AssetType.SECRET
        if "application" in normalized or "app" in normalized:
            return AssetType.APPLICATION
        return AssetType.OTHER


__all__ = ["AssetAgent"]