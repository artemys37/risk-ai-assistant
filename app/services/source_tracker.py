"""Traçabilité des sources : chaque affirmation relie à son origine.

Permet de répondre à la question : « Pourquoi l'agent affirme-t-il cela ? »
"""

from app.models.base import ConfidenceLevel


class SourceTracker:
    """Associe des identifiants de documents et fragments à des assertions.

    Convention : DOC-XXX pour un document importé,
    DOC-XXX§n pour un fragment / section.
    """

    def __init__(self) -> None:
        self._documents: dict[str, str] = {}
        self._claims: dict[str, list[str]] = {}
        self._counter = 0

    def register_document(self, filename: str) -> str:
        """Enregistre un document importé et retourne son ID (DOC-XXX)."""
        self._counter += 1
        doc_id = f"DOC-{self._counter:03d}"
        self._documents[doc_id] = filename
        return doc_id

    def link(self, claim_id: str, sources: list[str]) -> None:
        """Relie une affirmation (ACT-001, THR-003…) à ses sources."""
        existing = self._claims.setdefault(claim_id, [])
        for src in sources:
            if src not in existing:
                existing.append(src)

    def sources_of(self, claim_id: str) -> list[str]:
        """Retourne les sources d'une affirmation — [] si aucune (jamais inventé)."""
        return list(self._claims.get(claim_id, []))

    def known_documents(self) -> dict[str, str]:
        return dict(self._documents)

    @staticmethod
    def estimate_confidence(sources: list[str], evidence_type: str) -> ConfidenceLevel:
        """Estime un niveau de confiance à partir des critères explicites.

        Critères (pas une probabilité statistique) :
        - HIGH     : au moins une source ET fait documenté
        - MEDIUM   : au moins une source OU inférence étayée
        - LOW      : hypothèse ou aucune source
        """
        if evidence_type == "FAIT DOCUMENTÉ" and sources:
            return ConfidenceLevel.HIGH
        if sources or evidence_type == "INFERENCE":
            return ConfidenceLevel.MEDIUM
        return ConfidenceLevel.LOW
