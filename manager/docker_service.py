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


def get_system_overview():
    """Return live Docker Engine and resource inventory information."""
    client = get_docker_client()
    try:
        info = client.info()
        version = client.version()
        containers = client.containers.list(all=True)
        images = client.images.list()
        networks = client.networks.list()
        volumes = client.volumes.list()

        running = sum(1 for item in containers if item.status == "running")
        return {
            "engine_version": version.get("Version", "Unknown"),
            "api_version": version.get("ApiVersion", "Unknown"),
            "operating_system": info.get("OperatingSystem", "Unknown"),
            "architecture": info.get("Architecture", "Unknown"),
            "total_containers": len(containers),
            "running_containers": running,
            "stopped_containers": len(containers) - running,
            "images": len(images),
            "networks": len(networks),
            "volumes": len(volumes),
        }
    finally:
        client.close()


def list_images():
    """Return actual local Docker images and their metadata."""
    client = get_docker_client()
    try:
        images = client.images.list()
        results = []
        for image in images:
            attrs = image.attrs or {}
            results.append({
                "id": image.short_id.replace("sha256:", ""),
                "full_id": image.id,
                "tags": image.tags or ["<none>:<none>"],
                "size_bytes": attrs.get("Size", 0),
                "created": attrs.get("Created"),
            })
        return sorted(results, key=lambda item: (item["tags"][0].lower(), item["id"]))
    finally:
        client.close()


def pull_image(image_name):
    """Pull an image from a registry after validating the requested name."""
    name = (image_name or "").strip()
    if not name:
        raise ValueError("Enter an image name, for example nginx:alpine")
    if len(name) > 255 or any(ch.isspace() for ch in name):
        raise ValueError("Image name must be under 256 characters and contain no spaces")
    client = get_docker_client()
    try:
        image = client.images.pull(name)
        attrs = image.attrs or {}
        return {
            "id": image.short_id.replace("sha256:", ""),
            "full_id": image.id,
            "tags": image.tags or [name],
            "size_bytes": attrs.get("Size", 0),
            "created": attrs.get("Created"),
            "message": f"Image {name} downloaded successfully",
        }
    finally:
        client.close()


def create_container(image_name, name=None, host_port=None, container_port=80,
                     environment=None, restart_policy="no"):
    """Create and start a real Docker container from a local image."""
    image_name = (image_name or "").strip()
    if not image_name:
        raise ValueError("Choose a Docker image.")
    if any(ch.isspace() for ch in image_name):
        raise ValueError("Image name must not contain spaces.")
    if restart_policy not in {"no", "on-failure", "always", "unless-stopped"}:
        raise ValueError("Unsupported restart policy.")

    container_name = (name or "").strip() or None
    if container_name and (len(container_name) > 128 or
                           any(ch.isspace() for ch in container_name)):
        raise ValueError("Container name must be 1-128 characters with no spaces.")

    env_values = []
    for item in (environment or []):
        item = str(item).strip()
        if not item:
            continue
        if "=" not in item:
            raise ValueError("Each environment variable must use KEY=VALUE format.")
        key, value = item.split("=", 1)
        if not key or not key.replace("_", "").isalnum() or key[0].isdigit():
            raise ValueError(f"Invalid environment variable name: {key}")
        env_values.append(f"{key}={value}")

    ports = None
    if host_port is not None:
        if container_port is None:
            raise ValueError("Container port is required when mapping a host port.")
        ports = {f"{int(container_port)}/tcp": int(host_port)}

    client = get_docker_client()
    try:
        try:
            image = client.images.get(image_name)
        except NotFound:
            raise ValueError(
                f"Image '{image_name}' is not available locally. Pull it in Docker Images first."
            )

        container = client.containers.run(
            image=image,
            name=container_name,
            detach=True,
            ports=ports,
            environment=env_values or None,
            restart_policy={"Name": restart_policy},
        )
        container.reload()
        return {
            "id": container.short_id,
            "full_id": container.id,
            "name": container.name,
            "image": image_name,
            "status": container.status,
            "message": f"Container '{container.name}' created and started.",
        }
    finally:
        client.close()


def list_networks():
    """Return real Docker networks without modifying them."""
    client = get_docker_client()
    try:
        results = []
        for network in client.networks.list():
            network.reload()
            attrs = network.attrs or {}
            containers = attrs.get("Containers") or {}
            results.append({
                "id": network.short_id,
                "name": network.name,
                "driver": attrs.get("Driver", "unknown"),
                "scope": attrs.get("Scope", "unknown"),
                "created": attrs.get("Created"),
                "internal": bool(attrs.get("Internal", False)),
                "attachable": bool(attrs.get("Attachable", False)),
                "container_count": len(containers),
                "containers": [item.get("Name", item.get("IPv4Address", "unknown")) for item in containers.values()],
            })
        return sorted(results, key=lambda item: item["name"].lower())
    finally:
        client.close()


def list_volumes():
    """Return real Docker volumes and their mountpoints without changing them."""
    client = get_docker_client()
    try:
        results = []
        for volume in client.volumes.list():
            attrs = volume.attrs or {}
            results.append({
                "name": volume.name,
                "driver": attrs.get("Driver", "unknown"),
                "mountpoint": attrs.get("Mountpoint", ""),
                "scope": attrs.get("Scope", "unknown"),
                "created": attrs.get("CreatedAt"),
                "labels": attrs.get("Labels") or {},
            })
        return sorted(results, key=lambda item: item["name"].lower())
    finally:
        client.close()
