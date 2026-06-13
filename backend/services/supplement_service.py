"""Flexible supplement tracking — Health-3R protein powder (any time of day)."""

from datetime import date, datetime
from typing import Any
from zoneinfo import ZoneInfo

from backend.services.data_loader import SUPPLEMENTS_FILE, read_json
from backend.services.tracking_service import (
    TZ,
    _format_taken_at,
    _load_tracking,
    _parse_taken_at,
    _save_tracking,
    _today_key,
)

SUPPLEMENTS_KEY = "_supplements"

WHEN_LABELS = {
    "breakfast": {"telugu": "ఫలహారం తరువాత", "english": "After breakfast"},
    "evening": {"telugu": "సాయంత్రం", "english": "Evening"},
    "bedtime": {"telugu": "నిద్రకు ముందు", "english": "Before sleep"},
}


def _parse_date(value: str) -> date:
    return datetime.strptime(value, "%Y-%m-%d").date()


def _is_active(supp: dict[str, Any], on_date: date) -> bool:
    from datetime import timedelta

    start = _parse_date(supp["start_date"])
    end = start + timedelta(days=supp["duration_days"] - 1)
    return start <= on_date <= end


def get_all_supplements(on_date: date | None = None) -> list[dict[str, Any]]:
    target = on_date or date.today()
    supplements = read_json(SUPPLEMENTS_FILE)
    return [s for s in supplements if _is_active(s, target)]


def infer_when(hour: int) -> str:
    """Guess when context from current hour."""
    if hour < 14:
        return "breakfast"
    if hour < 20:
        return "evening"
    return "bedtime"


def _get_day_supplements(on_date: date | None = None) -> dict[str, Any]:
    key = _today_key(on_date)
    tracking = _load_tracking()
    day = tracking.get(key, {})
    return day.get(SUPPLEMENTS_KEY, {})


def _when_display(when_id: str | None, taken_at: str | None) -> dict[str, str | None]:
    labels = WHEN_LABELS.get(when_id or "", {})
    taken_dt = _parse_taken_at(taken_at)
    return {
        "when": when_id,
        "when_telugu": labels.get("telugu"),
        "when_english": labels.get("english"),
        "taken_at_display": taken_dt.strftime("%I:%M %p") if taken_dt else None,
    }


def get_supplements_today(on_date: date | None = None) -> list[dict[str, Any]]:
    """Return today's flexible supplements with taken status and when logged."""
    supplements = get_all_supplements(on_date)
    logged = _get_day_supplements(on_date)
    result = []

    for supp in supplements:
        entry = logged.get(supp["id"], {})
        taken = bool(entry.get("taken", False))
        when = entry.get("when")
        taken_at = entry.get("taken_at")
        display = _when_display(when, taken_at)

        result.append(
            {
                **supp,
                "taken": taken,
                "when": when,
                "taken_at": taken_at,
                "when_telugu": display["when_telugu"],
                "when_english": display["when_english"],
                "taken_at_display": display["taken_at_display"],
                "colorClass": "med-" + supp["id"],
            }
        )

    return result


def log_supplement(
    supplement_id: str,
    when: str | None = None,
    on_date: date | None = None,
) -> dict[str, Any]:
    """Log one serving with when-context (breakfast / evening / bedtime)."""
    on_date = on_date or date.today()
    active_ids = {s["id"] for s in get_all_supplements(on_date)}
    if supplement_id not in active_ids:
        raise ValueError(f"Supplement not found: {supplement_id}")

    if when not in WHEN_LABELS:
        when = infer_when(datetime.now(TZ).hour)

    key = _today_key(on_date)
    tracking = _load_tracking()
    if key not in tracking:
        tracking[key] = {}
    if SUPPLEMENTS_KEY not in tracking[key]:
        tracking[key][SUPPLEMENTS_KEY] = {}

    now = datetime.now(TZ)
    tracking[key][SUPPLEMENTS_KEY][supplement_id] = {
        "taken": True,
        "when": when,
        "taken_at": _format_taken_at(now),
    }
    _save_tracking(tracking)

    return get_supplements_today(on_date)


def undo_supplement(supplement_id: str, on_date: date | None = None) -> dict[str, Any]:
    """Clear today's supplement log."""
    key = _today_key(on_date)
    tracking = _load_tracking()
    if key in tracking and SUPPLEMENTS_KEY in tracking[key]:
        tracking[key][SUPPLEMENTS_KEY].pop(supplement_id, None)
        _save_tracking(tracking)
    return get_supplements_today(on_date)
