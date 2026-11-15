"""
DockPilot - Automated Environment and Configuration Validator
Validates Python dependencies, Docker Compose, Prometheus, Alertmanager,
Grafana provisioning, port conflicts, and Docker Engine connectivity.
"""

import os
import sys
import socket
import json
from pathlib import Path

# Ensure UTF-8 output on Windows
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

PROJECT_ROOT = Path(__file__).resolve().parent.parent

def print_pass(msg):
    print(f"  [PASS] {msg}")

def print_fail(msg):
    print(f"  [FAIL] {msg}")

def print_warn(msg):
    print(f"  [WARN] {msg}")

def print_info(msg):
    print(f"  [INFO] {msg}")

def check_python_dependencies():
    print("[1/7] Validating Python Dependencies...")
    required = [
        ("fastapi", "fastapi"),
        ("uvicorn", "uvicorn"),
        ("docker", "docker"),
        ("psutil", "psutil"),
        ("yaml", "PyYAML"),
        ("requests", "requests"),
        ("dotenv", "python-dotenv"),
        ("pytest", "pytest"),
    ]
    missing = []
    for mod, pkg in required:
        try:
            __import__(mod)
            print_pass(f"Module '{pkg}' is installed.")
        except ImportError:
            print_fail(f"Module '{pkg}' is NOT installed.")
            missing.append(pkg)
    return len(missing) == 0, missing

def check_docker_connectivity():
    print("\n[2/7] Checking Docker Engine Connectivity...")
    try:
        import docker
        client = docker.from_env()
        info = client.info()
        version = info.get("ServerVersion", "unknown")
        containers = info.get("Containers", 0)
        print_pass(f"Docker Engine connected (Version: {version}, Containers: {containers})")
        client.close()
        return True
    except Exception as e:
        print_fail(f"Cannot connect to Docker daemon: {e}")
        print_info("Ensure Docker Desktop is running.")
        return False

def check_port(port, host="127.0.0.1"):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.5)
        return s.connect_ex((host, port)) == 0

def check_port_conflicts():
    print("\n[3/7] Checking Service Port Availability & Conflicts...")
    ports = {
        8001: "DockPilot Backend",
        9090: "Prometheus",
        3000: "Grafana",
        9093: "Alertmanager",
        8085: "cAdvisor",
    }
    status = {}
    for port, name in ports.items():
        is_used = check_port(port)
        status[port] = is_used
        if is_used:
            print_info(f"Port {port} ({name}) is active / listening.")
        else:
            print_pass(f"Port {port} ({name}) is free.")
    return True, status

def check_docker_compose():
    print("\n[4/7] Validating Docker Compose Configuration...")
    compose_path = PROJECT_ROOT / "monitoring-compose.yaml"
    if not compose_path.exists():
        print_fail(f"File not found: {compose_path}")
        return False
    try:
        import yaml
        with open(compose_path, "r", encoding="utf-8") as f:
            cfg = yaml.safe_load(f)
        services = cfg.get("services", {})
        expected_services = ["prometheus", "cadvisor", "node-exporter", "grafana", "alertmanager"]
        for s in expected_services:
            if s in services:
                print_pass(f"Compose service defined: {s}")
            else:
                print_fail(f"Missing service in compose: {s}")
                return False
        networks = cfg.get("networks", {})
        if "dockpilot-monitoring" in networks:
            print_pass("Network defined: dockpilot-monitoring")
        else:
            print_fail("Missing network: dockpilot-monitoring")
            return False
        return True
    except Exception as e:
        print_fail(f"Error parsing {compose_path}: {e}")
        return False

