
import json
import subprocess

import pytest

from manager import container_health as health


def fake_container(
    container_id="abc123456789",
    name="test-container",
    state="running",
    health_status="healthy",
):
    return {
        "id": container_id,
        "name": name,
        "running": state == "running",
        "state": state,
        "health": health_status,
        "healthcheck_configured": health_status != "not_configured",
        "health_output": (
            "Simulated unhealthy health check"
            if health_status == "unhealthy"
            else ""
        ),
        "status": (
            f"Up ({health_status})"
            if state == "running" and health_status
            else state
        ),
        "image": "nginx:alpine",
        "exit_code": 0,
    }


@pytest.fixture
def isolated_health_files(tmp_path, monkeypatch):
    events_file = tmp_path / "container_health_events.jsonl"
    state_file = tmp_path / "container_health_state.json"

    monkeypatch.setattr(health, "EVENT_FILE", events_file)
    monkeypatch.setattr(health, "STATE_FILE", state_file)

    return events_file, state_file


def mock_inspection(monkeypatch, containers):
    monkeypatch.setattr(
        health,
        "_inspect_containers",
        lambda: containers,
    )


def read_events(events_file):
    if not events_file.exists():
        return []

    return [
        json.loads(line)
        for line in events_file.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def test_repeated_unhealthy_check_does_not_duplicate_alert(
    isolated_health_files, monkeypatch
):
    events_file, _ = isolated_health_files

    mock_inspection(
        monkeypatch,
        [fake_container(health_status="unhealthy")],
    )

    health.check_containers()
    health.check_containers()

    alerts = [
        event
        for event in read_events(events_file)
        if event.get("type") == "health_alert"
    ]

    assert len(alerts) == 1


def test_recovery_event_when_container_becomes_healthy(
    isolated_health_files, monkeypatch
):
    events_file, _ = isolated_health_files

    mock_inspection(
        monkeypatch,
        [fake_container(health_status="unhealthy")],
    )
    health.check_containers()

    mock_inspection(
        monkeypatch,
        [fake_container(health_status="healthy")],
    )
    health.check_containers()

    recovery_events = [
        event
        for event in read_events(events_file)
        if event.get("type") == "health_recovered"
    ]

    assert len(recovery_events) == 1
    assert recovery_events[0]["confirmed_healthy"] is True


def test_deleted_container_clears_old_alert_state(
    isolated_health_files, monkeypatch
):
    events_file, state_file = isolated_health_files

    mock_inspection(
        monkeypatch,
        [fake_container(health_status="unhealthy")],
    )
    health.check_containers()

    state = json.loads(state_file.read_text(encoding="utf-8"))
    assert any(key.startswith("alert:") for key in state)

    mock_inspection(monkeypatch, [])
    health.check_containers()

    state = json.loads(state_file.read_text(encoding="utf-8"))
    assert not any(key.startswith("alert:") for key in state)

    events = read_events(events_file)

    assert any(
        event.get("type") == "health_alert_cleared"
        for event in events
    )


def test_restart_rate_limit_prevents_excessive_restarts(
    isolated_health_files, monkeypatch
):
    _, state_file = isolated_health_files

    container = fake_container(health_status="unhealthy")
    mock_inspection(monkeypatch, [container])

    restart_calls = []

    def fake_docker(*args, **kwargs):
        restart_calls.append(args)
        return subprocess.CompletedProcess(
            args=args,
            returncode=0,
            stdout="",
            stderr="",
        )

    monkeypatch.setattr(health, "_docker", fake_docker)

    # Seed the restart history at the configured limit.
    state_file.write_text(
        json.dumps(
            {
                container["id"]: [
                    health.time.time(),
                    health.time.time(),
                    health.time.time(),
                ]
            }
        ),
        encoding="utf-8",
    )

    report = health.check_containers(
        auto_recover=True,
        max_restarts=3,
        window_seconds=900,
    )

    assert not any(
        args and args[0] == "restart"
        for args in restart_calls
    )

    assert report["containers"][0]["recovery"] == "rate_limited"


def test_docker_command_failure_is_reported_safely(monkeypatch):
    def failed_inspection():
        raise RuntimeError("Docker unavailable")

    monkeypatch.setattr(
        health,
        "_inspect_containers",
        failed_inspection,
    )

    with pytest.raises(RuntimeError, match="Docker unavailable"):
        health.check_containers()
