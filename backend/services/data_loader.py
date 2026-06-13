"""JSON file I/O helpers — single source for all persistent storage."""

import json
from pathlib import Path
from typing import Any

# Resolve data directory relative to this file (works locally and on Vercel)
DATA_DIR = Path(__file__).resolve().parent.parent / "data"
MEDICINES_FILE = DATA_DIR / "medicines.json"
TRACKING_FILE = DATA_DIR / "tracking.json"


def read_json(path: Path) -> Any:
    """Load JSON from disk; return empty list/dict when file is missing."""
    if not path.exists():
        return [] if path.name == "medicines.json" else {}
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def write_json(path: Path, data: Any) -> None:
    """Persist data atomically via a temp write."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.write("\n")
