
"""DockPilot automatic scaling controller."""
import subprocess
import threading
import time
from pathlib import Path

import yaml

from autoscaler import ScalingConfig, ScalingDecisionEngine
from autoscaling_service import get_service_metrics


PROJECT_ROOT = Path(__file__).resolve().parent.parent
COMPOSE_ROOT = PROJECT_ROOT / "compose_projects"


class AutoscalingController:
    def __init__(self):
        self.lock = threading.RLock()
        self.worker = None
        self.stop_event = threading.Event()
        self.engine = None
        self.project_name = None
        self.service_name = None
        self.enabled = False
        self.status = "Disabled"
        self.last_metrics = None
        self.last_error = None
        self.events = []
        self.config = ScalingConfig()

    def _record(self, message):
        with self.lock:
            self.events.insert(0, {
                "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
                "message": message,
            })
            self.events = self.events[:50]

    def _load_safe_service(self, project_name, service_name):
        path = COMPOSE_ROOT / project_name / "compose.yaml"

        if not path.is_file():
            raise ValueError("Saved Compose project was not found.")

        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        services = data.get("services", {})

        if service_name not in services:
            raise ValueError("Service does not exist in the Compose file.")

        service = services[service_name]

        # Fixed host ports and fixed container names prevent safe scaling.
        if service.get("container_name"):
            raise ValueError(
                "Scaling is blocked: remove container_name from this service."
            )

        if service.get("ports"):
            raise ValueError(
                "Scaling is blocked: this service declares ports. "
                "Use a reverse proxy/load balancer and internal service networking."
            )

        return path

    def enable(self, project_name, service_name):
        # Only accept the same safe naming convention as DockPilot's API.
        import re

        pattern = r"[a-z0-9][a-z0-9_-]{0,62}"
        if not re.fullmatch(pattern, project_name):
            raise ValueError("Invalid Compose project name.")
        if not re.fullmatch(pattern, service_name):
            raise ValueError("Invalid Compose service name.")

        self._load_safe_service(project_name, service_name)

        with self.lock:
            if self.worker and self.worker.is_alive():
                raise ValueError("Stop the current autoscaling session first.")

            self.stop_event = threading.Event()
            self.engine = ScalingDecisionEngine(self.config)
            self.project_name = project_name
            self.service_name = service_name
            self.enabled = True
            self.status = "Monitoring"
            self.last_error = None

            self.worker = threading.Thread(
                target=self._run,
                name="dockpilot-autoscaler",
                daemon=True,
            )
            self.worker.start()

        self._record(
            f"Automatic scaling enabled for {project_name}/{service_name}."
        )
        return self.get_status()

    def disable(self):
        with self.lock:
            self.enabled = False
            self.status = "Stopping"
            self.stop_event.set()
            worker = self.worker

        if worker and worker.is_alive():
            worker.join(timeout=3)

        with self.lock:
            self.status = "Disabled"

        self._record("Automatic scaling disabled. Existing replicas were unchanged.")
        return self.get_status()

    def _run(self):
        while not self.stop_event.is_set():
            try:
                project = self.project_name
                service = self.service_name

                metrics = get_service_metrics(project, service)
                cpu = metrics.get("average_cpu_percent")
                replicas = metrics.get("running_replicas", 0)

                with self.lock:
                    self.last_metrics = metrics
                    self.last_error = None

                # Do not make a decision without a valid CPU measurement.
                if cpu is not None and replicas > 0:
                    decision = self.engine.evaluate(
                        cpu_percent=float(cpu),
                        replicas=int(replicas),
                    )

                    action = decision.get("action")

                    if action in ("scale_up", "scale_down"):
                        target = int(decision["replicas"])

                        # Re-check the Compose configuration immediately
                        # before changing replica count.
                        compose_file = self._load_safe_service(project, service)

                        result = subprocess.run(
                            [
                                "docker", "compose",
                                "-p", project,
                                "-f", str(compose_file),
                                "up", "-d",
                                "--scale", f"{service}={target}",
                            ],
                            capture_output=True,
                            text=True,
                            timeout=180,
                            check=False,
                        )

                        if result.returncode != 0:
                            raise RuntimeError(
                                result.stderr.strip()
                                or "Docker Compose scaling failed."
                            )

                        self.engine.record_action()
                        self._record(
                            f"{action}: {project}/{service}, "
                            f"{replicas} -> {target} replicas; CPU={cpu}%."
                        )

            except Exception as exc:
                with self.lock:
                    self.last_error = str(exc)
                self._record(f"Autoscaling error: {exc}")

            self.stop_event.wait(self.config.sample_seconds)

    def get_status(self):
        with self.lock:
            return {
                "enabled": self.enabled,
                "status": self.status,
                "project_name": self.project_name,
                "service_name": self.service_name,
                "policy": {
                    "scale_up_cpu_percent": self.config.scale_up_cpu,
                    "scale_up_seconds": self.config.scale_up_seconds,
                    "scale_down_cpu_percent": self.config.scale_down_cpu,
                    "scale_down_seconds": self.config.scale_down_seconds,
                    "sample_seconds": self.config.sample_seconds,
                    "cooldown_seconds": self.config.cooldown_seconds,
                    "min_replicas": self.config.min_replicas,
                    "max_replicas": self.config.max_replicas,
                },
                "metrics": self.last_metrics,
                "last_error": self.last_error,
                "events": list(self.events),
            }


autoscaling_controller = AutoscalingController()
