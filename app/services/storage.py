"""Persistance SQLite de l'état des analyses (prototype, migrable PostgreSQL).

Tables :
- analyses   : un état complet d'analyse (JSON), par identifiant ;
- registres  : captures du registre final après validation humaine.

Le chemin est configuré par DATABASE_URL (ex. sqlite:///./data/risk_ai.db).
Aucune dépendance : sqlite3 de la bibliothèque standard.
"""

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from app.services import config

_DEFAULT_URL = "sqlite:///./data/risk_ai.db"


def _db_path() -> Path:
    url = config.get("DATABASE_URL", _DEFAULT_URL) or _DEFAULT_URL
    if url.startswith("sqlite:///"):
        path = Path(url[len("sqlite:///") :])
    else:
        path = Path(url)
    if not path.is_absolute():
        path = Path.cwd() / path
    return path


class Storage:
    """Accès bas-niveau SQLite — une connexion par opération (thread-safe
    pour un prototype ; SQLAlchemy/Alembic prévus en migration)."""

    def __init__(self, path: Path | str | None = None) -> None:
        self.path = Path(path) if path else _db_path()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        return connection

    def _init_schema(self) -> None:
        with self._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS analyses (
                    analysis_id TEXT PRIMARY KEY,
                    state TEXT NOT NULL,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS registres (
                    analysis_id TEXT PRIMARY KEY,
                    register TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                """
            )

    # ------------------------------------------------------------------
    # Analyses
    # ------------------------------------------------------------------

    def save_analysis(self, state: dict) -> None:
        """Upsert de l'état complet (analyses)."""
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO analyses (analysis_id, state, status, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(analysis_id) DO UPDATE SET
                    state = excluded.state,
                    status = excluded.status,
                    updated_at = excluded.updated_at
                """,
                (
                    state["id"],
                    json.dumps(state, ensure_ascii=False),
                    state["status"],
                    state["created_at"],
                    state["updated_at"],
                ),
            )

    def load_analysis(self, analysis_id: str) -> dict | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT state FROM analyses WHERE analysis_id = ?", (analysis_id,)
            ).fetchone()
        return json.loads(row["state"]) if row else None

    def list_analyses(self) -> list[dict]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT analysis_id, status, created_at, updated_at
                FROM analyses ORDER BY updated_at DESC
                """
            ).fetchall()
        return [dict(row) for row in rows]

    def delete_analysis(self, analysis_id: str) -> None:
        with self._connect() as connection:
            connection.execute(
                "DELETE FROM analyses WHERE analysis_id = ?", (analysis_id,)
            )
            connection.execute(
                "DELETE FROM registres WHERE analysis_id = ?", (analysis_id,)
            )

    # ------------------------------------------------------------------
    # Registre final
    # ------------------------------------------------------------------

    def save_register(self, analysis_id: str, register: dict) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO registres (analysis_id, register, created_at)
                VALUES (?, ?, ?)
                ON CONFLICT(analysis_id) DO UPDATE SET
                    register = excluded.register,
                    created_at = excluded.created_at
                """,
                (
                    analysis_id,
                    json.dumps(register, ensure_ascii=False),
                    datetime.now(timezone.utc).isoformat(),
                ),
            )

    def load_register(self, analysis_id: str) -> dict | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT register FROM registres WHERE analysis_id = ?", (analysis_id,)
            ).fetchone()
        return json.loads(row["register"]) if row else None


__all__ = ["Storage"]