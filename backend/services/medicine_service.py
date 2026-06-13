"""Medicine schedule logic — filter by period, date, and active duration."""

from datetime import date, datetime, timedelta
from typing import Any

from backend.services.data_loader import MEDICINES_FILE, read_json

VALID_PERIODS = ("morning", "afternoon", "evening", "bedtime")


def _parse_date(value: str) -> date:
    return datetime.strptime(value, "%Y-%m-%d").date()


def _is_active(medicine: dict[str, Any], on_date: date) -> bool:
    """Medicine is active between start_date and start_date + duration_days."""
    start = _parse_date(medicine["start_date"])
    end = start + timedelta(days=medicine["duration_days"] - 1)
    return start <= on_date <= end


def get_all_medicines(on_date: date | None = None) -> list[dict[str, Any]]:
    """Return all dose entries that are active on the given date."""
    target = on_date or date.today()
    medicines = read_json(MEDICINES_FILE)
    return [m for m in medicines if _is_active(m, target)]


def get_medicines_by_period(period: str, on_date: date | None = None) -> list[dict[str, Any]]:
    """Return active medicines for a single period (morning/afternoon/evening/bedtime)."""
    period = period.lower()
    if period not in VALID_PERIODS:
        raise ValueError(f"Invalid period: {period}")
    return [m for m in get_all_medicines(on_date) if m["period"] == period]


def get_today_grouped(on_date: date | None = None) -> dict[str, list[dict[str, Any]]]:
    """Return all active medicines grouped by period."""
    grouped = {p: [] for p in VALID_PERIODS}
    for medicine in get_all_medicines(on_date):
        grouped[medicine["period"]].append(medicine)
    # Sort each period by scheduled time for predictable display order
    for period in grouped:
        grouped[period].sort(key=lambda m: m["time"])
    return grouped
