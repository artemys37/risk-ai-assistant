"""Test de bout en bout du pipeline Sprint 2 (avec LLM mock).

Documents → extraction → actifs → menaces → vulnérabilités.
Vérifie la cohérence des identifiants entre les étapes.
"""

from app.agents.asset_agent import AssetAgent
from app.agents.documentation_agent import DocumentationAgent
from app.agents.threat_agent import ThreatAgent
from app.agents.vulnerability_agent import VulnerabilityAgent
from app.services.document_parser import load_documents
from app.services.llm import LLMClient
from tests.helpers import dispatch_responder

DOC_TEXT = """## Système Gestion RH
Application web interne utilisée par les employés du service RH.
Données : salaires, contrats, évaluations.
Serveur : Linux, base PostgreSQL, authentification Active Directory.
Une API interne expose des données RH aux autres applications.
Un pare-feu protège le réseau. Les sauvegardes sont quotidiennes.
"""

EXTRACTION = {
    "system_name": "Gestion RH",
    "system_objective": "Gestion des données RH internes",
    "architecture": "Application web + serveur Linux + PostgreSQL + AD",
    "components": ["Application web", "Serveur Linux", "Base PostgreSQL", "API interne"],
    "users": ["Employés RH"],
    "data": ["Salaires", "Contrats", "Évaluations"],
    "interfaces": ["API interne"],
    "technologies": ["Linux", "PostgreSQL", "Active Directory"],
    "dependencies": ["Active Directory"],
    "data_flows": [],
    "constraints": [],
    "existing_security_controls": ["Pare-feu", "Sauvegardes", "Authentification"],
    "missing_information": ["Propriétaire des données non documenté"],
    "sources": {"system_name": ["DOC-001"], "data": ["DOC-001"]},
}

ASSETS = [
    {"name": "Serveur Linux", "type": "serveur", "source": ["DOC-001"], "evidence_type": "FAIT DOCUMENTÉ"},
    {"name": "Base PostgreSQL RH", "type": "base de données", "description": "Salaires, contrats", "source": ["DOC-001"], "evidence_type": "FAIT DOCUMENTÉ"},
    {"name": "API interne", "type": "interface", "source": ["DOC-001"], "evidence_type": "FAIT DOCUMENTÉ"},
]

THREATS = [
    {"name": "Accès non autorisé", "description": "Accès illégitime aux données RH.",
     "target_assets": ["ACT-001", "ACT-002"], "rationale": "Exposition réseau décrite.",
     "stride_category": "Information Disclosure", "source": ["DOC-001"],
     "evidence_type": "INFERENCE"},
    {"name": "Exfiltration via API", "description": "Récupération massive de données RH.",
     "target_assets": ["ACT-003"], "rationale": "API documentée sans contrôle d'accès détaillé.",
     "source": ["DOC-001"], "evidence_type": "HYPOTHÈSE"},
]

VULNERABILITIES = [
    {"name": "Contrôle d'accès API non documenté", "description": "La doc ne précise pas d'autorisation sur l'API.",
     "status": "À VÉRIFIER", "target_assets": ["ACT-003"], "related_threats": ["THR-002"],
     "rationale": "Information absente de la documentation."},
    {"name": "Base non chiffrée ?", "description": "Le chiffrement au repos n'est pas mentionné.",
     "status": "À VÉRIFIER", "target_assets": ["ACT-002"], "related_threats": ["THR-001"],
     "rationale": "Élément indéterminé."},
]


def test_full_pipeline_agents() -> None:
    documents = load_documents([("systeme.md", DOC_TEXT.encode())])
    assert documents[0]["id"] == "DOC-001"

    responder = dispatch_responder(
        {
            "agent « Documentation »": EXTRACTION,
            "agent « Actifs »": ASSETS,
            "agent « Menaces »": THREATS,
            "agent « Vulnérabilités »": VULNERABILITIES,
        }
    )
    llm = LLMClient(provider="mock", responder=responder)

    extraction = DocumentationAgent().run(documents, llm=llm)
    assert extraction.system_name == "Gestion RH"

    assets = AssetAgent().run(extraction, llm=llm)
    assert [a.id for a in assets] == ["ACT-001", "ACT-002", "ACT-003"]
    asset_ids = {a.id for a in assets}

    threats = ThreatAgent().run(assets, extraction=extraction, llm=llm)
    assert threats  # au moins une menace reliée
    for threat in threats:
        # chaque cible existe réellement (cohérence inter-agents)
        assert set(threat.target_assets) <= asset_ids

    vulnerabilities = VulnerabilityAgent().run(assets, threats, extraction=extraction, llm=llm)
    assert vulnerabilities
    for vuln in vulnerabilities:
        assert set(vuln.target_assets) <= asset_ids
        for threat_ref in vuln.related_threats:
            assert threat_ref in {t.id for t in threats}

    # Les test 1 du cahier : extraction correcte des actifs sur doc complète.
    assert len(assets) == 3