"""
Persistent tracking storage.

- Local dev: backend/data/tracking.json
- Vercel + Blob store: naapills/tracking.json on Vercel Blob (free Hobby tier)
- Vercel without Blob: falls back to /tmp (ephemeral — not recommended)
"""

import json
import logging
import os
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

BLOB_API = "https://blob.vercel-storage.com"
TRACKING_BLOB_PATH = "naapills/tracking.json"


def use_blob_storage() -> bool:
    return bool(os.environ.get("BLOB_READ_WRITE_TOKEN"))


def storage_mode() -> str:
    if use_blob_storage():
        return "blob"
    if os.environ.get("VERCEL"):
        return "tmp"
    return "local"


def storage_note() -> str:
    mode = storage_mode()
    if mode == "blob":
        return (
            "Data is saved permanently on Vercel Blob (cloud). "
            "Not on Nannagaru's phone — not browser cache."
        )
    if mode == "tmp":
        return (
            "Data is on temporary server memory and may reset. "
            "Add a Vercel Blob store for permanent storage."
        )
    return "Data is saved locally in backend/data/tracking.json (dev mode)."


def _blob_headers(extra: dict[str, str] | None = None) -> dict[str, str]:
    headers = {
        "Authorization": f"Bearer {os.environ['BLOB_READ_WRITE_TOKEN']}",
        "x-api-version": "7",
    }
    if extra:
        headers.update(extra)
    return headers


def _blob_request(url: str, method: str = "GET", data: bytes | None = None, headers: dict | None = None):
    req = urllib.request.Request(url, data=data, headers=headers or {}, method=method)
    return urllib.request.urlopen(req, timeout=15)


def _read_blob_tracking() -> dict[str, Any]:
    """Read tracking JSON from Vercel Blob."""
    try:
        query = urllib.parse.urlencode({"prefix": "naapills/tracking"})
        with _blob_request(f"{BLOB_API}?{query}", headers=_blob_headers()) as resp:
            listing = json.loads(resp.read().decode("utf-8"))

        blobs = listing.get("blobs", [])
        if not blobs:
            return {}

        blob_url = blobs[0]["url"]
        with _blob_request(blob_url, headers=_blob_headers()) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            return {}
        logger.warning("Blob read failed (%s): %s", exc.code, exc.reason)
        return {}
    except Exception as exc:
        logger.warning("Blob read error: %s", exc)
        return {}


def _write_blob_tracking(data: dict[str, Any]) -> None:
    """Write tracking JSON to Vercel Blob (overwrite same path)."""
    body = json.dumps(data, indent=2, ensure_ascii=False).encode("utf-8")
    headers = _blob_headers(
        {
            "Content-Type": "application/json",
            "x-add-random-suffix": "false",
            "x-allow-overwrite": "true",
        }
    )
    try:
        _blob_request(f"{BLOB_API}/{TRACKING_BLOB_PATH}", method="PUT", data=body, headers=headers)
    except Exception as exc:
        logger.error("Blob write failed: %s", exc)
        raise


def read_tracking(local_path: Path) -> dict[str, Any]:
    if use_blob_storage():
        return _read_blob_tracking()
    if not local_path.exists():
        return {}
    with local_path.open(encoding="utf-8") as f:
        return json.load(f)


def write_tracking(local_path: Path, data: dict[str, Any]) -> None:
    if use_blob_storage():
        _write_blob_tracking(data)
        return
    local_path.parent.mkdir(parents=True, exist_ok=True)
    with local_path.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.write("\n")
