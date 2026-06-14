"""
Persistent JSON storage on Vercel Blob or local disk.

- tracking: naapills/tracking.json
- schedule: naapills/schedule.json (skips, disabled doses, custom medicines)
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
SCHEDULE_BLOB_PATH = "naapills/schedule.json"


def _blob_token() -> str | None:
    return os.environ.get("BLOB_READ_WRITE_TOKEN") or os.environ.get("VERCEL_BLOB_RW_TOKEN")


def use_blob_storage() -> bool:
    return bool(_blob_token())


def use_neon_tracking() -> bool:
    from backend.services.tracking_db import use_neon_db

    return use_neon_db()


def storage_mode() -> str:
    if use_neon_tracking():
        return "neon"
    if use_blob_storage():
        return "blob"
    if os.environ.get("VERCEL"):
        return "tmp"
    return "local"


def storage_note() -> str:
    mode = storage_mode()
    if mode == "neon":
        return (
            "Data is saved permanently on Neon Postgres (cloud). "
            "Not on Nannagaru's phone — not browser cache."
        )
    if mode == "blob":
        return (
            "Data is saved permanently on Vercel Blob (cloud). "
            "Not on Nannagaru's phone — not browser cache."
        )
    if mode == "tmp":
        return (
            "Data is on temporary server memory and may reset. "
            "Add Neon Postgres or Vercel Blob for permanent storage."
        )
    return "Data is saved locally in backend/data/ (dev mode)."


def _blob_headers(extra: dict[str, str] | None = None) -> dict[str, str]:
    token = _blob_token()
    if not token:
        raise RuntimeError("Blob token not configured")
    headers = {
        "Authorization": f"Bearer {token}",
        "x-api-version": "7",
    }
    if extra:
        headers.update(extra)
    return headers


def _blob_request(url: str, method: str = "GET", data: bytes | None = None, headers: dict | None = None):
    req = urllib.request.Request(url, data=data, headers=headers or {}, method=method)
    return urllib.request.urlopen(req, timeout=20)


def _parse_blob_json(resp) -> dict[str, Any]:
    raw = resp.read().decode("utf-8")
    if not raw.strip():
        return {}
    data = json.loads(raw)
    return data if isinstance(data, dict) else {}


def _read_blob_json(pathname: str) -> dict[str, Any]:
    """Read a JSON blob by pathname — direct path, then list fallback."""
    try:
        url = f"{BLOB_API}/{pathname}"
        with _blob_request(url, headers=_blob_headers()) as resp:
            data = _parse_blob_json(resp)
            if data:
                logger.info("Blob read OK (direct): %s", pathname)
                return data
    except urllib.error.HTTPError as exc:
        if exc.code != 404:
            logger.warning("Blob direct read HTTP %s for %s: %s", exc.code, pathname, exc.reason)
    except Exception as exc:
        logger.warning("Blob direct read error for %s: %s", pathname, exc)

    try:
        prefix = pathname.rsplit("/", 1)[0] + "/"
        query = urllib.parse.urlencode({"prefix": prefix})
        with _blob_request(f"{BLOB_API}?{query}", headers=_blob_headers()) as resp:
            listing = json.loads(resp.read().decode("utf-8"))

        filename = pathname.split("/")[-1]
        for blob in listing.get("blobs", []):
            blob_path = blob.get("pathname", "")
            if not blob_path.endswith(filename):
                continue
            blob_url = blob.get("downloadUrl") or blob.get("url")
            if not blob_url:
                continue
            with _blob_request(blob_url, headers=_blob_headers()) as resp:
                data = _parse_blob_json(resp)
                if data:
                    logger.info("Blob read OK (list): %s", blob_path)
                    return data
    except Exception as exc:
        logger.warning("Blob list read error for %s: %s", pathname, exc)

    return {}


def _write_blob_json(pathname: str, data: dict[str, Any]) -> None:
    body = json.dumps(data, indent=2, ensure_ascii=False).encode("utf-8")
    headers = _blob_headers(
        {
            "Content-Type": "application/json",
            "x-add-random-suffix": "false",
            "x-allow-overwrite": "true",
        }
    )
    with _blob_request(f"{BLOB_API}/{pathname}", method="PUT", data=body, headers=headers) as resp:
        result = json.loads(resp.read().decode("utf-8") or "{}")
        logger.info("Blob write OK: %s", result.get("pathname", pathname))


def _read_local_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    with path.open(encoding="utf-8") as f:
        data = json.load(f)
    return data if isinstance(data, dict) else {}


def _write_local_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.write("\n")


def read_blob_doc(local_path: Path, blob_path: str) -> dict[str, Any]:
    if use_blob_storage():
        return _read_blob_json(blob_path)
    return _read_local_json(local_path)


def write_blob_doc(local_path: Path, blob_path: str, data: dict[str, Any]) -> None:
    if use_blob_storage():
        _write_blob_json(blob_path, data)
        try:
            _write_local_json(local_path, data)
        except OSError:
            pass
        return
    _write_local_json(local_path, data)


def read_tracking(local_path: Path) -> dict[str, Any]:
    from backend.services.tracking_db import bootstrap_from_local_if_empty, load_tracking as load_neon_tracking, use_neon_db

    if use_neon_db():
        bootstrap_from_local_if_empty()
        return load_neon_tracking()
    return read_blob_doc(local_path, TRACKING_BLOB_PATH)


def write_tracking(local_path: Path, data: dict[str, Any]) -> None:
    from backend.services.tracking_db import save_day, use_neon_db

    if use_neon_db():
        for date_str, day in data.items():
            if isinstance(day, dict):
                save_day(date_str, day)
        return
    write_blob_doc(local_path, TRACKING_BLOB_PATH, data)


def read_schedule(local_path: Path) -> dict[str, Any]:
    return read_blob_doc(local_path, SCHEDULE_BLOB_PATH)


def write_schedule(local_path: Path, data: dict[str, Any]) -> None:
    write_blob_doc(local_path, SCHEDULE_BLOB_PATH, data)
