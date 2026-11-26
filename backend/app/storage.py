"""Local JSON-file storage for unit material and session logs. No database."""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Dict, List

from . import config

config.UNITS_DIR.mkdir(parents=True, exist_ok=True)
config.SESSIONS_DIR.mkdir(parents=True, exist_ok=True)


def _write_json(path: Path, data: Dict[str, Any]) -> None:
    tmp_path = path.with_suffix(".tmp")
    tmp_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    # On Windows, a sync client (OneDrive) or antivirus can hold the target
    # file open for a moment, and the atomic replace then fails with
    # "Access is denied". Seen in practice with this repo inside OneDrive.
    # Retry briefly rather than crash the request (e.g. a live tick).
    for attempt in range(6):
        try:
            tmp_path.replace(path)
            return
        except PermissionError:
            if attempt == 5:
                raise
            time.sleep(0.05 * (attempt + 1))


def _read_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


# --- Units ---

def unit_path(unit_id: str) -> Path:
    return config.UNITS_DIR / f"{unit_id}.json"


def save_unit(unit: Dict[str, Any]) -> None:
    _write_json(unit_path(unit["id"]), unit)


def load_unit(unit_id: str) -> Dict[str, Any]:
    return _read_json(unit_path(unit_id))


def unit_exists(unit_id: str) -> bool:
    return unit_path(unit_id).exists()


def list_units() -> List[Dict[str, Any]]:
    units = []
    for path in sorted(config.UNITS_DIR.glob("*.json")):
        data = _read_json(path)
        units.append(
            {
                "id": data["id"],
                "name": data["name"],
                "num_chunks": len(data["chunks"]),
                # Moodle course the unit belongs to (None for units made
                # with auth off) — used to scope what each teacher sees.
                "course_id": data.get("course_id"),
            }
        )
    return units


# --- Sessions ---

def session_path(session_id: str) -> Path:
    return config.SESSIONS_DIR / f"{session_id}.json"


def save_session(session: Dict[str, Any]) -> None:
    _write_json(session_path(session["id"]), session)


def load_session(session_id: str) -> Dict[str, Any]:
    return _read_json(session_path(session_id))


def session_exists(session_id: str) -> bool:
    return session_path(session_id).exists()
