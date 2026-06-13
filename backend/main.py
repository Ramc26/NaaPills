"""
Nannagaru Medicine Assistant — FastAPI backend.

Endpoints serve JSON medicine schedules and daily tracking.
Designed for Vercel serverless deployment with static frontend.
"""

import os
from datetime import date
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from backend.services import medicine_service, schedule_service, supplement_service, tracking_service
from backend.services.blob_storage import read_tracking, storage_mode, storage_note, use_blob_storage
from backend.services.data_loader import TRACKING_FILE

app = FastAPI(
    title="NaaPills API",
    description="Medicine reminder API for THR recovery",
    version="1.0.0",
)

# Allow frontend on Vercel or local dev
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class MarkTakenRequest(BaseModel):
    """Payload for marking a dose as taken."""

    dose_id: str = Field(..., description="Unique dose id, e.g. dolo_650_morning")
    taken: bool = Field(default=True, description="True = taken, False = undo")
    date: str | None = Field(default=None, description="YYYY-MM-DD, defaults to today")


class MarkTakenBatchRequest(BaseModel):
    """Mark all untaken doses in a period, or a specific list."""

    period: str | None = Field(default=None, description="morning/afternoon/evening/bedtime")
    dose_ids: list[str] | None = Field(default=None, description="Explicit dose ids")
    taken: bool = Field(default=True)
    date: str | None = Field(default=None, description="YYYY-MM-DD, defaults to today")


class CustomDoseRequest(BaseModel):
    """Add a caregiver-defined medicine dose."""

    id: str
    name: str
    time: str
    period: str
    dose: str
    start_date: str
    duration_days: int = 30
    food: str = "After Food"
    notes: str = ""
    image: str = "/images/placeholder.svg"
    medicine_id: str | None = None


class ScheduleActionRequest(BaseModel):
    """Skip/unskip/disable schedule actions."""

    dose_id: str
    date: str | None = Field(default=None, description="YYYY-MM-DD for skip/unskip")


@app.get("/api/medicines")
def list_medicines():
    """Return all active medicine doses for today."""
    return medicine_service.get_all_medicines()


@app.get("/api/medicines/{period}")
def list_medicines_by_period(period: str):
    """Return active doses for morning, afternoon, evening, or bedtime."""
    try:
        return medicine_service.get_medicines_by_period(period)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/today")
def today_grouped():
    """Return today's medicines grouped by period."""
    return medicine_service.get_today_grouped()


@app.get("/api/status/today")
def status_today():
    """Return today's completion progress and per-dose status."""
    return tracking_service.get_today_progress()


@app.get("/api/pilltrack")
def pilltrack(days: int = 30):
    """Caregiver dashboard — daily pill intake with timestamps (not linked from main UI)."""
    return tracking_service.get_pilltrack_report(days=min(days, 90))


@app.get("/api/health/storage")
def health_storage():
    """Debug: confirm tracking storage mode and whether blob has data."""
    tracking = read_tracking(TRACKING_FILE)
    return {
        "mode": storage_mode(),
        "blob_configured": use_blob_storage(),
        "tracking_days": len(tracking),
        "storage_note": storage_note(),
    }


class SupplementLogRequest(BaseModel):
    """Log a flexible supplement serving."""

    when: str | None = Field(
        default=None,
        description="breakfast, evening, or bedtime — auto-detected if omitted",
    )
    date: str | None = Field(default=None, description="YYYY-MM-DD, defaults to today")


@app.get("/api/supplements/today")
def supplements_today():
    """Return today's flexible supplements (e.g. Health-3R protein)."""
    return supplement_service.get_supplements_today()


@app.post("/api/supplements/{supplement_id}/log")
def log_supplement(supplement_id: str, body: SupplementLogRequest):
    """Log a supplement serving with when-context."""
    on_date = date.fromisoformat(body.date) if body.date else None
    try:
        supplements = supplement_service.log_supplement(supplement_id, body.when, on_date)
        progress = tracking_service.get_today_progress(on_date)
        return {"supplements": supplements, "progress": progress}
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post("/api/supplements/{supplement_id}/undo")
def undo_supplement(supplement_id: str, body: SupplementLogRequest):
    """Undo today's supplement log."""
    on_date = date.fromisoformat(body.date) if body.date else None
    supplements = supplement_service.undo_supplement(supplement_id, on_date)
    progress = tracking_service.get_today_progress(on_date)
    return {"supplements": supplements, "progress": progress}


