"""Client LLM configurable via variables d'environnement.

Fournisseurs pris en charge :
- "openai" / "openai-compatible" : API Chat Completions (cream OpenAI,
  ou tout serveur compatible : vLLM, LM Studio, Ollama OpenAI mode...)
- "ollama" : API native Ollama (/api/chat)
- "mock"  : aucun appel réseau — utilisé par les tests (responder)

Configuration (.env) :
    LLM_PROVIDER=openai|ollama|mock
    LLM_MODEL=gpt-4o-mini|llama3.1|...
    LLM_API_KEY=sk-...
    LLM_BASE_URL=https://api.openai.com/v1  (ou http://localhost:11434)
    LLM_TEMPERATURE=0.0

Aucune clé API n'est stockée dans le code. La température par défaut
(0.0) favorise la reproductibilité des extractions.
"""

import json
from collections.abc import Callable

import httpx

from app.services import config

ResponseFn = Callable[[str, str], str]


class LLMError(Exception):
    """Échec d'appel au LLM (réseau, clé, réponse invalide…)."""


class LLMClient:
    def __init__(
        self,
        *,
        provider: str | None = None,
        model: str | None = None,
        api_key: str | None = None,
        base_url: str | None = None,
        temperature: float | None = None,
        responder: ResponseFn | str | None = None,
    ) -> None:
        prefix = provider or config.get("LLM_PROVIDER") or "openai"
        self.provider = prefix.lower().replace("openai-compatible", "openai")
        self.model = model or config.get("LLM_MODEL")
        self.api_key = api_key or config.get("LLM_API_KEY")
        self.base_url = (base_url or config.get("LLM_BASE_URL")).rstrip("/")
        self.temperature = (
            temperature
            if temperature is not None
            else config.get_float("LLM_TEMPERATURE", 0.0)
        )
        self.responder = responder

        if self.provider not in {"openai", "ollama", "mock"}:
            raise LLMError(
                f"fournisseur LLM inconnu : '{self.provider}' "
                f"(attendu : openai | ollama | mock)"
            )

    # ------------------------------------------------------------------
    # Appels publics
    # ------------------------------------------------------------------

    def complete(self, system: str, user: str, max_tokens: int = 3000) -> str:
        """Envoie system + user au LLM et retourne le texte de la réponse."""
        if self.provider == "mock":
            return self._mock(system, user)
        if self.provider == "ollama":
            return self._call_ollama(system, user, max_tokens)
        return self._call_openai_compatible(system, user, max_tokens)

    # ------------------------------------------------------------------
    # Implémentations
    # ------------------------------------------------------------------

    def _mock(self, system: str, user: str) -> str:
        if callable(self.responder):
            return self.responder(system, user)
        if isinstance(self.responder, str):
            return self.responder
        raise LLMError("fournisseur 'mock' sans responder (tests uniquement)")

    def _call_openai_compatible(self, system: str, user: str, max_tokens: int) -> str:
        url = f"{self.base_url or 'https://api.openai.com/v1'}/chat/completions"
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "temperature": self.temperature,
            "max_tokens": max_tokens,
        }
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        try:
            with httpx.Client(timeout=120) as client:
                response = client.post(url, json=payload, headers=headers)
                response.raise_for_status()
                data = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise LLMError(f"échec appel LLM openai-compatible : {exc}") from exc
        try:
            return data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise LLMError(f"réponse LLM inattendue : {data!r}") from exc

    def _call_ollama(self, system: str, user: str, max_tokens: int) -> str:
        url = f"{self.base_url or 'http://localhost:11434'}/api/chat"
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "stream": False,
            "options": {"temperature": self.temperature, "num_predict": max_tokens},
        }
        try:
            with httpx.Client(timeout=120) as client:
                response = client.post(url, json=payload)
                response.raise_for_status()
                data = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise LLMError(f"échec appel LLM ollama : {exc}") from exc
        try:
            return data["message"]["content"]
        except (KeyError, TypeError) as exc:
            raise LLMError(f"réponse LLM inattendue : {data!r}") from exc


# ----------------------------------------------------------------------
# Extraction robuste d'un JSON depuis la réponse du LLM
# ----------------------------------------------------------------------


def extract_json(text: str) -> dict | list | None:
    """Extrait le premier objet/tableau JSON valide d'un texte LLM.

    Tolère les blocs de code markdown et le texte environnant.
    """
    if not text:
        return None
    stripped = text.replace("```json", "").replace("```", "").strip()
    start = -1
    for char in ("{", "["):
        idx = stripped.find(char)
        if idx != -1 and (start == -1 or idx < start):
            start = idx
    if start == -1:
        return None
    open_char = stripped[start]
    close_char = "}" if open_char == "{" else "]"
    depth = 0
    in_string = False
    escaped = False
    for i in range(start, len(stripped)):
        ch = stripped[i]
        if in_string:
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == '"':
                in_string = False
            continue
        if ch == '"':
            in_string = True
        elif ch == open_char:
            depth += 1
        elif ch == close_char:
            depth -= 1
            if depth == 0:
                try:
                    return json.loads(stripped[start : i + 1])
                except json.JSONDecodeError:
                    return None
    return None