"""Tests du client LLM (sans appel réseau — provider mock)."""

import pytest

from app.services.llm import LLMClient, LLMError, extract_json


def test_extract_json_plain() -> None:
    assert extract_json('{"a": 1}') == {"a": 1}


def test_extract_json_in_markdown_fence() -> None:
    text = "Voici le résultat :\n```json\n[{\"id\": \"ACT-001\"}]\n```\n Fin."
    assert extract_json(text) == [{"id": "ACT-001"}]


def test_extract_json_ignores_leading_text() -> None:
    assert extract_json("ok { \"x\": [1, 2] } fin") == {"x": [1, 2]}


def test_extract_json_returns_none_on_invalid() -> None:
    assert extract_json("pas de json ici") is None
    assert extract_json("") is None


def test_mock_provider_with_responder() -> None:
    llm = LLMClient(provider="mock", responder=lambda s, u: '{"ok": true}')
    assert llm.complete("s", "u") == '{"ok": true}'


def test_mock_provider_with_string() -> None:
    llm = LLMClient(provider="mock", responder='{"ok": true}')
    assert llm.complete("s", "u") == '{"ok": true}'


def test_mock_provider_without_responder_errors() -> None:
    llm = LLMClient(provider="mock")
    with pytest.raises(LLMError, match="responder"):
        llm.complete("s", "u")


@pytest.mark.parametrize("bad_provider", ["gemini", "toto"])
def test_unknown_provider_errors(bad_provider: str) -> None:
    with pytest.raises(LLMError, match="fournisseur LLM inconnu"):
        LLMClient(provider=bad_provider)


def test_temperature_defaults_to_zero() -> None:
    llm = LLMClient(provider="mock")
    assert llm.temperature == 0.0