@app.post("/api/mark-taken")
def mark_taken(body: MarkTakenRequest):
    """Mark a dose as taken (or undo)."""
    on_date = date.fromisoformat(body.date) if body.date else None

    active_ids = {m["id"] for m in medicine_service.get_all_medicines(on_date)}
    if body.dose_id not in active_ids:
        raise HTTPException(status_code=404, detail=f"Dose not found: {body.dose_id}")

    day_status = tracking_service.mark_taken(body.dose_id, body.taken, on_date)
    progress = tracking_service.get_today_progress(on_date)
    return {"status": day_status, "progress": progress}


@app.post("/api/mark-taken-batch")
def mark_taken_batch(body: MarkTakenBatchRequest):
    """Mark all doses in a period (or explicit list) as taken."""
    on_date = date.fromisoformat(body.date) if body.date else None

    if not body.period and not body.dose_ids:
        raise HTTPException(status_code=400, detail="Provide period or dose_ids")

    if body.period:
        try:
            active_ids = {m["id"] for m in medicine_service.get_medicines_by_period(body.period, on_date)}
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        dose_ids = list(active_ids)
    else:
        active_ids = {m["id"] for m in medicine_service.get_all_medicines(on_date)}
        dose_ids = [d for d in body.dose_ids if d in active_ids]
        if not dose_ids:
            raise HTTPException(status_code=404, detail="No valid dose ids")

    if body.taken:
        day_status = tracking_service.get_day_status(on_date)
        dose_ids = [d for d in dose_ids if not day_status.get(d, {}).get("taken", False)]

    if not dose_ids and body.taken:
        progress = tracking_service.get_today_progress(on_date)
        return {"status": tracking_service.get_day_status(on_date), "progress": progress, "marked": 0}

    day_status = tracking_service.mark_taken_batch(dose_ids, None, body.taken, on_date)
    progress = tracking_service.get_today_progress(on_date)
    return {"status": day_status, "progress": progress, "marked": len(dose_ids)}


@app.get("/api/schedule")
def get_schedule(date_str: str | None = None):
    """Caregiver schedule admin — all doses with skip/disable status."""
    on_date = date.fromisoformat(date_str) if date_str else None
    return schedule_service.get_schedule_status(on_date)


@app.post("/api/schedule/skip-today")
def schedule_skip_today(body: ScheduleActionRequest):
    on_date = date.fromisoformat(body.date) if body.date else None
    try:
        return schedule_service.skip_today(body.dose_id, on_date)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post("/api/schedule/unskip-today")
def schedule_unskip_today(body: ScheduleActionRequest):
    on_date = date.fromisoformat(body.date) if body.date else None
    try:
        return schedule_service.unskip_today(body.dose_id, on_date)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post("/api/schedule/disable/{dose_id}")
def schedule_disable(dose_id: str):
    try:
        return schedule_service.set_disabled(dose_id, True)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post("/api/schedule/enable/{dose_id}")
def schedule_enable(dose_id: str):
    try:
        return schedule_service.set_disabled(dose_id, False)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post("/api/schedule/add")
def schedule_add(body: CustomDoseRequest):
    try:
        return schedule_service.add_custom_dose(body.model_dump())
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.delete("/api/schedule/dose/{dose_id}")
def schedule_remove(dose_id: str):
    try:
        return schedule_service.remove_custom_dose(dose_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


# Caregiver dashboard — not linked from main UI
@app.get("/pilltrack")
def pilltrack_page():
    page = Path(__file__).resolve().parent.parent / "frontend" / "pilltrack.html"
    if page.exists():
        return FileResponse(page)
    raise HTTPException(status_code=404, detail="Pill track page not found")


# Serve frontend static files locally (Vercel serves static files separately)
if not os.environ.get("VERCEL"):
    FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"
    if FRONTEND_DIR.exists():
        app.mount("/", StaticFiles(directory=str(FRONTEND_DIR), html=True), name="frontend")
