"""Daily dose completion tracking with timestamps for caregiver dashboard."""

from datetime import date, datetime, timedelta, timezone
from typing import Any
from zoneinfo import ZoneInfo

from backend.services.data_loader import TRACKING_FILE
from backend.services import supplement_service
from backend.services.blob_storage import read_tracking, storage_mode, storage_note, write_tracking
from backend.services.medicine_service import get_all_medicines

# IST for Nannagaru's timezone
TZ = ZoneInfo("Asia/Kolkata")
ON_TIME_WINDOW_MINUTES = 15


def _today_key(on_date: date | None = None) -> str:
    return (on_date or date.today()).isoformat()


def _load_tracking() -> dict[str, Any]:
    return read_tracking(TRACKING_FILE)


def _save_tracking(data: dict[str, Any]) -> None:
    write_tracking(TRACKING_FILE, data)


def _normalize_entry(entry: Any) -> dict[str, Any]:
    """Support legacy boolean entries and new object format."""
    if isinstance(entry, bool):
        return {"taken": entry, "taken_at": None}
    if isinstance(entry, dict):
        return {
            "taken": bool(entry.get("taken", False)),
            "taken_at": entry.get("taken_at"),
        }
    return {"taken": False, "taken_at": None}


def _is_taken(entry: Any) -> bool:
    return _normalize_entry(entry)["taken"]


def _time_to_minutes(time_str: str) -> int:
    import re

    match = re.match(r"(\d{1,2}):(\d{2})\s*(AM|PM)", time_str, re.I)
    if not match:
        return 0
    hours = int(match.group(1)) % 12
    if match.group(3).upper() == "PM":
        hours += 12
    return hours * 60 + int(match.group(2))


def _parse_taken_at(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=TZ)
        return dt.astimezone(TZ)
    except ValueError:
        return None


def _format_taken_at(dt: datetime) -> str:
    return dt.astimezone(TZ).isoformat()


def get_day_status(on_date: date | None = None) -> dict[str, dict[str, Any]]:
    """Return {dose_id: {taken, taken_at}} for the given date (pills only)."""
    key = _today_key(on_date)
    tracking = _load_tracking()
    raw = tracking.get(key, {})
    return {
        dose_id: _normalize_entry(entry)
        for dose_id, entry in raw.items()
        if not dose_id.startswith("_")
    }


def mark_taken(dose_id: str, taken: bool = True, on_date: date | None = None) -> dict[str, Any]:
    """Mark a single dose as taken or not taken, recording timestamp when taken."""
    key = _today_key(on_date)
    tracking = _load_tracking()
    if key not in tracking:
        tracking[key] = {}

    if taken:
        tracking[key][dose_id] = {
            "taken": True,
            "taken_at": _format_taken_at(datetime.now(TZ)),
        }
    else:
        tracking[key][dose_id] = {"taken": False, "taken_at": None}

    _save_tracking(tracking)
    return {
        d: _normalize_entry(e) for d, e in tracking[key].items() if not d.startswith("_")
    }


def get_today_progress(on_date: date | None = None) -> dict[str, Any]:
    """Compute today's progress across pills + flexible supplements."""
    medicines = get_all_medicines(on_date)
    supplements = supplement_service.get_supplements_today(on_date)
    day_status = get_day_status(on_date)

    pill_taken = sum(1 for m in medicines if day_status.get(m["id"], {}).get("taken", False))
    supp_taken = sum(1 for s in supplements if s.get("taken"))
    total = len(medicines) + len(supplements)
    taken = pill_taken + supp_taken
    percentage = round((taken / total) * 100) if total else 0

    doses = []
    for m in medicines:
        status = day_status.get(m["id"], {"taken": False, "taken_at": None})
        doses.append({**m, "taken": status["taken"], "taken_at": status.get("taken_at")})

    return {
        "date": _today_key(on_date),
        "total": total,
        "taken": taken,
        "pill_total": len(medicines),
        "pill_taken": pill_taken,
        "remaining": total - taken,
        "percentage": percentage,
        "all_taken": taken == total and total > 0,
        "doses": doses,
        "supplements": supplements,
    }


def _dose_timing_info(medicine: dict[str, Any], taken_at: str | None) -> dict[str, Any]:
    """Compare scheduled time vs actual taken time."""
    scheduled_min = _time_to_minutes(medicine["time"])
    taken_dt = _parse_taken_at(taken_at)

    if not taken_dt:
        return {
            "on_time": None,
            "minutes_delta": None,
            "taken_at_display": None,
            "taken_at_time": None,
        }

    taken_min = taken_dt.hour * 60 + taken_dt.minute
    delta = taken_min - scheduled_min
    on_time = abs(delta) <= ON_TIME_WINDOW_MINUTES

    return {
        "on_time": on_time,
        "minutes_delta": delta,
        "taken_at_display": taken_dt.strftime("%I:%M %p"),
        "taken_at_time": taken_dt.strftime("%H:%M:%S"),
    }


