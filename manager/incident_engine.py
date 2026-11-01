
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from docker_service import get_docker_client


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


def initialize_incidents():
    with _connect() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS incidents (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                fingerprint TEXT NOT NULL,
                container_id TEXT NOT NULL,
                container_name TEXT NOT NULL,
                incident_type TEXT NOT NULL,
                severity TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'open',
                summary TEXT NOT NULL,
                evidence_json TEXT NOT NULL DEFAULT '{}',
                first_seen TEXT NOT NULL,
                last_seen TEXT NOT NULL,
                resolved_at TEXT
            )
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_incidents_status
            ON incidents(status, last_seen)
        """)
        conn.commit()


def _save_incident(container, incident_type, severity, summary, evidence):
    fingerprint = f"{container.id}:{incident_type}"
    now = _now()

    with _connect() as conn:
        existing = conn.execute("""
            SELECT id FROM incidents
            WHERE fingerprint = ? AND status = 'open'
            ORDER BY id DESC LIMIT 1
        """, (fingerprint,)).fetchone()

        if existing:
            incident_id = existing["id"]
            conn.execute("""
                UPDATE incidents
                SET severity = ?, summary = ?,
                    evidence_json = ?, last_seen = ?
                WHERE id = ?
            """, (
                severity, summary, json.dumps(evidence),
                now, incident_id
            ))
        else:
            cursor = conn.execute("""
                INSERT INTO incidents (
                    fingerprint, container_id, container_name,
                    incident_type, severity, status, summary,
                    evidence_json, first_seen, last_seen
                )
                VALUES (?, ?, ?, ?, ?, 'open', ?, ?, ?, ?)
            """, (
                fingerprint,
                container.id,
                container.name,
                incident_type,
                severity,
                summary,
                json.dumps(evidence),
                now,
                now
            ))
            incident_id = cursor.lastrowid

        conn.commit()

    return incident_id


def get_incidents(limit=100):
    with _connect() as conn:
        rows = conn.execute("""
            SELECT * FROM incidents
            ORDER BY
                CASE severity
                    WHEN 'critical' THEN 1
                    WHEN 'high' THEN 2
                    WHEN 'medium' THEN 3
                    ELSE 4
                END,
                last_seen DESC
            LIMIT ?
        """, (limit,)).fetchall()

    items = []
    for row in rows:
        item = dict(row)
        item["evidence"] = json.loads(item.pop("evidence_json") or "{}")
        items.append(item)

    return items

def _analyze_root_cause(container, attrs, state):
    health_data = state.get("Health", {}) or {}
    health_logs = health_data.get("Log", []) or []

    latest_check = health_logs[-1] if health_logs else {}

    health_output = latest_check.get("Output", "").strip()
    health_exit_code = latest_check.get("ExitCode")

    health_command = (
        attrs.get("Config", {})
        .get("Healthcheck", {})
        .get("Test", [])
    )

    try:
        recent_logs = container.logs(
            tail=20,
            timestamps=True
        ).decode("utf-8", errors="replace")
    except Exception as exc:
        recent_logs = f"Unable to retrieve logs: {exc}"

    if health_data.get("Status") == "unhealthy":
        if health_output:
            root_cause = (
                f"Health check failed. Output: {health_output}"
            )
        else:
            root_cause = (
                "Health check failed repeatedly. "
                "No output was returned."
            )

    elif state.get("Status") == "restarting":
        root_cause = (
            "Container is repeatedly restarting. "
            "Inspect logs and exit information."
        )

    elif state.get("Status") == "dead":
        root_cause = (
            "Container is in a dead state. "
            "Inspect Docker state errors and logs."
        )

    else:
        root_cause = "No specific root cause identified."

    return {
        "root_cause": root_cause,
        "health_check_command": health_command,
        "health_check_exit_code": health_exit_code,
        "health_check_output": health_output,
        "recent_logs": recent_logs
    }

def scan_for_incidents():
    client = None
    detected = []

    try:
        client = get_docker_client()

        for container in client.containers.list(all=True):
            try:
                container.reload()
                attrs = container.attrs or {}
                state = attrs.get("State", {})

                status = state.get("Status", container.status)
                restart_count = attrs.get("RestartCount", 0)
                health = state.get("Health", {}).get("Status")

                evidence = {
                    "container_status": status,
                    "restart_count": restart_count,
                    "health_status": health,
                    "image": attrs.get("Config", {}).get("Image"),
                    "state_error": state.get("Error", "")
                }
                evidence.update(
                    _analyze_root_cause(container, attrs, state)
                )

                issues = []

                if status == "dead":
                    issues.append((
                        "container_state_failure",
                        "critical",
                        "Container is in a dead state."
                    ))
                elif status == "restarting":
                    issues.append((
                        "container_state_failure",
                        "high",
                        "Container is repeatedly restarting."
                    ))

                if health == "unhealthy":
                    issues.append((
                        "container_unhealthy",
                        "high",
                        "Container health check reports unhealthy."
                    ))

                if restart_count >= 5:
                    issues.append((
                        "repeated_restarts",
                        "high",
                        f"Container has restarted {restart_count} times."
                    ))
                elif restart_count >= 3:
                    issues.append((
                        "repeated_restarts",
                        "medium",
                        f"Container has restarted {restart_count} times."
                    ))

                for incident_type, severity, summary in issues:
                    incident_id = _save_incident(
                        container,
                        incident_type,
                        severity,
                        summary,
                        evidence
                    )

                    detected.append({
                        "id": incident_id,
                        "container_name": container.name,
                        "incident_type": incident_type,
                        "severity": severity,
                        "summary": summary,
                        "evidence": evidence
                    })

            except Exception as exc:
                print(
                    f"Incident scan failed for "
                    f"{container.name}: {exc}"
                )

    finally:
        if client is not None:
            client.close()

    return detected
