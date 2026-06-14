"""Tracking persistence — Neon Postgres when configured, else blob/local JSON."""

from datetime import date
from typing import Any, Callable

from backend.services.data_loader import TRACKING_FILE
from backend.services.blob_storage import read_tracking, write_tracking
from backend.services import tracking_db

TRACKING_SAVE_RETRIES = 12


def today_key(on_date: date | None = None) -> str:
    return (on_date or date.today()).isoformat()


def load_tracking() -> dict[str, Any]:
    if tracking_db.use_neon_db():
        tracking_db.bootstrap_from_local_if_empty()
        return tracking_db.load_tracking()
    return read_tracking(TRACKING_FILE)


def save_tracking(data: dict[str, Any]) -> None:
    if tracking_db.use_neon_db():
        for date_str, day in data.items():
            if isinstance(day, dict):
                tracking_db.save_day(date_str, day)
        return
    write_tracking(TRACKING_FILE, data)


def normalize_entry(entry: Any) -> dict[str, Any]:
    if isinstance(entry, bool):
        return {"taken": entry, "taken_at": None}
    if isinstance(entry, dict):
        return {
            "taken": bool(entry.get("taken", False)),
            "taken_at": entry.get("taken_at"),
        }
    return {"taken": False, "taken_at": None}


def copy_day(day: dict[str, Any]) -> dict[str, Any]:
    copied = dict(day)
    supps = copied.get("_supplements")
    if isinstance(supps, dict):
        copied["_supplements"] = dict(supps)
    return copied


def dose_taken_map(day: dict[str, Any]) -> dict[str, bool]:
    return {
        dose_id: normalize_entry(entry)["taken"]
        for dose_id, entry in day.items()
        if not dose_id.startswith("_")
    }


def persist_day_update(on_date: date | None, apply_fn: Callable[[dict[str, Any]], None]) -> dict[str, Any]:
    """Apply updates for one day. Neon uses row upserts; blob uses read-modify-write retry."""
    key = today_key(on_date)

    if tracking_db.use_neon_db():
        tracking_db.ensure_schema()
        day = copy_day(tracking_db.load_day(key))
        apply_fn(day)
        tracking_db.save_day(key, day)
        return tracking_db.load_day(key)

    for _ in range(TRACKING_SAVE_RETRIES):
        tracking = load_tracking()
        day = copy_day(tracking.get(key, {}))
        before_taken = dose_taken_map(day)

        apply_fn(day)

        tracking = dict(tracking)
        tracking[key] = day
        save_tracking(tracking)

        fresh_day = load_tracking().get(key, {})
        after_taken = dose_taken_map(fresh_day)

        lost = any(
            was_taken and not after_taken.get(dose_id, False)
            for dose_id, was_taken in before_taken.items()
        )
        if not lost:
            return fresh_day

    return load_tracking().get(key, {})
