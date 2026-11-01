import json
import sqlite3
import time
import uuid

from datetime import datetime, timezone
from pathlib import Path

from docker_service import (
    get_docker_client,
    perform_action,
)


DB_PATH = (
    Path(__file__).resolve().parent.parent
    / "data"
    / "dockpilot_history.db"
)


def _connect():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH), timeout=10)
    conn.row_factory = sqlite3.Row
    return conn


def _now():
    return datetime.now(timezone.utc).isoformat()


def initialize_recovery():
    with _connect() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS incident_recovery_actions (
                action_id TEXT PRIMARY KEY,
                incident_id INTEGER NOT NULL,
                container_id TEXT NOT NULL,
                action TEXT NOT NULL,
                recommendation TEXT NOT NULL,
                status TEXT NOT NULL,
                created_at TEXT NOT NULL,
                approved_at TEXT,
                completed_at TEXT,
                result_json TEXT NOT NULL DEFAULT '{}'
            )
        """)
        conn.commit()


def create_recommendation(incident_id):
    with _connect() as conn:
        incident = conn.execute("""
            SELECT * FROM incidents WHERE id = ?
        """, (incident_id,)).fetchone()

    if not incident:
        raise ValueError("Incident not found.")

    if incident["status"] != "open":
        raise ValueError("Recovery is available only for open incidents.")

    evidence = json.loads(incident["evidence_json"] or "{}")
    incident_type = incident["incident_type"]

    if incident_type == "container_unhealthy":
        action = "restart"
        recommendation = (
            "A controlled restart is available as a diagnostic recovery "
            "attempt. It may not fix the underlying health-check failure."
        )

        if evidence.get("health_check_exit_code") not in (None, 0):
            recommendation += (
                " The latest health check returned exit code "
                f"{evidence['health_check_exit_code']}. "
                "Review the health-check command and configuration."
            )

    elif (
        incident_type == "container_state_failure"
        and evidence.get("container_status") == "dead"
    ):
        action = "restart"
        recommendation = (
            "The container is in a dead state. A controlled restart "
            "is recommended, followed by health verification."
        )

    else:
        action = None
        recommendation = (
            "Automatic recovery is not recommended for this incident. "
            "Investigate the container logs and configuration first."
        )

    action_id = str(uuid.uuid4())
    status = "pending_approval" if action else "manual_review"

    with _connect() as conn:
        conn.execute("""
            INSERT INTO incident_recovery_actions (
                action_id, incident_id, container_id,
                action, recommendation, status, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            action_id,
            incident_id,
            incident["container_id"],
            action or "manual_review",
            recommendation,
            status,
            _now(),
        ))
        conn.commit()

    return {
        "action_id": action_id,
        "incident_id": incident_id,
        "container_name": incident["container_name"],
        "recommended_action": action or "manual_review",
        "recommendation": recommendation,
        "executable": action is not None,
        "approval_required": action is not None,
        "status": status,
    }


def execute_approved_recovery(action_id):
    with _connect() as conn:
        row = conn.execute("""
            SELECT * FROM incident_recovery_actions
            WHERE action_id = ?
        """, (action_id,)).fetchone()

        if not row:
            raise ValueError("Recovery recommendation not found.")

        if row["status"] != "pending_approval":
            raise ValueError(
                f"Recovery cannot be executed. Current status: {row['status']}"
            )

        if row["action"] != "restart":
            raise ValueError("Unsupported recovery action.")

        conn.execute("""
            UPDATE incident_recovery_actions
            SET status = 'executing', approved_at = ?
            WHERE action_id = ? AND status = 'pending_approval'
        """, (_now(), action_id))
        conn.commit()

        container_id = row["container_id"]
        action = row["action"]

    try:
        action_result = perform_action(container_id, action)

        verification = {
            "container_status": action_result["status"],
            "health_status": None,
        }


        # Allow Docker sufficient time to complete its health-check cycle.
        for attempt in range(20):
            client = get_docker_client()

            try:
                container = client.containers.get(container_id)
                container.reload()

                state = (container.attrs or {}).get("State", {})
                verification = {
                    "container_status": state.get("Status"),
                    "health_status": (
                        state.get("Health", {}) or {}
                    ).get("Status"),
                }
            finally:
                client.close()

            health = verification["health_status"]

            # Stop when a final health result is available.
            if (
                verification["container_status"] != "running"
                or health in ("healthy", "unhealthy")
                or health is None
            ):
                break

            time.sleep(3)


        if verification["container_status"] != "running":
            result_status = "failed"
            message = "Container did not return to running state."

        elif verification["health_status"] == "unhealthy":
            result_status = "completed_degraded"
            message = (
                "Container restarted, but its health check is still failing. "
                "Investigate the underlying configuration."
            )

        elif verification["health_status"] == "starting":
            result_status = "verification_pending"
            message = "Container restarted; health verification is pending."

        else:
            result_status = "verified"
            message = "Container restart completed and verification passed."

        result = {
            "action_result": action_result,
            "verification": verification,
            "message": message,
        }

    except Exception as exc:
        result_status = "failed"
        result = {
            "message": f"Recovery execution failed: {exc}"
        }

    with _connect() as conn:
        conn.execute("""
            UPDATE incident_recovery_actions
            SET status = ?, completed_at = ?, result_json = ?
            WHERE action_id = ?
        """, (
            result_status,
            _now(),
            json.dumps(result),
            action_id,
        ))
        conn.commit()

    return {
        "action_id": action_id,
        "status": result_status,
        **result,
    }


def get_recovery_history(limit=100):
    with _connect() as conn:
        rows = conn.execute("""
            SELECT * FROM incident_recovery_actions
            ORDER BY created_at DESC
            LIMIT ?
        """, (limit,)).fetchall()

    items = []

    for row in rows:
        item = dict(row)
        item["result"] = json.loads(
            item.pop("result_json") or "{}"
        )
        items.append(item)

    return items