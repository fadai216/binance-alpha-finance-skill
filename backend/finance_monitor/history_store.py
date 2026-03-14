from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any


class FinanceHistoryStore:
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
                CREATE TABLE IF NOT EXISTS finance_runs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    updated_at TEXT NOT NULL,
                    source TEXT,
                    product_count INTEGER NOT NULL,
                    activity_count INTEGER NOT NULL,
                    diagnostics_json TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS finance_products (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_id INTEGER NOT NULL,
                    rank_index INTEGER NOT NULL,
                    product_id TEXT,
                    product_name TEXT NOT NULL,
                    product_type TEXT NOT NULL,
                    asset TEXT,
                    apr REAL NOT NULL,
                    term_days INTEGER NOT NULL,
                    min_purchase_amount TEXT,
                    available_balance TEXT,
                    reward_label TEXT,
                    reward_type TEXT,
                    source TEXT,
                    FOREIGN KEY(run_id) REFERENCES finance_runs(id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS finance_activities (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_id INTEGER NOT NULL,
                    rank_index INTEGER NOT NULL,
                    title TEXT NOT NULL,
                    activity_type TEXT NOT NULL,
                    participation_condition TEXT,
                    reward_summary TEXT,
                    reward_type TEXT,
                    status TEXT NOT NULL,
                    article_code TEXT,
                    publish_date TEXT,
                    end_time TEXT,
                    source TEXT,
                    FOREIGN KEY(run_id) REFERENCES finance_runs(id) ON DELETE CASCADE
                );

                CREATE INDEX IF NOT EXISTS idx_finance_runs_updated_at ON finance_runs(updated_at DESC);
                CREATE INDEX IF NOT EXISTS idx_finance_products_run_id ON finance_products(run_id);
                CREATE INDEX IF NOT EXISTS idx_finance_activities_run_id ON finance_activities(run_id);
                """
            )
            self._ensure_column(connection, "finance_products", "product_id", "TEXT")
            self._ensure_column(connection, "finance_products", "source", "TEXT")

    @staticmethod
    def _ensure_column(connection: sqlite3.Connection, table_name: str, column_name: str, column_type: str) -> None:
        columns = {
            row["name"]
            for row in connection.execute(f"PRAGMA table_info({table_name})").fetchall()
        }
        if column_name not in columns:
            connection.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_type}")

    def persist_snapshot(self, snapshot: dict[str, Any]) -> None:
        products = snapshot.get("products") or []
        activities = snapshot.get("activities") or []
        diagnostics = snapshot.get("diagnostics")

        with self._connect() as connection:
            cursor = connection.execute(
                """
                INSERT INTO finance_runs (
                    updated_at,
                    source,
                    product_count,
                    activity_count,
                    diagnostics_json
                ) VALUES (?, ?, ?, ?, ?)
                """,
                (
                    snapshot["updated_at"],
                    snapshot.get("source"),
                    len(products),
                    len(activities),
                    json.dumps(diagnostics, ensure_ascii=False) if diagnostics is not None else None,
                ),
            )
            run_id = int(cursor.lastrowid)

            connection.executemany(
                """
                INSERT INTO finance_products (
                    run_id,
                    rank_index,
                    product_id,
                    product_name,
                    product_type,
                    asset,
                    apr,
                    term_days,
                    min_purchase_amount,
                    available_balance,
                    reward_label,
                    reward_type,
                    source
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        run_id,
                        index + 1,
                        item.get("product_id"),
                        item["product_name"],
                        item["product_type"],
                        item.get("asset"),
                        float(item.get("apr") or 0),
                        int(item.get("term_days") or 0),
                        item.get("min_purchase_amount"),
                        item.get("available_balance"),
                        item.get("reward_label"),
                        item.get("reward_type"),
                        item.get("source"),
                    )
                    for index, item in enumerate(products)
                ],
            )

            connection.executemany(
                """
                INSERT INTO finance_activities (
                    run_id,
                    rank_index,
                    title,
                    activity_type,
                    participation_condition,
                    reward_summary,
                    reward_type,
                    status,
                    article_code,
                    publish_date,
                    end_time,
                    source
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        run_id,
                        index + 1,
                        item["title"],
                        item["activity_type"],
                        item.get("participation_condition"),
                        item.get("reward_summary"),
                        item.get("reward_type"),
                        item["status"],
                        item.get("article_code"),
                        item.get("publish_date"),
                        item.get("end_time"),
                        item.get("source"),
                    )
                    for index, item in enumerate(activities)
                ],
            )
            connection.commit()

    def fetch_recent_snapshots(self, limit: int) -> list[dict[str, Any]]:
        limit = max(1, limit)
        with self._connect() as connection:
            run_rows = connection.execute(
                """
                SELECT id, updated_at
                FROM finance_runs
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
                    "products": [],
                    "activities": [],
                }
                for row in run_rows
            }

            placeholders = ",".join("?" for _ in ordered_run_ids)
            product_rows = connection.execute(
                f"""
                SELECT run_id, product_id, product_name, product_type, asset, apr, term_days,
                       min_purchase_amount, available_balance, reward_label, reward_type, source
                FROM finance_products
                WHERE run_id IN ({placeholders})
                ORDER BY run_id DESC, rank_index ASC
                """,
                ordered_run_ids,
            ).fetchall()

            for row in product_rows:
                snapshots[int(row["run_id"])]["products"].append(
                    {
                        "product_id": row["product_id"] or self._build_legacy_product_id(
                            product_type=row["product_type"],
                            asset=row["asset"],
                            term_days=row["term_days"],
                            product_name=row["product_name"],
                        ),
                        "product_name": row["product_name"],
                        "product_type": row["product_type"],
                        "asset": row["asset"],
                        "apr": float(row["apr"]),
                        "term_days": int(row["term_days"]),
                        "min_purchase_amount": row["min_purchase_amount"],
                        "available_balance": row["available_balance"],
                        "reward_label": row["reward_label"],
                        "reward_type": row["reward_type"],
                        "source": row["source"] or self._build_legacy_source(row["product_type"]),
                    }
                )

            activity_rows = connection.execute(
                f"""
                SELECT run_id, title, activity_type, participation_condition, reward_summary,
                       reward_type, status, article_code, publish_date, end_time, source
                FROM finance_activities
                WHERE run_id IN ({placeholders})
                ORDER BY run_id DESC, rank_index ASC
                """,
                ordered_run_ids,
            ).fetchall()

            for row in activity_rows:
                snapshots[int(row["run_id"])]["activities"].append(
                    {
                        "title": row["title"],
                        "activity_type": row["activity_type"],
                        "participation_condition": row["participation_condition"],
                        "reward_summary": row["reward_summary"],
                        "reward_type": row["reward_type"],
                        "status": row["status"],
                        "article_code": row["article_code"],
                        "publish_date": row["publish_date"],
                        "end_time": row["end_time"],
                        "source": row["source"],
                    }
                )

        return [snapshots[run_id] for run_id in ordered_run_ids]

    @staticmethod
    def _build_legacy_product_id(
        *,
        product_type: str,
        asset: str | None,
        term_days: int,
        product_name: str,
    ) -> str:
        asset_part = (asset or "unknown").strip().lower()
        name_part = "".join(ch if ch.isalnum() else "-" for ch in product_name.strip().lower()).strip("-")
        return f"{product_type}:{asset_part}:{int(term_days or 0)}:{name_part}"

    @staticmethod
    def _build_legacy_source(product_type: str) -> str:
        if product_type == "activity":
            return "activity-derived"
        if product_type in {"flexible", "locked"}:
            return "public-finance-fallback"
        return "public-finance-fallback"
