
from __future__ import annotations

import json
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent
STATE_DIR = PROJECT_ROOT / "reports"
EVENT_FILE = STATE_DIR / "container_health_events.jsonl"
STATE_FILE = STATE_DIR / "container_health_state.json"

DEFAULT_MAX_RESTARTS = 3
DEFAULT_WINDOW_SECONDS = 900


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _docker(
    *args: str,
    timeout: int = 10,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["docker", *args],
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )


def _read_json(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return default


def _write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(
        json.dumps(data, indent=2),
        encoding="utf-8",
    )
    temp.replace(path)


def _append_event(event: dict[str, Any]) -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    with EVENT_FILE.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(event, ensure_ascii=False) + "\n")


def _inspect_containers() -> list[dict[str, Any]]:
    listed = _docker("ps", "-aq")

    if listed.returncode:
        raise RuntimeError(
            listed.stderr.strip()
            or "Docker could not list containers."
        )

    ids = [
        value.strip()
        for value in listed.stdout.splitlines()
        if value.strip()
    ]

    if not ids:
        return []

    inspected = _docker("inspect", *ids)

    if inspected.returncode:
        raise RuntimeError(
            inspected.stderr.strip()
            or "Docker inspect failed."
        )

    output = []

    for item in json.loads(inspected.stdout):
        state = item.get("State") or {}
        config = item.get("Config") or {}
        health = state.get("Health") or {}
        logs = health.get("Log") or []
        last = logs[-1] if logs else {}

        output.append({
            "id": item.get("Id", "")[:12],
            "name": (item.get("Name") or "").lstrip("/"),
            "image": config.get("Image", ""),
            "state": state.get("Status", "unknown"),
            "running": bool(state.get("Running")),
            "health": health.get("Status", "not_configured"),
            "healthcheck_configured": bool(
                config.get("Healthcheck")
            ),
            "health_output": (
                last.get("Output") or ""
            ).strip()[-1000:],
            "exit_code": state.get("ExitCode"),
        })

    return output