def check_prometheus_config():
    print("\n[5/7] Validating Prometheus Configuration & Alert Rules...")
    prom_path = PROJECT_ROOT / "prometheus" / "prometheus.yml"
    rules_path = PROJECT_ROOT / "prometheus" / "alert_rules.yml"
    
    if not prom_path.exists():
        print_fail(f"File not found: {prom_path}")
        return False
    if not rules_path.exists():
        print_fail(f"File not found: {rules_path}")
        return False

    try:
        import yaml
        with open(prom_path, "r", encoding="utf-8") as f:
            prom_cfg = yaml.safe_load(f)
        
        jobs = {j["job_name"]: j for j in prom_cfg.get("scrape_configs", [])}
        expected_jobs = ["prometheus", "cadvisor", "node-exporter", "grafana", "dockpilot", "alertmanager"]
        for ej in expected_jobs:
            if ej in jobs:
                print_pass(f"Prometheus scrape job configured: '{ej}'")
            else:
                print_fail(f"Missing scrape job in prometheus.yml: '{ej}'")
                return False
        
        # Check Alertmanager target in prometheus.yml
        alerting = prom_cfg.get("alerting", {}).get("alertmanagers", [])
        if alerting:
            print_pass("Prometheus alerting configured to target Alertmanager.")
        else:
            print_fail("Missing alerting configuration in prometheus.yml")
            return False

        with open(rules_path, "r", encoding="utf-8") as f:
            rules_cfg = yaml.safe_load(f)
        groups = rules_cfg.get("groups", [])
        rule_count = sum(len(g.get("rules", [])) for g in groups)
        print_pass(f"Prometheus alert rules valid: {len(groups)} group(s), {rule_count} rule(s).")
        return True
    except Exception as e:
        print_fail(f"Prometheus configuration error: {e}")
        return False

def check_alertmanager_config():
    print("\n[6/7] Validating Alertmanager Configuration...")
    am_path = PROJECT_ROOT / "alertmanager" / "alertmanager.yml"
    if not am_path.exists():
        print_fail(f"File not found: {am_path}")
        return False
    try:
        import yaml
        with open(am_path, "r", encoding="utf-8") as f:
            am_cfg = yaml.safe_load(f)
        route = am_cfg.get("route", {})
        if route.get("receiver"):
            print_pass(f"Alertmanager default receiver configured: '{route['receiver']}'")
        else:
            print_fail("Missing default receiver in Alertmanager route")
            return False
        receivers = am_cfg.get("receivers", [])
        print_pass(f"Alertmanager receivers defined: {len(receivers)} receiver(s).")
        return True
    except Exception as e:
        print_fail(f"Alertmanager configuration error: {e}")
        return False

def check_grafana_provisioning():
    print("\n[7/7] Validating Grafana Provisioning...")
    ds_path = PROJECT_ROOT / "grafana" / "provisioning" / "datasources" / "prometheus.yml"
    dash_prov = PROJECT_ROOT / "grafana" / "provisioning" / "dashboards" / "dashboard.yml"
    dash_json = PROJECT_ROOT / "grafana" / "dashboards" / "dockpilot-monitoring.json"

    ok = True
    for p in [ds_path, dash_prov, dash_json]:
        if p.exists():
            print_pass(f"Grafana file found: {p.relative_to(PROJECT_ROOT)}")
        else:
            print_fail(f"Missing Grafana file: {p.relative_to(PROJECT_ROOT)}")
            ok = False

    if dash_json.exists():
        try:
            with open(dash_json, "r", encoding="utf-8") as f:
                dash_data = json.load(f)
            panels = dash_data.get("panels", [])
            print_pass(f"Grafana dashboard JSON valid: '{dash_data.get('title')}' with {len(panels)} panels.")
        except Exception as e:
            print_fail(f"Error parsing dashboard JSON: {e}")
            ok = False

    return ok

def main():
    print("=" * 70)
    print("         DockPilot Environment & Configuration Pre-Flight Check")
    print("=" * 70)

    results = []
    r_deps, missing = check_python_dependencies()
    results.append(("Python Dependencies", r_deps))
    results.append(("Docker Connectivity", check_docker_connectivity()))
    r_ports, _ = check_port_conflicts()
    results.append(("Port Checks", r_ports))
    results.append(("Docker Compose Config", check_docker_compose()))
    results.append(("Prometheus Config", check_prometheus_config()))
    results.append(("Alertmanager Config", check_alertmanager_config()))
    results.append(("Grafana Provisioning", check_grafana_provisioning()))

    print("\n" + "=" * 70)
    print("                      Validation Summary")
    print("=" * 70)
    all_ok = True
    for name, res in results:
        status_str = "PASS" if res else "FAIL"
        print(f"  {name:<30} [{status_str}]")
        if not res:
            all_ok = False

    if all_ok:
        print("\n[RESULT] SUCCESS - All environment checks passed. DockPilot is ready.")
        sys.exit(0)
    else:
        print("\n[RESULT] FAILED - One or more configuration checks failed.")
        if missing:
            print(f"Install missing packages using: pip install {' '.join(missing)}")
        sys.exit(1)

if __name__ == "__main__":
    main()
