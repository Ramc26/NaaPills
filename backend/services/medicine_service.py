"""Medicine schedule logic — filter by period, date, active duration, and caregiver overrides."""

from datetime import date
from typing import Any

from backend.services import schedule_service

VALID_PERIODS = schedule_service.VALID_PERIODS


def get_all_medicines(on_date: date | None = None) -> list[dict[str, Any]]:
    """Return dose entries active today, excluding skipped/disabled."""
    target = on_date or date.today()
    medicines = schedule_service._all_definitions()
    active = [m for m in medicines if schedule_service._is_active(m, target)]
    return schedule_service.filter_active(active, target)


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
    for period in grouped:
        grouped[period].sort(key=lambda m: m["time"])
    return grouped
