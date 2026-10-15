import docker
from docker.errors import DockerException, NotFound, APIError


def get_docker_client():
    client = docker.from_env()
    client.ping()
    return client


def list_containers():
    client = get_docker_client()
    try:
        containers = client.containers.list(all=True)
        return [{
            "id": container.short_id,
            "name": container.name,
            "image": ", ".join(container.image.tags) or container.image.short_id,
            "status": container.status,
            "created": container.attrs.get("Created"),
        } for container in containers]
    finally:
        client.close()


def get_container_details(container_id):
    client = get_docker_client()
    try:
        container = client.containers.get(container_id)
        container.reload()
        return {
            "id": container.id,
            "name": container.name,
            "image": ", ".join(container.image.tags) or container.image.short_id,
            "status": container.status,
            "created": container.attrs.get("Created"),
            "ports": container.attrs.get("NetworkSettings", {}).get("Ports", {}),
        }
    finally:
        client.close()


def perform_action(container_id, action):
    if action not in {"start", "stop", "restart"}:
        raise ValueError("Unsupported container action")
    client = get_docker_client()
    try:
        container = client.containers.get(container_id)
        if action == "start":
            container.start()
        elif action == "stop":
            container.stop(timeout=10)
        else:
            container.restart(timeout=10)
        container.reload()
        return {
            "id": container.id,
            "name": container.name,
            "status": container.status,
            "action": action,
        }
    finally:
        client.close()


def get_container_logs(container_id, tail=100):
    client = get_docker_client()
    try:
        container = client.containers.get(container_id)
        logs = container.logs(
            stdout=True, stderr=True, tail=tail, timestamps=True
        )
        return logs.decode("utf-8", errors="replace")
    finally:
        client.close()


def get_container_stats(container_id):
    client = get_docker_client()
    try:
        container = client.containers.get(container_id)
        container.reload()
        if container.status != "running":
            raise ValueError(
                f"Container '{container.name}' is not running. "
                "Start it to collect live statistics."
            )

        stats = container.stats(stream=False)
        cpu_stats = stats.get("cpu_stats", {})
        previous_cpu = stats.get("precpu_stats", {})
        cpu_delta = (
            cpu_stats.get("cpu_usage", {}).get("total_usage", 0)
            - previous_cpu.get("cpu_usage", {}).get("total_usage", 0)
        )
        system_delta = (
            cpu_stats.get("system_cpu_usage", 0)
            - previous_cpu.get("system_cpu_usage", 0)
        )
        online_cpus = cpu_stats.get(
            "online_cpus",
            len(cpu_stats.get("cpu_usage", {}).get("percpu_usage", [])) or 1,
        )
        cpu_percent = 0.0
        if cpu_delta > 0 and system_delta > 0:
            cpu_percent = (cpu_delta / system_delta) * online_cpus * 100

        memory = stats.get("memory_stats", {})
        memory_usage = memory.get("usage", 0)
        memory_limit = memory.get("limit", 0)
        networks = stats.get("networks", {}).values()
        network_rx = sum(n.get("rx_bytes", 0) for n in networks)
        network_tx = sum(n.get("tx_bytes", 0) for n in networks)

        return {
            "id": container.short_id,
            "name": container.name,
            "status": container.status,
            "cpu_percent": round(cpu_percent, 2),
            "memory_usage_bytes": memory_usage,
            "memory_limit_bytes": memory_limit,
            "memory_percent": round(memory_usage / memory_limit * 100, 2)
            if memory_limit else None,
            "network_rx_bytes": network_rx,
            "network_tx_bytes": network_tx,
        }
    finally:
        client.close()
