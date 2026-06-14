"""Pill tracking on Neon Postgres — one row per dose/supplement per day."""

from __future__ import annotations

import json
import logging
import os
from datetime import date
from pathlib import Path
from typing import Any

import psycopg
from psycopg.rows import dict_row

logger = logging.getLogger(__name__)

SUPPLEMENTS_KEY = "_supplements"
TABLE_NAME = "pill_tracking"

_SCHEMA_SQL = f"""
CREATE TABLE IF NOT EXISTS {TABLE_NAME} (
    track_date DATE NOT NULL,
    dose_id TEXT NOT NULL,
    entry_type TEXT NOT NULL DEFAULT 'dose',
    taken BOOLEAN NOT NULL DEFAULT FALSE,
    taken_at TEXT,
    when_context TEXT,
    PRIMARY KEY (track_date, dose_id)
);

CREATE INDEX IF NOT EXISTS idx_{TABLE_NAME}_track_date
    ON {TABLE_NAME} (track_date DESC);
"""


def _load_dotenv() -> None:
    try:
        from dotenv import load_dotenv

        root = Path(__file__).resolve().parent.parent.parent
        load_dotenv(root / ".env")
    except ImportError:
        pass


def neon_database_url() -> str | None:
    _load_dotenv()
    url = os.environ.get("NEON_DB") or os.environ.get("DATABASE_URL")
    if not url:
        return None
    return url.strip().strip("'\"")


def use_neon_db() -> bool:
    return bool(neon_database_url())


def _connect() -> psycopg.Connection:
    url = neon_database_url()
    if not url:
        raise RuntimeError("NEON_DB is not configured")
    return psycopg.connect(url, row_factory=dict_row)


def ensure_schema() -> None:
    with _connect() as conn:
        conn.execute(_SCHEMA_SQL)
        conn.commit()
    logger.info("Neon schema ready: %s", TABLE_NAME)


def _row_to_entry(row: dict[str, Any]) -> dict[str, Any]:
    if row["entry_type"] == "supplement":
        return {
            "taken": bool(row["taken"]),
            "when": row["when_context"],
            "taken_at": row["taken_at"],
        }
    return {
        "taken": bool(row["taken"]),
        "taken_at": row["taken_at"],
    }


def load_day(date_str: str) -> dict[str, Any]:
    """Return one day's tracking dict (same shape as tracking.json day)."""
    ensure_schema()
    track_date = date.fromisoformat(date_str)
    day: dict[str, Any] = {}

    with _connect() as conn:
        rows = conn.execute(
            f"""
            SELECT dose_id, entry_type, taken, taken_at, when_context
            FROM {TABLE_NAME}
            WHERE track_date = %s
            """,
            (track_date,),
        ).fetchall()

    supplements: dict[str, Any] = {}
    for row in rows:
        if row["entry_type"] == "supplement":
            supplements[row["dose_id"]] = _row_to_entry(row)
        else:
            day[row["dose_id"]] = _row_to_entry(row)

    if supplements:
        day[SUPPLEMENTS_KEY] = supplements
    return day


def load_tracking() -> dict[str, Any]:
    """Return full tracking dict keyed by YYYY-MM-DD."""
    ensure_schema()
    tracking: dict[str, Any] = {}

    with _connect() as conn:
        rows = conn.execute(
            f"""
            SELECT track_date, dose_id, entry_type, taken, taken_at, when_context
            FROM {TABLE_NAME}
            ORDER BY track_date
            """
        ).fetchall()

    for row in rows:
        date_str = row["track_date"].isoformat()
        day = tracking.setdefault(date_str, {})
        if row["entry_type"] == "supplement":
            supps = day.setdefault(SUPPLEMENTS_KEY, {})
            supps[row["dose_id"]] = _row_to_entry(row)
        else:
            day[row["dose_id"]] = _row_to_entry(row)

    return tracking


