
import sqlite3
from pathlib import Path
from datetime import datetime, timezone

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"
DB_PATH = DATA_DIR / "dockpilot_history.db"


def _connect():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(DB_PATH, timeout=10)
    connection.row_factory = sqlite3.Row
    return connection


def initialize_history():
    with _connect() as connection:
        connection.execute("""
            CREATE TABLE IF NOT EXISTS metric_snapshots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                project_name TEXT NOT NULL,
                service_name TEXT NOT NULL,
                cpu_percent REAL,
                memory_percent REAL,
                running_replicas INTEGER
            )
        """)
        connection.execute("""
            CREATE TABLE IF NOT EXISTS scaling_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                project_name TEXT NOT NULL,
                service_name TEXT NOT NULL,
                action TEXT NOT NULL,
                previous_replicas INTEGER,
                target_replicas INTEGER,
                reason TEXT NOT NULL,
                success INTEGER NOT NULL,
                error TEXT
            )
        """)


def record_metrics(
    project_name,
    service_name,
    cpu_percent=None,
    memory_percent=None,
    running_replicas=0,
):
    timestamp = datetime.now(timezone.utc).isoformat()

    with _connect() as connection:
        connection.execute("""
            INSERT INTO metric_snapshots (
                timestamp, project_name, service_name,
                cpu_percent, memory_percent, running_replicas
            ) VALUES (?, ?, ?, ?, ?, ?)
        """, (
            timestamp,
            project_name,
            service_name,
            cpu_percent,
            memory_percent,
            running_replicas,
        ))


def record_scaling_event(
    project_name,
    service_name,
    action,
    previous_replicas,
    target_replicas,
    reason,
    success,
    error=None,
):
    timestamp = datetime.now(timezone.utc).isoformat()

    with _connect() as connection:
        connection.execute("""
            INSERT INTO scaling_events (
                timestamp, project_name, service_name, action,
                previous_replicas, target_replicas, reason,
                success, error
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            timestamp,
            project_name,
            service_name,
            action,
            previous_replicas,
            target_replicas,
            reason,
            int(success),
            error,
        ))


def get_metric_history(project_name, service_name, limit=100):
    limit = max(1, min(int(limit), 1000))

    with _connect() as connection:
        rows = connection.execute("""
            SELECT * FROM metric_snapshots
            WHERE project_name = ? AND service_name = ?
            ORDER BY id DESC LIMIT ?
        """, (project_name, service_name, limit)).fetchall()

    return [dict(row) for row in reversed(rows)]


def get_scaling_history(project_name=None, limit=100):
    limit = max(1, min(int(limit), 1000))

    with _connect() as connection:
        if project_name:
            rows = connection.execute("""
                SELECT * FROM scaling_events
                WHERE project_name = ?
                ORDER BY id DESC LIMIT ?
            """, (project_name, limit)).fetchall()
        else:
            rows = connection.execute("""
                SELECT * FROM scaling_events
                ORDER BY id DESC LIMIT ?
            """, (limit,)).fetchall()

    return [dict(row) for row in rows]
