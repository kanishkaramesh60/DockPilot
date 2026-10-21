
import docker
from docker.errors import DockerException, NotFound, APIError


def get_docker_client():
    client = docker.from_env()
    try:
        client.ping()
        return client
    except Exception:
        client.close()
        raise


def list_containers():
    client = get_docker_client()
    try:
        containers = client.containers.list(all=True)
        return [
            {
                "id": container.short_id,
                "name": container.name,
                "image": ", ".join(container.image.tags)
                or container.image.short_id,
                "status": container.status,
                "created": (container.attrs or {}).get("Created"),
            }
            for container in containers
        ]
    finally:
        client.close()


def get_container_details(container_id):
    client = get_docker_client()
    try:
        container = client.containers.get(container_id)
        container.reload()
        attrs = container.attrs or {}
        return {
            "id": container.id,
            "name": container.name,
            "image": ", ".join(container.image.tags)
            or container.image.short_id,
            "status": container.status,
            "created": attrs.get("Created"),
            "ports": attrs.get("NetworkSettings", {}).get("Ports", {}),
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
            stdout=True,
            stderr=True,
            tail=tail,
            timestamps=True,
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
            cpu_percent = (
                cpu_delta / system_delta
            ) * online_cpus * 100

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
            if memory_limit
            else None,
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
        results = []

        for image in client.images.list():
            attrs = image.attrs or {}
            results.append({
                "id": image.short_id.replace("sha256:", ""),
                "full_id": image.id,
                "tags": image.tags or ["<none>:<none>"],
                "size_bytes": attrs.get("Size", 0),
                "created": attrs.get("Created"),
            })

        return sorted(
            results,
            key=lambda item: (item["tags"][0].lower(), item["id"]),
        )
    finally:
        client.close()


def pull_image(image_name):
    """Pull an image from a registry after validating the requested name."""
    name = (image_name or "").strip()

    if not name:
        raise ValueError("Enter an image name, for example nginx:alpine")

    if len(name) > 255 or any(ch.isspace() for ch in name):
        raise ValueError(
            "Image name must be under 256 characters and contain no spaces"
        )

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


def create_container(
    image_name,
    name=None,
    host_port=None,
    container_port=80,
    environment=None,
    restart_policy="no",
):
    """Create and start a real Docker container from a local image."""
    image_name = (image_name or "").strip()

    if not image_name:
        raise ValueError("Choose a Docker image.")

    if any(ch.isspace() for ch in image_name):
        raise ValueError("Image name must not contain spaces.")

    if restart_policy not in {
        "no", "on-failure", "always", "unless-stopped"
    }:
        raise ValueError("Unsupported restart policy.")

    container_name = (name or "").strip() or None

    if container_name and (
        len(container_name) > 128
        or any(ch.isspace() for ch in container_name)
    ):
        raise ValueError(
            "Container name must be 1-128 characters with no spaces."
        )

    env_values = []

    for item in (environment or []):
        item = str(item).strip()
        if not item:
            continue

        if "=" not in item:
            raise ValueError(
                "Each environment variable must use KEY=VALUE format."
            )

        key, value = item.split("=", 1)

        if not key or not key.replace("_", "").isalnum() or key[0].isdigit():
            raise ValueError(f"Invalid environment variable name: {key}")

        env_values.append(f"{key}={value}")

    ports = None

    if host_port is not None:
        if container_port is None:
            raise ValueError(
                "Container port is required when mapping a host port."
            )

        ports = {f"{int(container_port)}/tcp": int(host_port)}

    client = get_docker_client()
    try:
        try:
            image = client.images.get(image_name)
        except NotFound:
            raise ValueError(
                f"Image '{image_name}' is not available locally. "
                "Pull it in Docker Images first."
            ) from None

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
                "containers": [
                    item.get("Name", item.get("IPv4Address", "unknown"))
                    for item in containers.values()
                ],
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


def audit_container_security():
    """Audit real Docker container configuration without changing containers."""
    client = get_docker_client()

    severity_rank = {
        "critical": 4,
        "high": 3,
        "medium": 2,
        "low": 1,
    }

    sensitive_paths = (
        "/",
        "/etc",
        "/proc",
        "/sys",
        "/root",
        "/var/run",
        "/var/lib/docker",
    )

    def is_sensitive_path(path):
        path = str(path or "").replace("\\", "/").lower()

        if not path:
            return False

        if path == "/":
            return True

        path = path.rstrip("/")

        return any(
            path == item or path.startswith(item + "/")
            for item in sensitive_paths
            if item != "/"
        )

    def image_name(container):
        tags = getattr(container.image, "tags", []) or []
        return ", ".join(tags) or getattr(
            container.image, "short_id", "unknown"
        )

    try:
        results = []

        for container in client.containers.list(all=True):
            container.reload()

            attrs = container.attrs or {}
            config = attrs.get("Config") or {}
            host_config = attrs.get("HostConfig") or {}
            findings = []
            seen_checks = set()

            def add_finding(check, severity, message, recommendation):
                # Avoid duplicate findings for the same check.
                if check in seen_checks:
                    return

                seen_checks.add(check)
                findings.append({
                    "check": check,
                    "severity": severity,
                    "message": message,
                    "recommendation": recommendation,
                })

            if host_config.get("Privileged") is True:
                add_finding(
                    "privileged_mode",
                    "critical",
                    "Container runs with privileged mode enabled.",
                    "Disable privileged mode and grant only required capabilities.",
                )

            if str(host_config.get("NetworkMode", "")).lower() == "host":
                add_finding(
                    "host_network",
                    "high",
                    "Container shares the host network namespace.",
                    "Use an isolated Docker network unless host networking is essential.",
                )

            for field, label in (("PidMode", "PID"), ("IpcMode", "IPC")):
                if str(host_config.get(field, "")).lower() == "host":
                    add_finding(
                        f"host_{label.lower()}_namespace",
                        "high",
                        f"Container shares the host {label} namespace.",
                        f"Avoid host {label} namespace sharing unless required.",
                    )

            capabilities = {
                str(cap).upper()
                for cap in (host_config.get("CapAdd") or [])
            }
            dangerous_caps = capabilities.intersection(
                {"ALL", "SYS_ADMIN", "SYS_PTRACE"}
            )

            if dangerous_caps:
                add_finding(
                    "dangerous_capabilities",
                    "high",
                    "Dangerous capabilities added: "
                    + ", ".join(sorted(dangerous_caps)),
                    "Remove unnecessary capabilities and follow least privilege.",
                )
            elif capabilities:
                add_finding(
                    "extra_capabilities",
                    "medium",
                    "Additional Linux capabilities are configured: "
                    + ", ".join(sorted(capabilities)),
                    "Review each added capability and remove any that are not required.",
                )

            security_opts = [
                str(option).lower()
                for option in (host_config.get("SecurityOpt") or [])
            ]
            unconfined = [
                option
                for option in security_opts
                if "seccomp=unconfined" in option
                or "apparmor=unconfined" in option
            ]

            if unconfined:
                add_finding(
                    "unconfined_security_profile",
                    "high",
                    "An unconfined seccomp or AppArmor profile is configured.",
                    "Use the default or an appropriately restricted security profile.",
                )

            mounts = attrs.get("Mounts") or []

            for mount in mounts:
                source = str(mount.get("Source") or "")
                destination = str(mount.get("Destination") or "")
                normalized_source = source.replace("\\", "/").lower()
                normalized_destination = destination.replace("\\", "/").lower()

                socket_paths = {
                    "/var/run/docker.sock",
                    "/run/docker.sock",
                }

                if (
                    normalized_source.rstrip("/") in socket_paths
                    or normalized_destination.rstrip("/") in socket_paths
                ):
                    add_finding(
                        "docker_socket_mount",
                        "critical",
                        "The Docker Engine socket appears to be mounted into the container.",
                        "Remove the socket mount unless strictly necessary; access may grant control over the Docker host.",
                    )
                elif (
                    mount.get("RW", True)
                    and (
                        is_sensitive_path(source)
                        or is_sensitive_path(destination)
                    )
                ):
                    add_finding(
                        "sensitive_writable_mount",
                        "high",
                        f"A writable mount uses a sensitive path: "
                        f"{source or '(unknown source)'} -> "
                        f"{destination or '(unknown destination)'}.",
                        "Remove the mount or make it read-only and narrowly scoped.",
                    )

            # Check bind configuration for Docker metadata that may not
            # appear in the Mounts collection.
            for bind in (host_config.get("Binds") or []):
                source = str(bind).split(":", 1)[0]
                normalized_source = source.replace("\\", "/").lower().rstrip("/")

                if normalized_source in {
                    "/var/run/docker.sock",
                    "/run/docker.sock",
                }:
                    add_finding(
                        "docker_socket_mount",
                        "critical",
                        "A Docker Engine socket bind mount is configured.",
                        "Remove the socket bind unless strictly necessary.",
                    )

            if host_config.get("ReadonlyRootfs") is not True:
                add_finding(
                    "writable_root_filesystem",
                    "medium",
                    "The container root filesystem is writable.",
                    "Enable a read-only root filesystem where the application supports it.",
                )

            user = str(config.get("User") or "").strip()

            if not user or user in {"0", "root", "0:0", "root:root"}:
                add_finding(
                    "root_or_unspecified_user",
                    "medium",
                    "The container user is root or is not explicitly configured.",
                    "Configure a non-root user in the image or container where supported.",
                )

            highest = max(
                (finding["severity"] for finding in findings),
                key=lambda severity: severity_rank[severity],
                default="low",
            )

            results.append({
                "id": container.id,
                "name": container.name,
                "image": image_name(container),
                "status": container.status,
                "risk_level": highest,
                "finding_count": len(findings),
                "findings": findings,
            })

        counts = {
            level: sum(
                1 for item in results if item["risk_level"] == level
            )
            for level in ("critical", "high", "medium", "low")
        }

        return {
            "containers_scanned": len(results),
            "containers_with_findings": sum(
                1 for item in results if item["finding_count"] > 0
            ),
            "risk_summary": counts,
            "containers": results,
            "read_only": True,
        }
    finally:
        client.close()
