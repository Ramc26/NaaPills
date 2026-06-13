"""Caregiver-controlled schedule: skip doses, disable medicines, add custom doses."""

from datetime import date, datetime, timedelta
from typing import Any

from backend.services.data_loader import MEDICINES_FILE, SCHEDULE_FILE, read_json
from backend.services.blob_storage import read_schedule, write_schedule

VALID_PERIODS = ("morning", "afternoon", "evening", "bedtime")


def _parse_date(value: str) -> date:
    return datetime.strptime(value, "%Y-%m-%d").date()


def _is_active(medicine: dict[str, Any], on_date: date) -> bool:
    start = _parse_date(medicine["start_date"])
    end = start + timedelta(days=medicine["duration_days"] - 1)
    return start <= on_date <= end

DEFAULT_SCHEDULE: dict[str, Any] = {
    "disabled_doses": [],
    "daily_skips": {},
    "custom_doses": [],
}


def _today_key(on_date: date | None = None) -> str:
    return (on_date or date.today()).isoformat()


def _load_schedule() -> dict[str, Any]:
    raw = read_schedule(SCHEDULE_FILE)
    if not raw:
        return dict(DEFAULT_SCHEDULE)
    return {
        "disabled_doses": list(raw.get("disabled_doses", [])),
        "daily_skips": dict(raw.get("daily_skips", {})),
        "custom_doses": list(raw.get("custom_doses", [])),
    }


def _save_schedule(data: dict[str, Any]) -> None:
    write_schedule(SCHEDULE_FILE, data)


def _all_definitions() -> list[dict[str, Any]]:
    """Bundled medicines plus caregiver-added custom doses."""
    bundled = read_json(MEDICINES_FILE)
    schedule = _load_schedule()
    custom = schedule.get("custom_doses", [])
    by_id = {m["id"]: m for m in bundled}
    for dose in custom:
        by_id[dose["id"]] = dose
    return list(by_id.values())


def _excluded_ids(on_date: date | None = None) -> set[str]:
    schedule = _load_schedule()
    key = _today_key(on_date)
    skipped = set(schedule.get("daily_skips", {}).get(key, []))
    disabled = set(schedule.get("disabled_doses", []))
    return skipped | disabled


def filter_active(doses: list[dict[str, Any]], on_date: date | None = None) -> list[dict[str, Any]]:
    """Remove disabled or skipped-for-today doses."""
    excluded = _excluded_ids(on_date)
    target = on_date or date.today()
    return [d for d in doses if d["id"] not in excluded and _is_active(d, target)]


def get_schedule_status(on_date: date | None = None) -> dict[str, Any]:
    """Admin view — every dose with active / skipped / disabled status."""
    target = on_date or date.today()
    schedule = _load_schedule()
    key = _today_key(target)
    skipped_today = set(schedule.get("daily_skips", {}).get(key, []))
    disabled = set(schedule.get("disabled_doses", []))
    custom_ids = {d["id"] for d in schedule.get("custom_doses", [])}

    rows = []
    for dose in sorted(_all_definitions(), key=lambda d: (d.get("period", ""), d.get("time", ""))):
        in_course = _is_active(dose, target)
        dose_id = dose["id"]
        if dose_id in disabled:
            status = "disabled"
        elif dose_id in skipped_today:
            status = "skipped_today"
        elif not in_course:
            status = "expired"
        else:
            status = "active"

        rows.append(
            {
                **dose,
                "status": status,
                "is_custom": dose_id in custom_ids,
                "in_course": in_course,
            }
        )

    return {
        "date": key,
        "doses": rows,
        "active_count": sum(1 for r in rows if r["status"] == "active"),
    }


def skip_today(dose_id: str, on_date: date | None = None) -> dict[str, Any]:
    """Hide a dose from today's schedule (e.g. no fever — skip Dolo afternoon)."""
    schedule = _load_schedule()
    key = _today_key(on_date)
    if dose_id not in {d["id"] for d in _all_definitions()}:
        raise ValueError(f"Dose not found: {dose_id}")

    daily = schedule.setdefault("daily_skips", {})
    skips = list(daily.get(key, []))
    if dose_id not in skips:
        skips.append(dose_id)
    daily[key] = skips
    _save_schedule(schedule)
    return get_schedule_status(on_date)


def unskip_today(dose_id: str, on_date: date | None = None) -> dict[str, Any]:
    schedule = _load_schedule()
    key = _today_key(on_date)
    daily = schedule.get("daily_skips", {})
    skips = [s for s in daily.get(key, []) if s != dose_id]
    if skips:
        daily[key] = skips
    elif key in daily:
        del daily[key]
    _save_schedule(schedule)
    return get_schedule_status(on_date)


def set_disabled(dose_id: str, disabled: bool = True) -> dict[str, Any]:
    """Permanently disable or re-enable a dose until changed again."""
    schedule = _load_schedule()
    if dose_id not in {d["id"] for d in _all_definitions()}:
        raise ValueError(f"Dose not found: {dose_id}")

    disabled_list = list(schedule.get("disabled_doses", []))
    if disabled and dose_id not in disabled_list:
        disabled_list.append(dose_id)
    elif not disabled:
        disabled_list = [d for d in disabled_list if d != dose_id]
    schedule["disabled_doses"] = disabled_list
    _save_schedule(schedule)
    return get_schedule_status()


def add_custom_dose(dose: dict[str, Any]) -> dict[str, Any]:
    """Add a new medicine dose to the schedule (caregiver-added)."""
    required = ("id", "name", "time", "period", "dose", "start_date", "duration_days")
    for field in required:
        if not dose.get(field):
            raise ValueError(f"Missing required field: {field}")

    period = dose["period"].lower()
    if period not in VALID_PERIODS:
        raise ValueError(f"Invalid period: {period}")

    _parse_date(dose["start_date"])

    schedule = _load_schedule()
    all_ids = {d["id"] for d in _all_definitions()}
    if dose["id"] in all_ids:
        raise ValueError(f"Dose id already exists: {dose['id']}")

    entry = {
        "id": dose["id"],
        "medicine_id": dose.get("medicine_id") or dose["id"].rsplit("_", 1)[0],
        "name": dose["name"],
        "time": dose["time"],
        "period": period,
        "dose": dose["dose"],
        "food": dose.get("food", "After Food"),
        "notes": dose.get("notes", ""),
        "duration_days": int(dose["duration_days"]),
        "start_date": dose["start_date"],
        "image": dose.get("image", "/images/placeholder.svg"),
    }
    schedule.setdefault("custom_doses", []).append(entry)
    _save_schedule(schedule)
    return get_schedule_status()


def remove_custom_dose(dose_id: str) -> dict[str, Any]:
    """Remove a caregiver-added dose."""
    schedule = _load_schedule()
    custom = schedule.get("custom_doses", [])
    if not any(d["id"] == dose_id for d in custom):
        raise ValueError(f"Custom dose not found: {dose_id}")

    schedule["custom_doses"] = [d for d in custom if d["id"] != dose_id]
    schedule["disabled_doses"] = [d for d in schedule.get("disabled_doses", []) if d != dose_id]
    for day, skips in list(schedule.get("daily_skips", {}).items()):
        schedule["daily_skips"][day] = [s for s in skips if s != dose_id]
    _save_schedule(schedule)
    return get_schedule_status()
