"""
Unit and integration tests for DockPilot Environment Management & Pre-Flight Validation.
"""

import sys
from pathlib import Path
from fastapi.testclient import TestClient

# Add manager directory to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "manager"))

from main import app, _check_python_environment, _validate_environment_configs

client = TestClient(app)


def test_python_environment_helper():
    py_stat = _check_python_environment()
    assert "version" in py_stat
    assert "executable" in py_stat
    assert "dependencies_ok" in py_stat
    assert "installed" in py_stat
    assert py_stat["dependencies_ok"] is True
    assert "fastapi" in py_stat["installed"]
    assert "docker" in py_stat["installed"]


def test_validate_environment_configs_helper():
    cfg_stat = _validate_environment_configs()
    assert "overall_valid" in cfg_stat
    assert "checks" in cfg_stat
    assert cfg_stat["overall_valid"] is True
    check_names = [c["name"] for c in cfg_stat["checks"]]
    assert "Compose Configuration" in check_names
    assert "Prometheus & Rules" in check_names
    assert "Alertmanager Routing" in check_names
    assert "Grafana Provisioning" in check_names


def test_api_environment_status():
    response = client.get("/api/environment/status")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] in ("healthy", "attention")
    assert "docker" in data
    assert "python" in data
    assert "services" in data
    assert "validation" in data
    assert isinstance(data["services"], list)
    assert len(data["services"]) >= 5


def test_api_environment_validate():
    response = client.get("/api/environment/validate")
    assert response.status_code == 200
    data = response.json()
    assert "status" in data
    assert "checks" in data
    assert isinstance(data["checks"], list)
    assert len(data["checks"]) >= 4
    for check in data["checks"]:
        assert check["status"] in ("pass", "fail")
