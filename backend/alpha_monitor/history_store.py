from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any


class HistoryStore:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA journal_mode=WAL")
        return connection

    def _init_schema(self) -> None:
        with self._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS runs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    updated_at TEXT NOT NULL,
                    source TEXT,
                    window_minutes INTEGER NOT NULL,
                    token_count INTEGER NOT NULL,
                    recommendation TEXT NOT NULL,
                    alerts_json TEXT NOT NULL,
                    diagnostics_json TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS analysis_items (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_id INTEGER NOT NULL,
                    rank_index INTEGER NOT NULL,
                    symbol TEXT NOT NULL,
                    market_symbol TEXT,
                    chain_name TEXT,
                    volatility REAL NOT NULL,
                    spread REAL NOT NULL,
                    score REAL NOT NULL,
                    error TEXT,
                    FOREIGN KEY(run_id) REFERENCES runs(id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS alert_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    updated_at TEXT NOT NULL,
                    alert_type TEXT NOT NULL,
                    symbol TEXT,
                    message TEXT NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_runs_updated_at ON runs(updated_at DESC);
                CREATE INDEX IF NOT EXISTS idx_analysis_items_run_id ON analysis_items(run_id);
                CREATE INDEX IF NOT EXISTS idx_alert_events_updated_at ON alert_events(updated_at DESC);
                """
            )

    def persist_report(self, report: dict[str, Any]) -> None:
        analysis = report.get("analysis") or []
        alerts = report.get("alerts") or []
        diagnostics = report.get("diagnostics")

        with self._connect() as connection:
            cursor = connection.execute(
                """
                INSERT INTO runs (
                    updated_at,
                    source,
                    window_minutes,
                    token_count,
                    recommendation,
                    alerts_json,
                    diagnostics_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    report["updated_at"],
                    report.get("source"),
                    int(report.get("window_minutes") or 60),
                    len(analysis),
                    report.get("recommendation") or "",
                    json.dumps(alerts, ensure_ascii=False),
                    json.dumps(diagnostics, ensure_ascii=False) if diagnostics is not None else None,
                ),
            )
            run_id = int(cursor.lastrowid)

            connection.executemany(
                """
                INSERT INTO analysis_items (
                    run_id,
                    rank_index,
                    symbol,
                    market_symbol,
                    chain_name,
                    volatility,
                    spread,
                    score,
                    error
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        run_id,
                        index + 1,
                        item["symbol"],
                        item.get("market_symbol"),
                        item.get("chain_name"),
                        float(item["volatility"]),
                        float(item["spread"]),
                        float(item["score"]),
                        item.get("error"),
                    )
                    for index, item in enumerate(analysis)
                ],
            )

            alert_rows: list[tuple[str, str, str | None, str]] = []
            for alert in alerts:
                alert_type = "new_token" if alert.startswith("🔔") else "high_volatility"
                symbols = self._extract_symbols(alert)
                if symbols:
                    for symbol in symbols:
                        alert_rows.append((report["updated_at"], alert_type, symbol, alert))
                else:
                    alert_rows.append((report["updated_at"], alert_type, None, alert))

            if alert_rows:
                connection.executemany(
                    """
                    INSERT INTO alert_events (updated_at, alert_type, symbol, message)
                    VALUES (?, ?, ?, ?)
                    """,
                    alert_rows,
                )

            connection.commit()

    def fetch_recent_snapshots(self, limit: int) -> list[dict[str, Any]]:
        limit = max(1, limit)
        with self._connect() as connection:
            run_rows = connection.execute(
                """
                SELECT id, updated_at, alerts_json
                FROM runs
                ORDER BY updated_at DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()

            if not run_rows:
                return []

            ordered_run_ids = [int(row["id"]) for row in run_rows]
            snapshots = {
                int(row["id"]): {
                    "timestamp": row["updated_at"],
                    "analysis": [],
                    "alerts": json.loads(row["alerts_json"] or "[]"),
                }
                for row in run_rows
            }

            placeholders = ",".join("?" for _ in ordered_run_ids)
            analysis_rows = connection.execute(
                f"""
                SELECT run_id, symbol, volatility, spread, score
                FROM analysis_items
                WHERE run_id IN ({placeholders})
                ORDER BY run_id DESC, rank_index ASC
                """,
                ordered_run_ids,
            ).fetchall()

            for row in analysis_rows:
                snapshots[int(row["run_id"])]["analysis"].append(
                    {
                        "symbol": row["symbol"],
                        "volatility": float(row["volatility"]),
                        "spread": float(row["spread"]),
                        "score": float(row["score"]),
                    }
                )

        return [snapshots[run_id] for run_id in ordered_run_ids]

    @staticmethod
    def _extract_symbols(alert_text: str) -> list[str]:
        if ":" not in alert_text:
            return []
        return [item.strip() for item in alert_text.split(":", 1)[1].split(",") if item.strip()]
