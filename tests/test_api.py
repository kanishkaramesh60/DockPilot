
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


def test_alertmanager_compose_and_prometheus_integration():
    import yaml
    from pathlib import Path

    root = Path(__file__).resolve().parent.parent

    # 1. Verify monitoring-compose.yaml Alertmanager service
    compose_path = root / "monitoring-compose.yaml"
    assert compose_path.exists()
    compose_cfg = yaml.safe_load(compose_path.read_text(encoding="utf-8"))

    services = compose_cfg.get("services", {})
    assert "alertmanager" in services
    am_svc = services["alertmanager"]
    assert am_svc.get("image") == "prom/alertmanager:latest"
    assert "9093:9093" in am_svc.get("ports", [])
    assert "dockpilot-monitoring" in am_svc.get("networks", [])
    assert any("dockpilot_alertmanager_data:" in str(v) for v in am_svc.get("volumes", []))
    assert any("alertmanager.yml:/etc/alertmanager/alertmanager.yml:ro" in str(v) for v in am_svc.get("volumes", []))
    assert "dockpilot_alertmanager_data" in compose_cfg.get("volumes", {})

    # 2. Verify prometheus.yml alerting endpoint
    prom_cfg_path = root / "prometheus" / "prometheus.yml"
    prom_cfg = yaml.safe_load(prom_cfg_path.read_text(encoding="utf-8"))

    alerting_cfg = prom_cfg.get("alerting", {})
    alertmanagers = alerting_cfg.get("alertmanagers", [])
    assert len(alertmanagers) >= 1
    am_targets = alertmanagers[0].get("static_configs", [])[0].get("targets", [])
    assert "alertmanager:9093" in am_targets

    # 3. Verify all scrape jobs are preserved
    jobs = {job["job_name"] for job in prom_cfg.get("scrape_configs", [])}
    for expected in ["prometheus", "cadvisor", "node-exporter", "grafana", "dockpilot", "alertmanager"]:
        assert expected in jobs


def test_alertmanager_config_routing_and_receivers():
    import yaml
    from pathlib import Path

    root = Path(__file__).resolve().parent.parent
    am_cfg_path = root / "alertmanager" / "alertmanager.yml"
    assert am_cfg_path.exists()
    am_cfg = yaml.safe_load(am_cfg_path.read_text(encoding="utf-8"))

    # Global
    assert "global" in am_cfg
    assert "smtp_smarthost" in am_cfg["global"]
    assert "smtp_from" in am_cfg["global"]

    # Route
    route = am_cfg.get("route", {})
    assert route.get("receiver") == "dockpilot-default-receiver"
    assert "alertname" in route.get("group_by", [])
    assert "severity" in route.get("group_by", [])

    # Sub-routes
    sub_routes = route.get("routes", [])
    route_map = {}
    for r in sub_routes:
        match = r.get("match", {})
        if "severity" in match:
            route_map[match["severity"]] = r.get("receiver")

    assert route_map.get("critical") == "dockpilot-critical-receiver"
    assert route_map.get("warning") == "dockpilot-warning-receiver"

    # Inhibition rules
    inhibit_rules = am_cfg.get("inhibit_rules", [])
    assert len(inhibit_rules) >= 1
    # Critical inhibits warning, NEVER warning inhibits critical
    for rule in inhibit_rules:
        assert rule.get("source_match", {}).get("severity") == "critical"
        assert rule.get("target_match", {}).get("severity") == "warning"

    # Receivers
    receivers = {rec["name"]: rec for rec in am_cfg.get("receivers", [])}
    assert "dockpilot-default-receiver" in receivers
    assert "dockpilot-critical-receiver" in receivers
    assert "dockpilot-warning-receiver" in receivers

    for name, rec in receivers.items():
        email_configs = rec.get("email_configs", [])
        assert len(email_configs) >= 1
        assert email_configs[0].get("send_resolved") is True


def test_env_example_and_gitignore():
    from pathlib import Path

    root = Path(__file__).resolve().parent.parent

    # .env.example
    env_example = root / ".env.example"
    assert env_example.exists()
    content = env_example.read_text(encoding="utf-8")
    for key in [
        "SMTP_SMARTHOST",
        "SMTP_PORT",
        "SMTP_AUTH_USERNAME",
        "SMTP_AUTH_PASSWORD",
        "SMTP_FROM",
        "ALERT_RECEIVER_EMAIL",
        "ALERT_RECEIVER_CRITICAL_EMAIL",
        "ALERT_RECEIVER_WARNING_EMAIL",
        "SMTP_REQUIRE_TLS"
    ]:
        assert f"{key}=" in content

    # .gitignore
    gitignore = root / ".gitignore"
    assert gitignore.exists()
    gi_content = gitignore.read_text(encoding="utf-8")
    assert ".env" in gi_content


def test_feature5_automated_setup_scripts():
    from pathlib import Path

    root = Path(__file__).resolve().parent.parent

    # 1. install.bat
    install_bat = root / "install.bat"
    assert install_bat.exists(), "install.bat must exist"
    install_text = install_bat.read_text(encoding="utf-8")
    assert "git --version" in install_text or "where git" in install_text
    assert "python" in install_text
    assert "docker compose" in install_text
    assert "monitoring-compose.yaml" in install_text
    assert "venv" in install_text
    assert "8001" in install_text
    assert "check-monitoring.bat" in install_text
    # Ensure .env is preserved and not blindly overwritten
    assert ".env" in install_text
    assert ".env.example" in install_text

    # 2. start.bat
    start_bat = root / "start.bat"
    assert start_bat.exists(), "start.bat must exist"
    start_text = start_bat.read_text(encoding="utf-8")
    assert "docker compose" in start_text
    assert "monitoring-compose.yaml" in start_text
    assert "8001" in start_text

    # 3. stop.bat
    stop_bat = root / "stop.bat"
    assert stop_bat.exists(), "stop.bat must exist"
    stop_text = stop_bat.read_text(encoding="utf-8")
    assert "docker compose" in stop_text
    assert "stop" in stop_text
    assert "8001" in stop_text

    # 4. check-monitoring.bat
    check_bat = root / "check-monitoring.bat"
    assert check_bat.exists(), "check-monitoring.bat must exist"
    check_text = check_bat.read_text(encoding="utf-8")
    assert "dockpilot-prometheus" in check_bat.read_text(encoding="utf-8")
    assert "dockpilot-grafana" in check_text
    assert "dockpilot-alertmanager" in check_text


def test_feature5_safety_rules_and_preservation():
    from pathlib import Path

    root = Path(__file__).resolve().parent.parent

    scripts = [
        root / "install.bat",
        root / "start.bat",
        root / "stop.bat",
        root / "check-monitoring.bat",
    ]

    prohibited_patterns = [
        "docker compose down -v",
        "down -v",
        "volume prune",
        "system prune",
        "docker volume rm",
    ]

    for script in scripts:
        assert script.exists()
        content = script.read_text(encoding="utf-8").lower()
        for pattern in prohibited_patterns:
            assert pattern not in content, f"Destructive command '{pattern}' found in {script.name}"


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
