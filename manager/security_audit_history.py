"""Persistent, read-only history for DockPilot container security audits."""
from __future__ import annotations
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"
DB_PATH = DATA_DIR / "security_audit_history.db"

def _connect() -> sqlite3.Connection:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(DB_PATH, timeout=10)
    connection.row_factory = sqlite3.Row
    return connection

def initialize_security_audit_history() -> None:
    with _connect() as connection:
        connection.execute("""
            CREATE TABLE IF NOT EXISTS security_audits (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                audited_at TEXT NOT NULL,
                containers_scanned INTEGER NOT NULL,
                containers_with_findings INTEGER NOT NULL,
                total_findings INTEGER NOT NULL,
                critical INTEGER NOT NULL,
                high INTEGER NOT NULL,
                medium INTEGER NOT NULL,
                low INTEGER NOT NULL,
                report_json TEXT NOT NULL
            )
        """)

def save_security_audit(report: dict[str, Any]) -> dict[str, Any]:
    """Persist an audit result; this function never interacts with Docker."""
    summary = report.get("findings_by_severity") or report.get("risk_summary") or {}
    audited_at = datetime.now(timezone.utc).isoformat()
    with _connect() as connection:
        cursor = connection.execute("""
            INSERT INTO security_audits (
                audited_at, containers_scanned, containers_with_findings,
                total_findings, critical, high, medium, low, report_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            audited_at,
            int(report.get("containers_scanned", 0)),
            int(report.get("containers_with_findings", 0)),
            int(report.get("total_findings", 0)),
            int(summary.get("critical", 0)),
            int(summary.get("high", 0)),
            int(summary.get("medium", 0)),
            int(summary.get("low", 0)),
            json.dumps(report, separators=(",", ":"), ensure_ascii=False),
        ))
        audit_id = int(cursor.lastrowid)
    return {"id": audit_id, "audited_at": audited_at}

def list_security_audits(limit: int = 50) -> list[dict[str, Any]]:
    limit = max(1, min(int(limit), 500))
    with _connect() as connection:
        rows = connection.execute("""
            SELECT id, audited_at, containers_scanned, containers_with_findings,
                   total_findings, critical, high, medium, low
            FROM security_audits ORDER BY id DESC LIMIT ?
        """, (limit,)).fetchall()
    return [dict(row) for row in rows]

def get_security_audit(audit_id: int) -> dict[str, Any] | None:
    with _connect() as connection:
        row = connection.execute(
            "SELECT id, audited_at, report_json FROM security_audits WHERE id = ?",
            (audit_id,),
        ).fetchone()
    if row is None:
        return None
    return {"id": row["id"], "audited_at": row["audited_at"],
            "report": json.loads(row["report_json"])}
