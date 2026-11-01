
"""Read real Docker stats for an explicitly selected Compose service."""

from docker_service import get_docker_client


def get_service_metrics(project_name, service_name):
    """Return live stats for running containers in one Compose service."""
    if not project_name or not service_name:
        raise ValueError("A Compose project and service name are required.")

    client = get_docker_client()
    try:
        matching = []

        for container in client.containers.list(
            filters={"label": [
                f"com.docker.compose.project={project_name}",
                f"com.docker.compose.service={service_name}",
            ]}
        ):
            container.reload()

            if container.status != "running":
                continue

            stats = container.stats(stream=False)
            cpu_stats = stats.get("cpu_stats", {})
            precpu_stats = stats.get("precpu_stats", {})

            cpu_delta = (
                cpu_stats.get("cpu_usage", {}).get("total_usage", 0)
                - precpu_stats.get("cpu_usage", {}).get("total_usage", 0)
            )
            system_delta = (
                cpu_stats.get("system_cpu_usage", 0)
                - precpu_stats.get("system_cpu_usage", 0)
            )
            online_cpus = cpu_stats.get(
                "online_cpus",
                len(cpu_stats.get("cpu_usage", {}).get("percpu_usage", [])) or 1,
            )

            cpu_percent = None
            if cpu_delta >= 0 and system_delta > 0:
                cpu_percent = round(
                    (cpu_delta / system_delta) * online_cpus * 100,
                    2,
                )

            memory = stats.get("memory_stats", {})
            usage = memory.get("usage", 0)
            limit = memory.get("limit", 0)

            matching.append({
                "container_id": container.short_id,
                "container_name": container.name,
                "status": container.status,
                "cpu_percent": cpu_percent,
                "memory_usage_bytes": usage,
                "memory_limit_bytes": limit,
                "memory_percent": round(usage / limit * 100, 2)
                if limit else None,
            })

        valid_cpu = [
            item["cpu_percent"]
            for item in matching
            if item["cpu_percent"] is not None
        ]

        return {
            "project_name": project_name,
            "service_name": service_name,
            "running_replicas": len(matching),
            "measurement": (
                "Docker CPU usage percentage; normalized using Docker's "
                "system CPU delta and online CPU count."
            ),
            "average_cpu_percent": round(sum(valid_cpu) / len(valid_cpu), 2)
            if valid_cpu else None,
            "containers": matching,
        }
    finally:
        client.close()
