"""Aides aux tests des agents — construction de LLM mock."""

import json


def canned_responder(payload: object):
    """Retourne un responder renvoyant un payload encapsulé en markdown JSON."""

    def responder(system: str, user: str) -> str:
        data = json.dumps(payload, ensure_ascii=False)
        return f"Voici le résultat :\n```json\n{data}\n```"

    return responder


def dispatch_responder(handlers: dict[str, object]):
    """Responder qui choisit le payload selon un marqueur du prompt système."""

    def responder(system: str, user: str) -> str:
        for marker, payload in handlers.items():
            if marker in system:
                return canned_responder(payload)(system, user)
        raise AssertionError(f"aucun handler pour le prompt système : {system[:80]}...")

    return responder