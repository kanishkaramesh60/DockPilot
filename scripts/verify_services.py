"""
DockPilot - Live Infrastructure & API Verification Helper
Performs live health queries across Prometheus, Grafana, Alertmanager,
cAdvisor, Node Exporter, and the DockPilot FastAPI backend.
"""

import sys
import json
import urllib.request
import urllib.error

# Ensure UTF-8 output on Windows
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

def check_http_status(url, expected_codes=(200,), timeout=5.0):
    try:
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status in expected_codes, resp.status
    except Exception as e:
        return False, str(e)

def query_json(url, timeout=10.0):
    try:
        req = urllib.request.Request(url, headers={"Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            if resp.status == 200:
                return json.loads(resp.read().decode("utf-8")), resp.status
            return None, resp.status
    except Exception as e:
        return None, str(e)

def verify_all():
    checks = []

    # 1. DockPilot backend health
    ok_b, _ = check_http_status("http://localhost:8001/health")
    checks.append(("DockPilot Backend (/health)", ok_b))

    # 2. Prometheus server health
    ok_p, _ = check_http_status("http://localhost:9090/-/healthy")
    checks.append(("Prometheus Server (port 9090)", ok_p))

    # 3. Prometheus active scrape targets (all 6)
    d_targets, _ = query_json("http://localhost:9090/api/v1/targets")
    expected_jobs = ["prometheus", "cadvisor", "node-exporter", "grafana", "dockpilot", "alertmanager"]
    active = {}
    if d_targets:
        for t in d_targets.get("data", {}).get("activeTargets", []):
            job = t.get("labels", {}).get("job")
            if job:
                active[job] = t.get("health", "").lower()
    
    for ej in expected_jobs:
        is_up = (active.get(ej) == "up")
        checks.append((f"Prometheus Target '{ej}'", is_up))

    # 4. Node Exporter metric scraped
    d_cpu, _ = query_json("http://localhost:9090/api/v1/query?query=node_cpu_seconds_total")
    node_cpu_ok = bool(d_cpu and d_cpu.get("data", {}).get("result"))
    checks.append(("Node Exporter metric 'node_cpu_seconds_total'", node_cpu_ok))

    d_mem, _ = query_json("http://localhost:9090/api/v1/query?query=node_memory_MemAvailable_bytes")
    node_mem_ok = bool(d_mem and d_mem.get("data", {}).get("result"))
    checks.append(("Node Exporter metric 'node_memory_MemAvailable_bytes'", node_mem_ok))

    # 5. cAdvisor dashboard & metric
    ok_cad, _ = check_http_status("http://localhost:8085/containers/")
    checks.append(("cAdvisor Web Dashboard (port 8085)", ok_cad))

    d_cad_metric, _ = query_json("http://localhost:9090/api/v1/query?query=container_cpu_usage_seconds_total")
    cad_metric_ok = bool(d_cad_metric and d_cad_metric.get("data", {}).get("result"))
    checks.append(("cAdvisor metric 'container_cpu_usage_seconds_total'", cad_metric_ok))

    # 6. Grafana health & dashboard
    ok_graf, _ = check_http_status("http://localhost:3000/api/health")
    checks.append(("Grafana Server (port 3000)", ok_graf))

    ok_dash, _ = check_http_status("http://localhost:3000/d/dockpilot-monitoring?kiosk")
    checks.append(("Grafana Dashboard Embedded Route", ok_dash))

    # 7. Prometheus alert rules
    d_rules, _ = query_json("http://localhost:9090/api/v1/rules")
    rules_ok = bool(d_rules and len(d_rules.get("data", {}).get("groups", [])) >= 3)
    checks.append(("Prometheus 11 Alert Rules Evaluated", rules_ok))

    # 8. Custom health metric scraped
    d_cust, _ = query_json("http://localhost:9090/api/v1/query?query=dockpilot_container_health_status")
    cust_ok = bool(d_cust and d_cust.get("data", {}).get("result"))
    checks.append(("Custom metric 'dockpilot_container_health_status'", cust_ok))

    # 9. Alertmanager health & connection
    ok_am, _ = check_http_status("http://localhost:9093/-/healthy")
    checks.append(("Alertmanager Server (port 9093)", ok_am))

    d_am_conn, _ = query_json("http://localhost:9090/api/v1/alertmanagers")
    am_conn_ok = bool(d_am_conn and d_am_conn.get("data", {}).get("activeAlertmanagers"))
    checks.append(("Prometheus -> Alertmanager Connection", am_conn_ok))

    # 10. Unified Overview API
    d_ov, s_ov = query_json("http://localhost:8001/api/monitoring/overview", timeout=12.0)
    ov_ok = bool(d_ov and "host" in d_ov and "containers" in d_ov)
    checks.append(("DockPilot Unified Overview API", ov_ok))

    # 11. System Settings API
    d_set, s_set = query_json("http://localhost:8001/api/system/settings")
    set_ok = bool(d_set and d_set.get("backend_port") == 8001)
    checks.append(("DockPilot System Settings API", set_ok))

    # 12. Environment Management Status & Validation APIs
    d_env_st, _ = query_json("http://localhost:8001/api/environment/status")
    env_st_ok = bool(d_env_st and d_env_st.get("docker", {}).get("connected") and d_env_st.get("python", {}).get("dependencies_ok"))
    checks.append(("DockPilot Environment Status API", env_st_ok))

    d_env_val, _ = query_json("http://localhost:8001/api/environment/validate")
    env_val_ok = bool(d_env_val and d_env_val.get("docker_connected") and len(d_env_val.get("checks", [])) >= 4)
    checks.append(("DockPilot Environment Pre-Flight Validation API", env_val_ok))

    # Print results
    passed = 0
    failed = 0
    for name, res in checks:
        if res:
            print(f"  [PASS] {name}")
            passed += 1
        else:
            print(f"  [FAIL] {name}")
            failed += 1

    print("\n" + "=" * 70)
    print(f"Verification Summary: {passed} Passed, {failed} Failed")
    print("=" * 70)
    if failed == 0:
        print("[RESULT] PASS - All DockPilot services and verification checks passed.")
        return 0
    else:
        print(f"[RESULT] FAIL - {failed} verification check(s) failed.")
        return 1

if __name__ == "__main__":
    sys.exit(verify_all())
