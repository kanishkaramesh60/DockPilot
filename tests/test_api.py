
from fastapi.testclient import TestClient
from unittest.mock import patch
import main


client = TestClient(main.app)


# 1. Health endpoint
def test_health_endpoint():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}


# 1b. Prometheus metrics endpoint
def test_metrics_endpoint():
    response = client.get("/metrics")
    assert response.status_code == 200
    assert "dockpilot_container_health_status" in response.text
    assert "# HELP dockpilot_container_health_status" in response.text
    assert "# TYPE dockpilot_container_health_status gauge" in response.text


def test_metrics_endpoint_container_states():
    mock_containers = [
        {"id": "c11111111111", "name": "healthy-svc", "health": "healthy"},
        {"id": "c22222222222", "name": "failing-svc", "health": "unhealthy"},
        {"id": "c33333333333", "name": "no-check-svc", "health": "not_configured"},
    ]
    with patch("main._inspect_containers", return_value=mock_containers):
        response = client.get("/metrics")

    assert response.status_code == 200
    text = response.text
    assert 'dockpilot_container_health_status{container_name="healthy-svc",container_id="c11111111111",health="healthy"} 1' in text
    assert 'dockpilot_container_health_status{container_name="failing-svc",container_id="c22222222222",health="unhealthy"} 0' in text
    assert 'dockpilot_container_health_status{container_name="no-check-svc",container_id="c33333333333",health="not_configured"} -1' in text


def test_prometheus_scrape_and_alert_rule_alignment():
    import yaml
    from pathlib import Path

    root = Path(__file__).resolve().parent.parent

    # 1. Verify prometheus.yml scrape targets
    prom_cfg_path = root / "prometheus" / "prometheus.yml"
    assert prom_cfg_path.exists()
    prom_cfg = yaml.safe_load(prom_cfg_path.read_text(encoding="utf-8"))

    jobs = {job["job_name"]: job for job in prom_cfg.get("scrape_configs", [])}
    assert "dockpilot" in jobs
    assert "host.docker.internal:8001" in jobs["dockpilot"]["static_configs"][0]["targets"]
    assert jobs["dockpilot"].get("metrics_path", "/metrics") == "/metrics"
    # Ensure all original jobs are preserved
    for expected_job in ["prometheus", "cadvisor", "node-exporter", "grafana"]:
        assert expected_job in jobs

    # 2. Verify alert_rules.yml ContainerUnhealthy alignment
    rules_path = root / "prometheus" / "alert_rules.yml"
    assert rules_path.exists()
    rules_cfg = yaml.safe_load(rules_path.read_text(encoding="utf-8"))

    all_rules = {}
    for group in rules_cfg.get("groups", []):
        for rule in group.get("rules", []):
            all_rules[rule["alert"]] = rule

    assert "ContainerUnhealthy" in all_rules
    unhealthy_rule = all_rules["ContainerUnhealthy"]
    assert unhealthy_rule["expr"] == "dockpilot_container_health_status == 0"
    assert "$labels.container_name" in unhealthy_rule["annotations"]["summary"]
    assert "$labels.container_name" in unhealthy_rule["annotations"]["description"]
    assert "$labels.container_id" in unhealthy_rule["annotations"]["description"]




# 2. Dashboard route
def test_dashboard_route():
    response = client.get("/")
    assert response.status_code == 200
    assert "text/html" in response.headers.get("content-type", "")
    assert response.text.strip()


# 3. Reject invalid container action
def test_invalid_container_action():
    response = client.post("/api/containers/fake-id/delete")
    assert response.status_code == 400


# 4. Reject invalid container port
def test_invalid_container_port():
    response = client.post(
        "/api/containers",
        json={
            "image": "nginx:alpine",
            "host_port": 70000
        }
    )
    assert response.status_code == 422


# 5. Reject invalid Compose project name
def test_compose_invalid_project_name():
    response = client.post(
        "/api/compose/save",
        json={
            "project_name": "../outside",
            "compose_yaml": "services:\n  web:\n    image: nginx:alpine\n"
        }
    )
    assert response.status_code == 422


# 6. Require confirmation before Compose deployment
def test_compose_deployment_requires_confirmation():
    response = client.post(
        "/api/compose/up",
        json={
            "project_name": "unit-test-project",
            "compose_yaml": "services:\n  web:\n    image: nginx:alpine\n",
            "confirm": False
        }
    )
    assert response.status_code == 400


# 7. List Docker images
def test_list_images():
    with patch(
        "main.list_images",
        return_value=[{"id": "sha256:test123", "tags": ["nginx:alpine"]}]
    ):
        response = client.get("/api/images")

    assert response.status_code == 200
    assert isinstance(response.json(), list)


# 8. List Docker networks
def test_list_networks():
    with patch("main.list_networks", return_value=[]):
        response = client.get("/api/networks")

    assert response.status_code == 200
    assert isinstance(response.json(), list)


# 9. List Docker volumes
def test_list_volumes():
    with patch("main.list_volumes", return_value=[]):
        response = client.get("/api/volumes")

    assert response.status_code == 200
    assert isinstance(response.json(), list)


# 10. List saved Compose configurations
def test_list_saved_compose_projects():
    response = client.get("/api/compose/saved")

    assert response.status_code == 200
    assert isinstance(response.json(), list)


# 11. List deployed Compose projects

def test_list_compose_projects():
    response = client.get("/api/compose/projects")

    assert response.status_code == 200
    assert isinstance(response.json(), list)