def check_containers(
    *,
    auto_recover: bool = False,
    max_restarts: int = DEFAULT_MAX_RESTARTS,
    window_seconds: int = DEFAULT_WINDOW_SECONDS,
) -> dict[str, Any]:
    """
    Check Docker container health.

    Optional recovery restarts only running unhealthy containers.
    Restart attempts are rate-limited per container.
    """

    if max_restarts < 0 or window_seconds <= 0:
        raise ValueError(
            "max_restarts must be >= 0 and window_seconds must be > 0"
        )

    containers = _inspect_containers()
    state = _read_json(STATE_FILE, {})

    if not isinstance(state, dict):
        state = {}

    now = time.time()
    results = []

    for container in containers:
        container_id = container["id"]
        container_name = container["name"]

        if not container["running"]:
            status = "stopped"
            reason = f'Container state is {container["state"]}.'

        elif container["health"] == "unhealthy":
            status = "unhealthy"
            reason = (
                container["health_output"]
                or "Docker health check reports unhealthy."
            )

        elif container["health"] == "starting":
            status = "starting"
            reason = "Docker health check is still starting."

        elif container["health"] == "healthy":
            status = "healthy"
            reason = "Docker health check reports healthy."

        else:
            status = "running_no_healthcheck"
            reason = "No Docker HEALTHCHECK is configured."

        entry = {
            **container,
            "status": status,
            "reason": reason,
            "recovery": "not_attempted",
        }

        # Optional recovery for running unhealthy containers only.
        if status == "unhealthy" and auto_recover:
            restart_key = container_id
            history = state.get(restart_key, [])

            if not isinstance(history, list):
                history = []

            history = [
                stamp
                for stamp in history
                if isinstance(stamp, (int, float))
                and now - stamp < window_seconds
            ]

            if len(history) >= max_restarts:
                entry["recovery"] = "rate_limited"
                entry["recovery_reason"] = (
                    f"Limit reached: {max_restarts} restarts "
                    f"per {window_seconds} seconds."
                )

            else:
                try:
                    result = _docker("restart", container_id)

                    if result.returncode == 0:
                        history.append(now)
                        entry["recovery"] = "restart_requested"
                        entry["recovery_reason"] = (
                            "Restart requested; health will be checked "
                            "on the next poll."
                        )
                    else:
                        entry["recovery"] = "restart_failed"
                        entry["recovery_reason"] = (
                            result.stderr.strip()
                            or "Docker restart failed."
                        )

                except (OSError, subprocess.TimeoutExpired) as exc:
                    entry["recovery"] = "restart_failed"
                    entry["recovery_reason"] = str(exc)

            state[restart_key] = history

            _append_event({
                "timestamp": _now(),
                "type": "recovery_attempt",
                "container_id": container_id,
                "container_name": container_name,
                "recovery": entry["recovery"],
                "reason": entry.get("recovery_reason", reason),
            })

        # Deduplicate alerts by container and problem status.
        alert_key = f"alert:{container_id}"
        previous_alert = state.get(alert_key)

        if status in {"unhealthy", "stopped"}:
            if (
                not isinstance(previous_alert, dict)
                or previous_alert.get("status") != status
            ):
                _append_event({
                    "timestamp": _now(),
                    "type": "health_alert",
                    "container_id": container_id,
                    "container_name": container_name,
                    "status": status,
                    "reason": reason,
                })

            state[alert_key] = {
                "status": status,
                "last_seen": _now(),
            }

        else:
            # A previous alert has cleared.
            if isinstance(previous_alert, dict):
                _append_event({
                    "timestamp": _now(),
                    "type": "health_recovered",
                    "container_id": container_id,
                    "container_name": container_name,
                    "previous_status": previous_alert.get("status"),
                    "status": status,
                    "confirmed_healthy": status == "healthy",
                })

            state.pop(alert_key, None)

        results.append(entry)

    # Clear alert state for containers that have been deleted.
    current_alert_keys = {
        f"alert:{container['id']}"
        for container in containers
    }

    for key in list(state):
        if key.startswith("alert:") and key not in current_alert_keys:
            previous_alert = state.pop(key)

            _append_event({
                "timestamp": _now(),
                "type": "health_alert_cleared",
                "container_id": key.removeprefix("alert:"),
                "previous_status": (
                    previous_alert.get("status")
                    if isinstance(previous_alert, dict)
                    else "unknown"
                ),
                "reason": "Container no longer exists in Docker.",
            })

    _write_json(STATE_FILE, state)

    return {
        "checked_at": _now(),
        "auto_recovery_enabled": auto_recover,
        "container_count": len(results),
        "problem_count": sum(
            item["status"] in {"unhealthy", "stopped"}
            for item in results
        ),
        "containers": results,
        "events_file": str(EVENT_FILE),
    }


def get_recent_health_events(
    limit: int = 100,
) -> list[dict[str, Any]]:
    if limit < 1:
        raise ValueError("limit must be >= 1")

    try:
        lines = EVENT_FILE.read_text(
            encoding="utf-8"
        ).splitlines()
    except OSError:
        return []

    events = []

    for line in lines[-limit:]:
        try:
            events.append(json.loads(line))
        except json.JSONDecodeError:
            continue

    return list(reversed(events))


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="DockPilot container health monitor"
    )
    parser.add_argument(
        "--recover",
        action="store_true",
        help=(
            "Restart unhealthy running containers "
            "with rate limiting"
        ),
    )
    args = parser.parse_args()

    try:
        report = check_containers(auto_recover=args.recover)
        print(json.dumps(report, indent=2))

    except (
        RuntimeError,
        OSError,
        subprocess.TimeoutExpired,
        json.JSONDecodeError,
    ) as exc:
        raise SystemExit(f"Health monitor failed: {exc}")