def save_day(date_str: str, day: dict[str, Any]) -> None:
    """Upsert all marks for a day; delete rows removed from the day dict."""
    ensure_schema()
    track_date = date.fromisoformat(date_str)

    dose_ids: set[str] = set()
    supplement_ids: set[str] = set()

    with _connect() as conn:
        for dose_id, entry in day.items():
            if dose_id.startswith("_"):
                continue
            if not isinstance(entry, dict):
                entry = {"taken": bool(entry), "taken_at": None}
            dose_ids.add(dose_id)
            conn.execute(
                f"""
                INSERT INTO {TABLE_NAME}
                    (track_date, dose_id, entry_type, taken, taken_at, when_context)
                VALUES (%s, %s, 'dose', %s, %s, NULL)
                ON CONFLICT (track_date, dose_id) DO UPDATE SET
                    entry_type = EXCLUDED.entry_type,
                    taken = EXCLUDED.taken,
                    taken_at = EXCLUDED.taken_at,
                    when_context = NULL
                """,
                (track_date, dose_id, bool(entry.get("taken", False)), entry.get("taken_at")),
            )

        supps = day.get(SUPPLEMENTS_KEY, {})
        if isinstance(supps, dict):
            for supp_id, entry in supps.items():
                if not isinstance(entry, dict):
                    entry = {"taken": bool(entry), "when": None, "taken_at": None}
                supplement_ids.add(supp_id)
                conn.execute(
                    f"""
                    INSERT INTO {TABLE_NAME}
                        (track_date, dose_id, entry_type, taken, taken_at, when_context)
                    VALUES (%s, %s, 'supplement', %s, %s, %s)
                    ON CONFLICT (track_date, dose_id) DO UPDATE SET
                        entry_type = EXCLUDED.entry_type,
                        taken = EXCLUDED.taken,
                        taken_at = EXCLUDED.taken_at,
                        when_context = EXCLUDED.when_context
                    """,
                    (
                        track_date,
                        supp_id,
                        bool(entry.get("taken", False)),
                        entry.get("taken_at"),
                        entry.get("when"),
                    ),
                )

        if dose_ids:
            conn.execute(
                f"""
                DELETE FROM {TABLE_NAME}
                WHERE track_date = %s
                  AND entry_type = 'dose'
                  AND dose_id <> ALL(%s)
                """,
                (track_date, list(dose_ids)),
            )
        else:
            conn.execute(
                f"DELETE FROM {TABLE_NAME} WHERE track_date = %s AND entry_type = 'dose'",
                (track_date,),
            )

        if supplement_ids:
            conn.execute(
                f"""
                DELETE FROM {TABLE_NAME}
                WHERE track_date = %s
                  AND entry_type = 'supplement'
                  AND dose_id <> ALL(%s)
                """,
                (track_date, list(supplement_ids)),
            )
        else:
            conn.execute(
                f"DELETE FROM {TABLE_NAME} WHERE track_date = %s AND entry_type = 'supplement'",
                (track_date,),
            )

        conn.commit()


def import_tracking_json(path: Path) -> int:
    """One-time import from tracking.json into Neon. Returns rows upserted."""
    if not path.exists():
        return 0
    with path.open(encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        return 0

    count = 0
    for date_str, day in data.items():
        if not isinstance(day, dict):
            continue
        save_day(date_str, day)
        count += len([k for k in day if not k.startswith("_")])
        supps = day.get(SUPPLEMENTS_KEY, {})
        if isinstance(supps, dict):
            count += len(supps)
    return count


def bootstrap_from_local_if_empty() -> int:
    """Import bundled/local tracking.json when Neon table has no rows."""
    ensure_schema()
    with _connect() as conn:
        row = conn.execute(f"SELECT COUNT(*) AS n FROM {TABLE_NAME}").fetchone()
        if row and row["n"] > 0:
            return 0

    from backend.services.data_loader import TRACKING_FILE

    imported = import_tracking_json(TRACKING_FILE)
    if imported:
        logger.info("Imported %s tracking rows from %s", imported, TRACKING_FILE)
    return imported
