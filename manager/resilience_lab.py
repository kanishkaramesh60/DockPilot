
"""Safety checks and persistent history for DockPilot Resilience Lab."""

import json
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock

CHAOS_LABEL = "dockpilot.chaos"
CHAOS_ALLOWED_VALUE = "allowed"

_HISTORY_FILE = Path(__file__).resolve().parent / "resilience_history.json"
_HISTORY_LOCK = Lock()


def is_eligible_container(container) -> bool:
    """Only allow containers that explicitly opt in."""
    labels = getattr(container, "labels", None) or {}
    return labels.get(CHAOS_LABEL) == CHAOS_ALLOWED_VALUE


def validate_experiment_target(container):
    """Validate and summarize an explicitly opted-in running container."""
    if container is None:
        raise ValueError("Container was not found.")

    if not is_eligible_container(container):
        raise ValueError(
            "Experiment blocked: container must have the label "
            "'dockpilot.chaos=allowed'."
        )

    status = getattr(container, "status", "unknown")
    if status != "running":
        raise ValueError(
            f"Experiment blocked: container must be running; current status is '{status}'."
        )

    return {
        "container_id": getattr(container, "short_id", ""),
        "container_name": getattr(container, "name", ""),
        "status": status,
        "eligible": True,
    }


def save_experiment(record):
    """Append one experiment record to local JSON history."""
    with _HISTORY_LOCK:
        _HISTORY_FILE.parent.mkdir(parents=True, exist_ok=True)

        try:
            history = json.loads(_HISTORY_FILE.read_text(encoding="utf-8"))
            if not isinstance(history, list):
                history = []
        except (FileNotFoundError, json.JSONDecodeError):
            history = []

        history.insert(0, record)
        history = history[:500]

        temporary_file = _HISTORY_FILE.with_suffix(".tmp")
        temporary_file.write_text(
            json.dumps(history, indent=2),
            encoding="utf-8",
        )
        temporary_file.replace(_HISTORY_FILE)

    return record


def get_experiment_history(limit=50):
    """Return recent experiment records, newest first."""
    with _HISTORY_LOCK:
        try:
            history = json.loads(_HISTORY_FILE.read_text(encoding="utf-8"))
        except (FileNotFoundError, json.JSONDecodeError):
            return []

    if not isinstance(history, list):
        return []

    return history[:limit]


def utc_now():
    """Return a timezone-aware ISO timestamp."""
    return datetime.now(timezone.utc).isoformat()
