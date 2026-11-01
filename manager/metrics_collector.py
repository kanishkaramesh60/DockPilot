
"""
DockPilot - Automatic Docker Metrics Collector

Collects CPU and memory metrics periodically
without depending on dashboard requests.
"""

import logging
import threading
import time

from docker.errors import DockerException

from docker_service import get_docker_client
from metrics_history import record_metrics

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

COLLECTION_INTERVAL = 10

_stop_event = threading.Event()
_collector_thread = None
_collector_lock = threading.Lock()


def collect_container_metrics(project_name="dockpilot"):
    """Collect and store metrics for running containers."""

    client = None
    collected = 0

    try:
        client = get_docker_client()

        for container in client.containers.list(all=False):
            try:
                stats = container.stats(stream=False)

                cpu_stats = stats.get("cpu_stats", {})
                precpu_stats = stats.get("precpu_stats", {})

                cpu_usage = cpu_stats.get("cpu_usage", {})
                precpu_usage = precpu_stats.get("cpu_usage", {})

                cpu_delta = (
                    cpu_usage.get("total_usage", 0)
                    - precpu_usage.get("total_usage", 0)
                )

                system_delta = (
                    cpu_stats.get("system_cpu_usage", 0)
                    - precpu_stats.get("system_cpu_usage", 0)
                )

                online_cpus = (
                    cpu_stats.get("online_cpus")
                    or len(cpu_usage.get("percpu_usage", []) or [])
                    or 1
                )

                cpu_percent = (
                    (cpu_delta / system_delta) * online_cpus * 100
                    if system_delta > 0 and cpu_delta >= 0
                    else None
                )

                memory_stats = stats.get("memory_stats", {})
                memory_usage = memory_stats.get("usage", 0)
                memory_limit = memory_stats.get("limit", 0)

                memory_percent = (
                    memory_usage / memory_limit * 100
                    if memory_limit > 0
                    else None
                )

                record_metrics(
                    project_name=project_name,
                    service_name=container.name,
                    cpu_percent=(
                        round(cpu_percent, 2)
                        if cpu_percent is not None else None
                    ),
                    memory_percent=(
                        round(memory_percent, 2)
                        if memory_limit > 0 else None
                    ),
                    running_replicas=1,
                )

                collected += 1

            except Exception:
                logger.exception(
                    "Could not collect metrics for container %s",
                    container.name,
                )

    except DockerException:
        logger.exception("Docker metrics collection failed")

    finally:
        if client is not None:
            try:
                client.close()
            except Exception:
                logger.exception("Could not close Docker client")

    return collected


def _collector_loop():
    """Run periodic metric collection."""

    logger.info("DockPilot metrics collector started")

    while not _stop_event.is_set():
        try:
            count = collect_container_metrics()
            logger.info("Collected metrics for %s containers", count)

        except Exception:
            logger.exception("Unexpected metrics collector error")

        _stop_event.wait(COLLECTION_INTERVAL)

    logger.info("DockPilot metrics collector stopped")


def start_metrics_collector():
    """Start one background collector thread."""

    global _collector_thread

    with _collector_lock:
        if (
            _collector_thread is not None
            and _collector_thread.is_alive()
        ):
            return

        _stop_event.clear()

        _collector_thread = threading.Thread(
            target=_collector_loop,
            name="dockpilot-metrics-collector",
            daemon=True,
        )

        _collector_thread.start()


def stop_metrics_collector():
    """Stop the background collector safely."""

    global _collector_thread

    with _collector_lock:
        thread = _collector_thread

        if thread is None:
            return

        _stop_event.set()

    if thread.is_alive():
        thread.join(timeout=15)

    with _collector_lock:
        if _collector_thread is thread and not thread.is_alive():
            _collector_thread = None
