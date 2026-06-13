"""JSON file I/O helpers — single source for all persistent storage."""

import json
import os
import shutil
from pathlib import Path
from typing import Any

# Bundled read-only data shipped with the app
BUNDLED_DATA_DIR = Path(__file__).resolve().parent.parent / "data"


def _resolve_data_dir() -> Path:
    """
    Local dev: write directly to backend/data/.
    Vercel: use /tmp (only writable path) and seed from bundled JSON.
    """
    override = os.environ.get("DATA_DIR")
    if override:
        data_dir = Path(override)
    elif os.environ.get("VERCEL"):
        data_dir = Path("/tmp/naapills/data")
    else:
        return BUNDLED_DATA_DIR

    data_dir.mkdir(parents=True, exist_ok=True)

    # Medicines schedule is read-only — always copy latest from bundle
    bundled_medicines = BUNDLED_DATA_DIR / "medicines.json"
    if bundled_medicines.exists():
        shutil.copy2(bundled_medicines, data_dir / "medicines.json")

    # Tracking starts empty; preserve existing /tmp file once created
    tracking = data_dir / "tracking.json"
    if not tracking.exists():
        tracking.write_text("{}\n", encoding="utf-8")

    return data_dir


DATA_DIR = _resolve_data_dir()
MEDICINES_FILE = DATA_DIR / "medicines.json"
TRACKING_FILE = DATA_DIR / "tracking.json"


def read_json(path: Path) -> Any:
    """Load JSON from disk; return empty list/dict when file is missing."""
    if not path.exists():
        return [] if path.name == "medicines.json" else {}
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def write_json(path: Path, data: Any) -> None:
    """Persist JSON to disk."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.write("\n")
