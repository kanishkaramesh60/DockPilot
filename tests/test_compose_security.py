import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANAGER = ROOT / "manager"
if str(MANAGER) not in sys.path:
    sys.path.insert(0, str(MANAGER))

import pytest
from compose_security import ComposeSecurityError, analyze_compose_security


def test_normal_compose_passes_with_warnings_for_default_user_and_published_port():
    report = analyze_compose_security("""
services:
  web:
    image: nginx:alpine
    ports:
      - "8080:80"
""")
    assert report["safe_to_deploy"] is True
    assert report["blocked"] == []
    assert report["warnings"]


@pytest.mark.parametrize("setting", [
    "privileged: true",
    "network_mode: host",
    "pid: host",
    "ipc: host",
    "cap_add: [ALL]",
    "security_opt: [seccomp=unconfined]",
    "devices: [/dev/sda:/dev/sda]",
])
def test_high_risk_settings_are_blocked(setting):
    report = analyze_compose_security(f"services:\n  app:\n    image: alpine\n    {setting}\n")
    assert report["safe_to_deploy"] is False
    assert report["blocked"]


@pytest.mark.parametrize("mount", [
    "/var/run/docker.sock:/var/run/docker.sock",
    "/etc:/host-etc:ro",
    "/:/host:rw",
    "/proc:/host-proc",
    "C:/Windows:/host-windows",
])
def test_sensitive_host_mounts_are_blocked(mount):
    report = analyze_compose_security(f"services:\n  app:\n    image: alpine\n    volumes:\n      - '{mount}'\n")
    assert report["safe_to_deploy"] is False
    assert any("volumes" == item["setting"] for item in report["blocked"])


def test_explicit_root_user_is_warning_not_blocker():
    report = analyze_compose_security("services:\n  app:\n    image: alpine\n    user: '0:0'\n")
    assert report["safe_to_deploy"] is True
    assert any(item["setting"] == "user" for item in report["warnings"])


def test_malformed_yaml_is_rejected():
    with pytest.raises(ComposeSecurityError):
        analyze_compose_security("services: [oops")


def test_non_mapping_top_level_is_rejected():
    with pytest.raises(ComposeSecurityError):
        analyze_compose_security("- just-a-list")
