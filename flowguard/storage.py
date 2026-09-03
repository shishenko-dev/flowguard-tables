"""SQLite-backed run history for FlowGuard Tables."""

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3
from typing import Any


class RunStore:
    def __init__(self, path: Path):
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._initialise()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        return connection

    def _initialise(self) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS analysis_runs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    created_at TEXT NOT NULL,
                    total INTEGER NOT NULL,
                    attention INTEGER NOT NULL,
                    critical INTEGER NOT NULL,
                    duplicate_groups INTEGER NOT NULL,
                    anomalies INTEGER NOT NULL,
                    processing_ms REAL NOT NULL,
                    payload_json TEXT NOT NULL
                )
                """
            )

    def save(self, analysis: dict[str, Any]) -> int:
        summary = analysis["summary"]
        created_at = datetime.now(timezone.utc).isoformat()
        with self._connect() as connection:
            cursor = connection.execute(
                """
                INSERT INTO analysis_runs (
                    created_at, total, attention, critical, duplicate_groups,
                    anomalies, processing_ms, payload_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    created_at,
                    summary["total"],
                    summary["attention"],
                    summary["critical"],
                    summary["duplicate_groups"],
                    summary["anomalies"],
                    summary["processing_ms"],
                    json.dumps(analysis, ensure_ascii=False),
                ),
            )
            return int(cursor.lastrowid)

    def list_runs(self, limit: int = 10) -> list[dict[str, Any]]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT id, created_at, total, attention, critical,
                       duplicate_groups, anomalies, processing_ms
                FROM analysis_runs ORDER BY id DESC LIMIT ?
                """,
                (max(1, min(limit, 100)),),
            ).fetchall()
        return [dict(row) for row in rows]

    def latest(self) -> dict[str, Any] | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT payload_json FROM analysis_runs ORDER BY id DESC LIMIT 1"
            ).fetchone()
        return json.loads(row["payload_json"]) if row else None
