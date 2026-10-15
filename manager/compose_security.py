"""Conservative static security checks for Docker Compose configuration."""
from __future__ import annotations

from pathlib import PurePosixPath, PureWindowsPath
from typing import Any

import yaml


class ComposeSecurityError(ValueError):
    """Raised when a Compose file is malformed or contains blocked settings."""


def _truthy(value: Any) -> bool:
    return value is True or (isinstance(value, str) and value.strip().lower() in {"true", "yes", "1"})


def _is_sensitive_host_path(path: str) -> bool:
    """Return True for host paths that expose broad or sensitive host resources."""
    raw = path.strip().replace("\\", "/")
    if not raw:
        return False
    lower = raw.lower()
    # Docker socket access is separately blocked, including common Windows mount forms.
    if "docker.sock" in lower:
        return True
    # Match exact roots and descendants, without treating /home/user/data as /home itself.
    posix = PurePosixPath(raw)
    sensitive_posix = ("/", "/etc", "/proc", "/sys", "/dev", "/root", "/boot", "/var/run")
    if raw.startswith("/") and any(str(posix) == root or str(posix).startswith(root.rstrip("/") + "/") for root in sensitive_posix):
        return True
    win = PureWindowsPath(raw)
    if win.drive:
        normalized = str(win).replace("\\", "/").lower().rstrip("/")
        drive_root = win.drive.replace("\\", "/").lower().rstrip("/")
        if normalized == drive_root or normalized in {"c:/windows", "c:/program files", "c:/users"} or any(
            normalized.startswith(root + "/") for root in ("c:/windows", "c:/program files", "c:/users")
        ):
            return True
    return False


def _mount_parts(mount: Any) -> tuple[str | None, str | None]:
    """Return (source, target) for short or long Compose volume syntax."""
    if isinstance(mount, dict):
        source = mount.get("source") or mount.get("src")
        target = mount.get("target") or mount.get("dst") or mount.get("destination")
        return (str(source) if source is not None else None, str(target) if target is not None else None)
    if not isinstance(mount, str):
        return None, None
    # Windows drive letters contain a colon, so split after the drive prefix.
    text = mount.strip()
    if len(text) >= 3 and text[1] == ":" and text[2] in "\\/":
        parts = text[2:].split(":")
        source = text[:2] + parts[0]
        target = parts[1] if len(parts) > 1 else None
    else:
        parts = text.split(":")
        source = parts[0] if len(parts) >= 2 else None
        target = parts[1] if len(parts) >= 2 else None
    return source, target


def analyze_compose_security(compose_text: str) -> dict[str, Any]:
    """Parse Compose YAML and report high-risk blockers plus lower-risk warnings.

    This is a static guardrail, not a complete sandbox or a replacement for review.
    """
    try:
        config = yaml.safe_load(compose_text)
    except yaml.YAMLError as exc:
        raise ComposeSecurityError(f"Compose YAML could not be parsed: {exc}") from exc

    if not isinstance(config, dict):
        raise ComposeSecurityError("Compose YAML must contain a top-level mapping.")
    services = config.get("services", {})
    if not isinstance(services, dict):
        raise ComposeSecurityError("The Compose 'services' section must be a mapping.")

    blocked: list[dict[str, str]] = []
    warnings: list[dict[str, str]] = []

    def block(service: str, setting: str, message: str) -> None:
        blocked.append({"service": service, "setting": setting, "message": message})

    def warn(service: str, setting: str, message: str) -> None:
        warnings.append({"service": service, "setting": setting, "message": message})

    for service_name, service in services.items():
        name = str(service_name)
        if not isinstance(service, dict):
            block(name, "service", "Each service definition must be a mapping.")
            continue

        if _truthy(service.get("privileged")):
            block(name, "privileged", "privileged: true grants the container extensive host-level capabilities.")

        network_mode = str(service.get("network_mode", "")).strip().lower()
        if network_mode == "host":
            block(name, "network_mode", "Host networking bypasses normal container network isolation.")

        if str(service.get("pid", "")).strip().lower() == "host":
            block(name, "pid", "Host PID namespace exposes host process information.")
        if str(service.get("ipc", "")).strip().lower() == "host":
            block(name, "ipc", "Host IPC namespace weakens process isolation.")

        cap_add = service.get("cap_add", []) or []
        if isinstance(cap_add, (str, int)):
            cap_add = [cap_add]
        if any(str(cap).strip().upper() in {"ALL", "SYS_ADMIN"} for cap in cap_add):
            block(name, "cap_add", "Adding ALL or SYS_ADMIN capabilities grants unusually broad privileges.")
        elif cap_add:
            warn(name, "cap_add", "Additional Linux capabilities are enabled; keep only capabilities the service needs.")

        security_opt = service.get("security_opt", []) or []
        if isinstance(security_opt, str):
            security_opt = [security_opt]
        if any("seccomp=unconfined" in str(opt).lower() or "apparmor=unconfined" in str(opt).lower() for opt in security_opt):
            block(name, "security_opt", "Disabling seccomp/AppArmor confinement removes an important security layer.")

        if service.get("devices"):
            block(name, "devices", "Host device access can expose sensitive hardware or host resources.")

        for mount in service.get("volumes", []) or []:
            source, target = _mount_parts(mount)
            if source and _is_sensitive_host_path(source):
                block(name, "volumes", f"Host mount source '{source}' exposes a sensitive host path or Docker socket.")
            elif source and (source.startswith("/") or (len(source) >= 3 and source[1:3] in {":\\", ":/"})):
                warn(name, "volumes", f"Bind mount '{source}' gives the container access to a host path; verify scope and read-only mode.")
            if isinstance(mount, dict) and str(mount.get("type", "")).lower() == "bind":
                if _truthy(mount.get("read_only")) is False and _truthy(mount.get("read_only", False)) is False:
                    # This warning is only added for bind mounts that are not explicitly read-only.
                    if source and not _is_sensitive_host_path(source):
                        warn(name, "volumes", f"Bind mount '{source}' is not explicitly read-only.")

        user = str(service.get("user", "")).strip().lower()
        if user in {"0", "root", "0:0", "root:root"}:
            warn(name, "user", "The service explicitly runs as root; use a non-root user when the image supports it.")
        elif not user:
            warn(name, "user", "No user is specified; the image may run as root by default. Verify the image's default user.")

        if service.get("network_mode") and network_mode != "host":
            warn(name, "network_mode", f"Custom network_mode '{service.get('network_mode')}' reduces Compose network flexibility; review its need.")

        ports = service.get("ports", []) or []
        for port in ports:
            if isinstance(port, dict):
                host_ip = str(port.get("host_ip", ""))
                published = port.get("published")
                if published and not host_ip:
                    warn(name, "ports", f"Published port {published} has no host_ip restriction and may listen on all interfaces.")
            elif isinstance(port, str):
                source, _ = _mount_parts(port)
                # For port syntax, first field is host port, and no IP means wildcard bind.
                if len(port.split(":", 2)) == 2 and source and source.isdigit():
                    warn(name, "ports", f"Published port mapping '{port}' may listen on all host interfaces.")

        if _truthy(service.get("read_only")) is False and "read_only" in service:
            warn(name, "read_only", "The container root filesystem is writable; consider read_only: true if compatible.")

    return {"safe_to_deploy": not blocked, "blocked": blocked, "warnings": warnings}
