"""Tests de la persistance SQLite."""

from app.orchestration.workflow import Orchestrator, AnalysisState
from app.services.storage import Storage


def _state(analysis_id: str) -> AnalysisState:
    return AnalysisState(
        id=analysis_id,
        documents=[{"id": "DOC-001", "filename": "x.md", "content": "bonjour"}],
        created_at="2026-09-23T09:00:00Z",
        updated_at="2026-09-23T09:01:00Z",
        status="1. Import de la documentation",
    )


def test_save_and_load_roundtrip(tmp_db_path) -> None:
    storage = Storage(tmp_db_path)
    state = _state("ANALYSIS-TEST-001")
    storage.save_analysis(Orchestrator.to_dict(state))

    loaded = storage.load_analysis("ANALYSIS-TEST-001")
    assert loaded["id"] == "ANALYSIS-TEST-001"
    assert loaded["documents"][0]["id"] == "DOC-001"
    restored = Orchestrator.from_dict(loaded)
    assert restored.id == state.id
    assert restored.documents == state.documents


def test_upsert_updates_status(tmp_db_path) -> None:
    storage = Storage(tmp_db_path)
    first = _state("A")
    storage.save_analysis(Orchestrator.to_dict(first))
    second = first.model_copy(deep=True)
    second.status = "9. Registre des risques proposé"
    storage.save_analysis(Orchestrator.to_dict(second))
    assert storage.load_analysis("A")["status"] == "9. Registre des risques proposé"
    assert len(storage.list_analyses()) == 1


def test_unknown_analysis_is_none(tmp_db_path) -> None:
    storage = Storage(tmp_db_path)
    assert storage.load_analysis("INCONNU") is None
    assert storage.list_analyses() == []


def test_register_save_and_load(tmp_db_path) -> None:
    storage = Storage(tmp_db_path)
    storage.save_register("A", {"register": [{"id": "RSK-001"}]})
    loaded = storage.load_register("A")
    assert loaded["register"][0]["id"] == "RSK-001"


def test_delete_removes_analysis_and_register(tmp_db_path) -> None:
    storage = Storage(tmp_db_path)
    storage.save_analysis(Orchestrator.to_dict(_state("A")))
    storage.save_register("A", {"register": []})
    storage.delete_analysis("A")
    assert storage.load_analysis("A") is None
    assert storage.load_register("A") is None