def _pilltrack_summary(total_days: int = 0, perfect_days: int = 0) -> dict[str, Any]:
    return {
        "total_days": total_days,
        "perfect_days": perfect_days,
        "on_time_window_minutes": ON_TIME_WINDOW_MINUTES,
        "storage": storage_mode(),
        "storage_note": storage_note(),
    }


def get_pilltrack_report(days: int = 30) -> dict[str, Any]:
    """
    Caregiver dashboard data — daily breakdown with taken times and on-time status.
    Returns most recent days first.
    """
    tracking = _load_tracking()
    if not tracking:
        return {"days": [], "summary": _pilltrack_summary()}

    sorted_dates = sorted(tracking.keys(), reverse=True)[:days]
    report_days = []
    perfect_days = 0

    for date_str in sorted_dates:
        on_date = date.fromisoformat(date_str)
        medicines = get_all_medicines(on_date)
        day_raw = tracking.get(date_str, {})
        day_status = {
            d: _normalize_entry(e) for d, e in day_raw.items() if not d.startswith("_")
        }

        dose_rows = []
        taken_count = 0
        on_time_count = 0
        timed_taken_count = 0

        for med in medicines:
            status = day_status.get(med["id"], {"taken": False, "taken_at": None})
            taken = status["taken"]
            timing = _dose_timing_info(med, status.get("taken_at") if taken else None)

            if taken:
                taken_count += 1
                if timing["on_time"] is True:
                    on_time_count += 1
                if timing["taken_at_display"]:
                    timed_taken_count += 1

            dose_rows.append(
                {
                    "id": med["id"],
                    "name": med["name"],
                    "dose": med["dose"],
                    "period": med["period"],
                    "scheduled_time": med["time"],
                    "taken": taken,
                    "taken_at": status.get("taken_at"),
                    "taken_at_display": timing["taken_at_display"],
                    "on_time": timing["on_time"],
                    "minutes_delta": timing["minutes_delta"],
                    "minutes_delta_label": _delta_label(timing["minutes_delta"]),
                }
            )

        total = len(medicines)
        all_taken = taken_count == total and total > 0

        dose_rows.sort(key=lambda d: _time_to_minutes(d["scheduled_time"]))

        # Flexible supplements
        supp_logged = day_raw.get("_supplements", {})
        for supp in supplement_service.get_all_supplements(on_date):
            entry = supp_logged.get(supp["id"], {})
            if not isinstance(entry, dict):
                entry = {"taken": bool(entry), "when": None, "taken_at": None}
            taken = bool(entry.get("taken", False))
            when = entry.get("when") if isinstance(entry.get("when"), str) else None
            taken_at = entry.get("taken_at")
            labels = supplement_service.WHEN_LABELS.get(when or "", {})
            taken_dt = _parse_taken_at(taken_at) if taken else None

            if taken:
                taken_count += 1

            dose_rows.append(
                {
                    "id": supp["id"],
                    "name": supp["name"],
                    "dose": supp["dose"],
                    "period": "flexible",
                    "scheduled_time": labels.get("english", "Any time"),
                    "taken": taken,
                    "taken_at": taken_at,
                    "taken_at_display": taken_dt.strftime("%I:%M %p") if taken_dt else None,
                    "on_time": None,
                    "minutes_delta": None,
                    "minutes_delta_label": labels.get("english") if taken else None,
                    "when_telugu": labels.get("telugu"),
                }
            )

        total = len(medicines) + len(supplement_service.get_all_supplements(on_date))
        all_taken = taken_count == total and total > 0
        if all_taken:
            perfect_days += 1

        report_days.append(
            {
                "date": date_str,
                "date_display": on_date.strftime("%a, %d %b %Y"),
                "total": total,
                "taken": taken_count,
                "remaining": total - taken_count,
                "percentage": round((taken_count / total) * 100) if total else 0,
                "all_taken": all_taken,
                "on_time_count": on_time_count,
                "doses": dose_rows,
            }
        )

    return {
        "days": report_days,
        "summary": _pilltrack_summary(len(report_days), perfect_days),
    }


def _delta_label(minutes: int | None) -> str | None:
    if minutes is None:
        return None
    if minutes == 0:
        return "On time"
    if minutes > 0:
        return f"{minutes} min late"
    return f"{abs(minutes)} min early"
