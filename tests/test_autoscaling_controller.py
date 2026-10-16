
import subprocess
import threading
import time

import pytest

import manager.autoscaling_controller as controller_module
from manager.autoscaling_controller import AutoscalingController


@pytest.fixture
def controller(tmp_path, monkeypatch):
    compose_dir = tmp_path / "dockpilot-scaled-demo"
    compose_dir.mkdir()
    compose_file = compose_dir / "compose.yaml"
    compose_file.write_text(
        """
services:
  web:
    image: nginx:alpine
    expose:
      - "80"
  proxy:
    image: nginx:alpine
    ports:
      - "8091:80"
""",
        encoding="utf-8",
    )

    monkeypatch.setattr(controller_module, "COMPOSE_ROOT", tmp_path)

    instance = AutoscalingController()
    instance.config.scale_up_seconds = 1
    instance.config.scale_down_seconds = 1
    instance.config.sample_seconds = 1
    instance.config.cooldown_seconds = 10

    yield instance

    instance.disable()


def test_safe_service_allows_internal_port_but_rejects_host_ports(
    controller, tmp_path
):
    assert controller._load_safe_service(
        "dockpilot-scaled-demo", "web"
    ).is_file()

    with pytest.raises(ValueError, match="declares ports"):
        controller._load_safe_service("dockpilot-scaled-demo", "proxy")


def test_enable_rejects_invalid_project_name(controller):
    with pytest.raises(ValueError, match="Invalid Compose project name"):
        controller.enable("../outside", "web")


def test_controller_scales_up_after_engine_decision(
    controller, monkeypatch
):
    metrics = {
        "project_name": "dockpilot-scaled-demo",
        "service_name": "web",
        "running_replicas": 1,
        "average_cpu_percent": 85.0,
        "containers": [],
    }

    monkeypatch.setattr(
        controller_module, "get_service_metrics", lambda *args: metrics
    )

    calls = []

    def fake_compose(*args, **kwargs):
        calls.append(args[0])
        return subprocess.CompletedProcess(args[0], 0, "", "")

    monkeypatch.setattr(controller_module.subprocess, "run", fake_compose)

    class FakeEngine:
        def __init__(self):
            self.evaluations = 0
            self.actions_recorded = 0

        def evaluate(self, cpu_percent, replicas):
            self.evaluations += 1
            if self.evaluations == 1:
                return {"action": "none", "replicas": replicas}
            return {
                "action": "scale_up",
                "replicas": replicas + 1,
            }

        def record_action(self):
            self.actions_recorded += 1

    fake_engine = FakeEngine()
    controller.engine = fake_engine
    controller.project_name = "dockpilot-scaled-demo"
    controller.service_name = "web"
    controller.enabled = True
    controller.stop_event = threading.Event()

    run_thread = threading.Thread(target=controller._run, daemon=True)
    run_thread.start()

    deadline = time.monotonic() + 3
    while not calls and time.monotonic() < deadline:
        time.sleep(0.02)

    controller.stop_event.set()
    run_thread.join(timeout=2)

    assert calls, "Controller did not invoke Docker Compose."
    assert "--scale" in calls[0]
    assert "web=2" in calls[0]
    assert fake_engine.actions_recorded == 1
    assert controller.last_error is None
    assert any("scale_up" in event["message"] for event in controller.events)


def test_failed_compose_command_is_reported(controller, monkeypatch):
    monkeypatch.setattr(
        controller_module,
        "get_service_metrics",
        lambda *args: {
            "running_replicas": 1,
            "average_cpu_percent": 85.0,
        },
    )

    class FakeEngine:
        def evaluate(self, cpu_percent, replicas):
            return {"action": "scale_up", "replicas": replicas + 1}

        def record_action(self):
            pytest.fail("Cooldown must not be recorded after a failed scale")

    monkeypatch.setattr(
        controller_module.subprocess,
        "run",
        lambda *args, **kwargs: subprocess.CompletedProcess(
            args[0], 1, "", "simulated compose failure"
        ),
    )

    controller.engine = FakeEngine()
    controller.project_name = "dockpilot-scaled-demo"
    controller.service_name = "web"
    controller.stop_event = threading.Event()

    thread = threading.Thread(target=controller._run, daemon=True)
    thread.start()

    deadline = time.monotonic() + 2
    while controller.last_error is None and time.monotonic() < deadline:
        time.sleep(0.02)

    controller.stop_event.set()
    thread.join(timeout=2)

    assert controller.last_error == "simulated compose failure"
