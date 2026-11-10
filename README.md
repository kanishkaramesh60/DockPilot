# DockPilot
### Docker Engine Management, Monitoring and Container Security Dashboard

DockPilot is a local DevOps monitoring and container management platform designed to provide centralized visibility into Docker containers, system resources, application health, and infrastructure alerts.

It integrates Docker Engine, Prometheus, Grafana, cAdvisor, Node Exporter, and Alertmanager to create an all-in-one monitoring environment. The platform provides real-time metrics, historical monitoring, preconfigured dashboards, configurable alert rules, and notification management through a unified local environment.

---

## Table of Contents

1. [Project Overview](#1-project-overview)
2. [Technology Stack](#2-technology-stack)
3. [System Architecture](#3-system-architecture)
4. [Core Features](#4-core-features)
5. [Environment Automation](#5-environment-automation)
6. [Project Directory Structure](#6-project-directory-structure)
7. [Installation and Setup](#7-installation-and-setup)
8. [Alert Configuration](#8-alert-configuration)
9. [Testing and Validation](#9-testing-and-validation)
10. [Security Considerations](#10-security-considerations)
11. [Expected Project Deliverables](#11-expected-project-deliverables)
12. [Future Scope](#12-future-scope)
13. [Project Information](#13-project-information)
14. [Conclusion](#14-conclusion)

---

## 1. Project Overview

Managing Docker containers requires continuous monitoring of resource consumption, container health, infrastructure availability, and potential failures.

DockPilot addresses these requirements by combining container management and infrastructure monitoring tools into a single local platform.

The system collects metrics from Docker containers and the host monitoring environment, stores time-series data in Prometheus, visualizes metrics through Grafana, and processes alerts through Alertmanager.

### Main Objectives

- Monitor Docker containers and system resource utilization.
- Provide centralized monitoring through Grafana dashboards.
- Collect real-time and historical infrastructure metrics.
- Detect abnormal resource utilization and container health issues.
- Generate alerts based on configurable thresholds.
- Route and manage notifications using Alertmanager.
- Automate the monitoring environment setup.
- Provide a reproducible local DevOps sandbox.

---

## 2. Technology Stack

| Technology | Purpose |
|---|---|
| Python | Backend application and monitoring logic |
| FastAPI | Backend REST API |
| Docker Engine | Container management |
| Docker Compose | Monitoring stack orchestration |
| Prometheus | Metrics collection and storage |
| Grafana | Monitoring dashboards and visualization |
| cAdvisor | Docker container metrics |
| Node Exporter | System-level metrics |
| Alertmanager | Alert routing and notification management |
| SQLite | Application history and monitoring records |
| HTML, CSS, JavaScript | Dashboard frontend |
| Batch / Shell scripts | Environment automation |
| Git and GitHub | Version control and project distribution |
| Vagrant / VirtualBox | Reproducible VM-based setup option |

---

## 3. System Architecture

```text
                  DOCKPILOT
                      |
          +-----------+-----------+
          |                       |
    Docker Management       Monitoring Stack
          |                       |
     Docker Engine          +-----+------+
          |                 |            |
    Container State      Prometheus   Exporters
    Container Controls      |         /       \
    Health Information      |    Node Exporter cAdvisor
          |                 |
          +--------+--------+
                   |
              Grafana
                   |
          Preconfigured Dashboards
                   |
             Prometheus
             Alert Rules
                   |
             Alertmanager
                   |
          +--------+---------+
          |                  |
      Alert Routing     Notifications
          |
    Email / Severity /
    Grouping / Deduplication

       DockPilot Backend
              |
       FastAPI REST API
              |
       SQLite History
```

---

## 4. Core Features

### 4.1 Docker Container Management

DockPilot provides a centralized interface to manage Docker containers using the local Docker Engine.

- List available Docker containers.
- Display container names, IDs, images, and status.
- Start, stop, and restart containers.
- Inspect container information.
- Monitor container health status.
- Track container restart information.
- Display container port mappings.

### 4.2 Real-Time Container Monitoring

- Container CPU utilization.
- Container memory consumption.
- Container network activity.
- Container health monitoring.
- Container restart tracking.
- Historical resource utilization.
- Container-level monitoring visualizations.

### 4.3 System Resource Monitoring

- CPU utilization monitoring.
- Memory utilization monitoring.
- Available memory tracking.
- Disk space monitoring.
- Filesystem utilization.
- Network monitoring.
- Historical system resource metrics.

### 4.4 Prometheus Metrics Collection

Prometheus acts as the central metrics collection and time-series monitoring system.

- Configurable scrape intervals.
- Exporter-based metric collection.
- Prometheus self-monitoring.
- cAdvisor, Node Exporter, and Grafana metrics integration.
- DockPilot backend metrics integration.
- Historical time-series storage.
- PromQL-based metric queries.
- Target health monitoring.

### 4.5 cAdvisor Integration

cAdvisor collects Docker container resource metrics:

- Container CPU usage.
- Container memory usage.
- Container network statistics.
- Container resource consumption.
- Container-level performance information.

### 4.6 Node Exporter Integration

Node Exporter provides system-level metrics:

- CPU utilization.
- Memory statistics.
- Filesystem usage.
- Disk availability.
- Network statistics.
- System-level resource information.

### 4.7 Grafana Monitoring Dashboard

Grafana provides centralized visualization using Prometheus as its metrics datasource.

| Section | Contents |
|---|---|
| **A. System Overview** | Overall resource utilization, monitoring environment status, key infrastructure metrics |
| **B. CPU Monitoring** | CPU utilization, usage trends, idle time |
| **C. Memory Monitoring** | Total memory, available memory, used memory percentage, utilization trends |
| **D. Disk and Filesystem** | Available disk space, filesystem utilization, disk usage percentage |
| **E. Docker Container Monitoring** | Container CPU utilization, memory consumption, resource metrics |
| **F. Monitoring Health** | Prometheus status, exporter availability, monitoring target health |
| **G. Alert Monitoring** | Active alerts, alert severity, rule status, threshold violations |

### 4.8 Prometheus Alert Rules

Prometheus evaluates configured alert rules to identify infrastructure and container problems.

| Alert | Condition |
|---|---|
| High CPU Usage | CPU usage exceeds 85% |
| Critical CPU Usage | CPU usage exceeds 95% |
| High Memory Usage | Memory usage exceeds 85% |
| Critical Memory Usage | Memory usage exceeds 95% |
| Low Disk Space | Available disk space falls below 10% |
| Critical Disk Space | Available disk space falls below 5% |
| Container High CPU | Container CPU usage exceeds the configured threshold |
| Container High Memory | Container memory usage exceeds the configured threshold |
| Container Unhealthy | Docker reports an unhealthy container |
| Prometheus Target Down | A monitored target becomes unavailable |
| Prometheus Not Scraping | Expected metrics are no longer being collected |

Alert rules use configurable evaluation intervals and durations to reduce unnecessary notifications.

### 4.9 Alertmanager Integration

- Centralized alert management.
- Severity-based alert routing.
- Warning and critical alert classification.
- Alert grouping and deduplication.
- Email notifications.
- Resolution notifications.
- Notification receiver configuration.
- Alert inhibition and suppression.
- Alert status management.

### 4.10 Application Metrics and History

- Historical container metrics.
- Resource utilization history.
- Container health history.
- Restart records.
- Incident history.
- Monitoring data persistence.
- SQLite-based application data storage.

### 4.11 Container Security Monitoring

DockPilot includes checks for potentially insecure Docker configurations:

- Privileged container configuration.
- Host network mode.
- Security profile configuration.
- Seccomp and AppArmor settings.
- Host filesystem mounts.
- Potentially risky container configurations.

### 4.12 Container Failure Prediction

Rule-based container failure prediction using historical resource information:

- CPU threshold analysis.
- Memory threshold analysis.
- Resource growth monitoring.
- Historical metric evaluation.
- Risk-level classification.
- Container failure prediction results.

### 4.13 Incident Detection

- Unhealthy container detection.
- Container availability checks.
- Resource threshold violations.
- Restart-related issues.
- Incident severity classification.
- Incident history.

### 4.14 Docker Compose Management

- Save Compose configurations.
- Validate Compose files.
- Start Compose applications.
- Inspect configuration issues.
- Check potentially insecure Compose settings.

### 4.15 Unified Web Dashboard (Port 8001)

The entire DockPilot ecosystem is accessible and manageable through ONE unified, production-grade DevOps web dashboard at `http://localhost:8001`.

#### Unified Navigation (14 Dedicated Sections):
1. **Overview**: Executive dashboard displaying real-time Docker container counts, host resource meters (CPU %, Memory %, Disk %, Network I/O), infrastructure service status pills (6 services), Prometheus target health badges (6 targets), active alerts grouped by severity, recent incidents, and container health events.
2. **Docker Containers**: Complete container lifecycle management, search, logs, stats, and run container modal.
3. **Images**: Docker image repository view, pulling images from registries, tag inspection, and pruning.
4. **Networks**: Dedicated Docker network inspection, driver details, subnet tracking, and creation.
5. **Volumes**: Persistent volume management, mount points, drivers, and inspection.
6. **Resource Monitoring**: Real-time canvas CPU, Memory, and Network charts with quick links to cAdvisor (:8085) and Grafana (:3000).
7. **Container Health**: Real-time container health check monitor, failure states, reasons, and recovery attempts.
8. **Prometheus Monitoring**: Live status of all 6 Prometheus scrape targets, all 11 production alert rules, and an embedded Grafana monitoring dashboard (`dockpilot-monitoring`) via an iframe.
9. **Alert Management**: Alertmanager (:9093) integration, cluster status, active firing alerts grouped by severity, receiver channels, and routing policies.
10. **Security Center**: Runtime container security auditor and historical audit trend tracking.
11. **Incident History**: Incident detection, investigation with collected evidence, root-cause analysis, and human-in-the-loop approved recovery execution.
12. **Docker Compose Management**: Compose project management, compose file storage, and Compose Security Auditor.
13. **Historical Metrics**: Long-term CPU and memory metrics history from autoscaling, heuristic failure predictor, and container health event log.
14. **System Settings**: Docker Engine runtime information, service port allocation matrix, persistent storage paths, and Alertmanager notification settings.

---

## 5. Environment Automation

DockPilot provides a reproducible monitoring environment. The installation approach supports Docker Compose and an automated setup option using scripts or Vagrant.

Automation scope:

- Check required dependencies.
- Configure the monitoring environment.
- Create or use the monitoring network.
- Start the monitoring services.
- Configure Prometheus scrape targets.
- Load Grafana datasources.
- Provision Grafana dashboards.
- Configure alert rules.
- Configure Alertmanager.
- Verify service availability.
- Provide startup, shutdown, restart, and status commands.

The VM-based option uses VirtualBox and Vagrant to provide a consistent all-in-one monitoring environment.

---

## 6. Project Directory Structure

```text
DockPilot/
│
├── manager/
│   ├── main.py                     # FastAPI backend & metrics exporter (:8001)
│   ├── docker_service.py           # Docker Engine SDK integration
│   ├── metrics_collector.py        # Real-time container metrics worker
│   ├── metrics_history.py          # SQLite metrics history persistence
│   ├── failure_predictor.py        # Predictive failure heuristics
│   ├── incident_engine.py          # Incident detection & classification
│   └── compose_security.py         # Compose security auditor
│
├── data/
│   └── dockpilot_history.db        # SQLite metrics & incident database
│
├── prometheus/
│   ├── prometheus.yml              # Prometheus scrape jobs & Alertmanager endpoint
│   └── alert_rules.yml             # 11 production alert rules (infrastructure & containers)
│
├── alertmanager/
│   └── alertmanager.yml            # Alert routing, grouping, inhibition & email templates
│
├── grafana/
│   ├── provisioning/
│   │   ├── datasources/prometheus.yml   # Auto-provisioned Prometheus datasource
│   │   └── dashboards/dashboard.yml     # Auto-provisioned dashboard provider
│   └── dashboards/
│       └── dockpilot-monitoring.json    # Complete 39-panel observability dashboard
│
├── scripts/
│   └── apply_alertmanager_env.py   # Secure .env-to-alertmanager.yml sync & hot-reload
│
├── .env.example                    # Environment secrets template
├── monitoring-compose.yaml         # Orchestration for Prometheus, Grafana, Alertmanager, cAdvisor, Node Exporter
├── install.bat                     # Feature 5: Automated prerequisites, venv, compose & health setup
├── start.bat                       # Feature 5: Fast startup for backend & monitoring stack
├── stop.bat                        # Feature 5: Safe shutdown script preserving all volumes
├── check-monitoring.bat            # 30-point monitoring infrastructure health check (12 categories)
├── pytest.ini                      # Pytest configuration
├── README.md                       # Comprehensive system documentation
└── tests/
    ├── test_api.py                 # Core API, scrape targets, Alertmanager & Feature 5 tests
    ├── test_compose_security.py    # Security audit tests
    ├── test_container_health.py    # Container health & metrics exporter tests
    ├── test_resilience_lab.py      # Chaos testing suite
    ├── test_security.py            # Container vulnerability tests
    └── test_security_audit_history.py # Audit history database tests
```

---

## 7. Automated Installation and Setup (Feature 5)

DockPilot is engineered to be fully installable, configurable, and runnable on a fresh Windows machine with a single command (`install.bat`), while strictly safeguarding existing persistent volumes, metrics databases, and environment secrets.

### 7.1 Automated One-Click Installation (`install.bat`)

To install DockPilot on a fresh Windows machine, clone the repository and run `install.bat` from a Windows Command Prompt (CMD) with administrative privileges:

```cmd
git clone https://github.com/kanishkaramesh60/DockPilot.git
cd DockPilot
install.bat
```

`install.bat` automatically executes a 7-stage end-to-end installation and verification pipeline:

```text
==============================================================================
                     DockPilot - Installation and Setup
==============================================================================
[1/7] Verifying system prerequisites...
      - Git (PATH check and version verification)
      - Python 3.10+ (verifies runtime >= 3.10)
      - Docker CLI & Docker Compose v2 (validates docker compose)
      - Docker Engine Daemon (verifies daemon connectivity)
[2/7] Checking required project files and directories...
      - Verifies core files: monitoring-compose.yaml, manager\main.py,
        prometheus.yml, alert_rules.yml, alertmanager.yml, dashboard json
      - Automatically creates data\, reports\, and logs\ runtime directories
[3/7] Setting up Python virtual environment and dependencies...
      - Creates isolated .\venv environment if missing
      - Upgrades pip and installs manager\requirements.txt, pytest, and httpx
[4/7] Checking environment configuration...
      - If .env is missing, initializes it safely from .env.example
      - If .env already exists, strictly preserves existing secrets and SMTP settings
[5/7] Validating and starting Docker monitoring services...
      - Validates syntax using docker compose -f monitoring-compose.yaml config
      - Starts Prometheus, Grafana, Alertmanager, cAdvisor, Node Exporter via up -d
[6/7] Starting DockPilot FastAPI backend service (port 8001)...
      - Detects if backend is already running on port 8001
      - Launches backend in background using uvicorn with --app-dir manager
      - Actively polls port 8001 until the socket is listening
[7/7] Verifying service readiness and Prometheus targets...
      - Automatically invokes check-monitoring.bat
      - Validates all 30 checks across 12 monitoring categories
==============================================================================
```

### 7.2 Service Lifecycle Commands (Day-to-Day Operations)

DockPilot provides dedicated Windows batch scripts for routine operational management:

| Command | Script File | Purpose & Behavior |
|---|---|---|
| **Full Install** | `install.bat` | End-to-end prerequisites validation, venv setup, dependencies install, container spin-up, backend launch, and 30-point health check. |
| **Start Stack** | `start.bat` | Fast daily startup. Verifies Docker daemon, starts monitoring containers via `docker compose up -d`, starts FastAPI backend on port 8001 if not already running, and outputs interface URLs. |
| **Stop Stack** | `stop.bat` | Gracefully terminates FastAPI backend process on port 8001 and halts containers using `docker compose stop`. **Never deletes volumes or data.** |
| **Health Check** | `check-monitoring.bat` | Runs 30 automated integration checks across 12 categories covering containers, endpoints, metrics, Grafana panels, alert rules, and Alertmanager routing. |

#### Starting All Services
```cmd
start.bat
```

#### Stopping All Services Safely
```cmd
stop.bat
```

#### Verifying Infrastructure Health
```cmd
check-monitoring.bat
```

### 7.3 Fresh Machine vs. Repeated Run Behavior (Idempotency)

DockPilot's automation scripts are fully **idempotent** and safe to execute repeatedly:

- **Virtual Environment**: If `.\venv` exists, `install.bat` reuses the existing environment and updates packages, avoiding slow re-creation.
- **Environment Secrets (`.env`)**: If `.env` already exists, `install.bat` will **never** overwrite it. User-configured SMTP credentials and secrets remain untouched.
- **Port 8001 Backend Detection**: If the FastAPI backend is already listening on port 8001, both `install.bat` and `start.bat` recognize the running process (by PID) and avoid launching duplicate instances.
- **Container Idempotency**: Docker Compose ensures only stopped or missing containers are started. Running containers are left undisturbed.

### 7.4 Manual Configuration & Setup Notes

While `install.bat` automates software installation and orchestration, two items require user configuration:

#### 1. Docker Desktop on Windows
- Docker Desktop must be installed and running before executing `install.bat` or `start.bat`.
- Ensure Docker Desktop is set to **Linux containers** mode.
- If Docker Desktop is stopped, `install.bat` will detect this in Step 1 and provide clear instructions to start the daemon before re-running.

#### 2. SMTP Credentials for Email Alerting (Optional)
To enable real email delivery from Alertmanager:
1. Open the `.env` file in the project root.
2. Fill in your SMTP server credentials:
   ```env
   SMTP_SMARTHOST=smtp.gmail.com
   SMTP_PORT=587
   SMTP_AUTH_USERNAME=your-email@gmail.com
   SMTP_AUTH_PASSWORD=your-app-password
   SMTP_FROM=dockpilot-alerts@yourdomain.com
   ALERT_RECEIVER_EMAIL=devops-admin@yourdomain.com
   ALERT_RECEIVER_CRITICAL_EMAIL=devops-critical@yourdomain.com
   ALERT_RECEIVER_WARNING_EMAIL=devops-warning@yourdomain.com
   SMTP_REQUIRE_TLS=true
   ```
3. Synchronize the environment variables into `alertmanager/alertmanager.yml` and hot-reload Alertmanager:
   ```cmd
   venv\Scripts\python.exe scripts\apply_alertmanager_env.py
   ```

### 7.5 Safety & Data Preservation Guarantees

DockPilot follows strict DevOps safety practices to protect production telemetry and monitoring history:

> [!CAUTION]
> **Data Preservation Policy:**
> - DockPilot scripts **NEVER** use `docker compose down -v`.
> - DockPilot scripts **NEVER** run `docker volume prune` or `docker system prune`.
> - All named Docker volumes (`dockpilot_prometheus_data`, `dockpilot_grafana_data`, `dockpilot_alertmanager_data`) are permanent and retained across all restarts and stops.
> - The application SQLite history database (`data\dockpilot_history.db`) is preserved across shutdowns.

### 7.6 Service Access & Default Credentials

Once started, all services are accessible via localhost:

| Service | Local URL | Default Credentials | Description |
|---|---|---|---|
| **DockPilot Dashboard** | http://localhost:8001 | None (direct access) | Container management, metrics graphs, incident & security dashboard |
| **DockPilot REST API Docs** | http://localhost:8001/docs | None | Swagger UI for all REST endpoints & metrics engine |
| **Grafana Dashboard** | http://localhost:3000 | `admin` / `admin` | Centralized 39-panel observability dashboard |
| **Prometheus Web UI** | http://localhost:9090 | None | TSDB metrics engine, targets status & 11 alert rules |
| **Alertmanager Web UI** | http://localhost:9093 | None | Alert routing, grouping, silencing & active notifications |
| **cAdvisor Telemetry** | http://localhost:8085 | None | Real-time container resource telemetry & cgroup statistics |

### 7.7 Troubleshooting Guide

| Issue / Symptom | Possible Cause | Solution |
|---|---|---|
| `[FAIL] Docker daemon is not running` | Docker Desktop is not started or initializing. | Open Docker Desktop, wait for the status indicator to show green ("Engine running"), then re-run `install.bat`. |
| Port `8001` already in use | Another application or an orphaned uvicorn process is occupying port 8001. | Run `stop.bat` to terminate any orphaned process on port 8001, or run `netstat -ano \| findstr :8001` to identify the conflicting process. |
| Grafana reports `Datasource not found` | Prometheus container started after Grafana. | Run `docker compose -f monitoring-compose.yaml restart grafana` or run `check-monitoring.bat` to re-verify provisioning. |
| Alertmanager email delivery fails | SMTP host, port, or app password incorrect in `.env`. | Verify `.env` credentials, ensure an App Password (not standard account password) is used for Gmail/Outlook, and run `venv\Scripts\python.exe scripts\apply_alertmanager_env.py`. |
| Scrape target `dockpilot` shows DOWN in Prometheus | Backend process not running or firewall blocking `host.docker.internal`. | Ensure backend is active via `start.bat`. Confirm `http://localhost:8001/metrics` responds in your browser. |

---

## 8. Prometheus Alert Rules & Alertmanager Integration

DockPilot integrates **Prometheus Alertmanager** into the monitoring stack to collect, group, deduplicate, route, and deliver rich HTML email notifications for alerts evaluated by Prometheus.

```mermaid
flowchart TD
    subgraph Targets["Scrape Targets (5 + Alertmanager)"]
        CA["cAdvisor (:8085)"]
        NE["Node Exporter (:9100)"]
        DP["DockPilot Exporter (:8001)"]
        PR["Prometheus (:9090)"]
        GF["Grafana (:3000)"]
        AM["Alertmanager (:9093)"]
    end

    subgraph PrometheusEngine["Prometheus Engine (:9090)"]
        RULES["alert_rules.yml<br/>11 Production Rules"]
        TSDB[("Prometheus TSDB")]
        EVAL{"Rule Evaluator<br/>(Every 10s)"}
    end

    subgraph AlertmanagerService["Alertmanager Service (:9093)"]
        ROUTER{"Severity Router<br/>(alertmanager.yml)"}
        INHIBIT["Inhibition Rules<br/>(Critical inhibits Warning)"]
        DEDUP["Deduplication &amp; Grouping<br/>(alertname + severity)"]
        REC_CRIT["Critical Receiver<br/>devops-critical@..."]
        REC_WARN["Warning Receiver<br/>devops-warning@..."]
        REC_DEF["Default Receiver<br/>admin@..."]
    end

    subgraph Notifications["Notification Delivery"]
        EMAIL_CRIT["📧 Critical Alert Email<br/>(Immediate Dispatch, group_wait: 10s)"]
        EMAIL_WARN["📧 Warning Alert Email<br/>(group_wait: 10s)"]
        EMAIL_RESOLV["✅ Resolution Email<br/>(send_resolved: true)"]
    end

    Targets -->|Pull Metrics (10s)| PrometheusEngine
    PrometheusEngine --> RULES
    RULES --> EVAL
    EVAL -->|Push Firing / Resolved Alerts| AlertmanagerService
    ROUTER --> INHIBIT
    INHIBIT --> DEDUP
    DEDUP -->|severity: critical| REC_CRIT --> EMAIL_CRIT
    DEDUP -->|severity: warning| REC_WARN --> EMAIL_WARN
    DEDUP -->|status: resolved| EMAIL_RESOLV
    DEDUP -->|unmatched| REC_DEF
```

### Component Configuration Files

| Component | Configuration File | Purpose |
|---|---|---|
| **Prometheus alert rules** | `prometheus/alert_rules.yml` | 11 declarative alert rules across Infra, Containers, and Monitoring |
| **Prometheus configuration** | `prometheus/prometheus.yml` | Configures scrape targets and `alerting.alertmanagers` pointing to `alertmanager:9093` |
| **Alertmanager configuration** | `alertmanager/alertmanager.yml` | Severity routing, receivers, group intervals, HTML templates, and inhibition rules |
| **Environment Template** | `.env.example` | Template for SMTP credentials and receiver email addresses |
| **Environment Sync Script** | `scripts/apply_alertmanager_env.py` | Synchronizes `.env` credentials to `alertmanager.yml` and hot-reloads via `/-/reload` |

### Alert Severity Routing Matrix

Alertmanager matches labels evaluated by Prometheus and routes notifications to the appropriate receiver:

| Severity | Receiver Name | Destination Email | Repeat Interval | Behavior |
|---|---|---|---|---|
| `critical` | `dockpilot-critical-receiver` | `devops-critical@dockpilot.local` | 2h | High-priority immediate alert; sends firing and resolved notifications |
| `warning` | `dockpilot-warning-receiver` | `devops-warning@dockpilot.local` | 2h | Warning-level alerts; inhibited if a critical alert is firing on the same instance |
| *fallback* | `dockpilot-default-receiver` | `admin@dockpilot.local` | 2h | Default fallback for unclassified or info-level alerts |

### Inhibition Rules

To avoid notification floods during major infrastructure failures, Alertmanager enforces inhibition:
- **Rule:** A `critical` alert suppresses any `warning` alert with the matching `alertname` and `instance`.
- **Guarantee:** Critical alerts are **never** suppressed by warning alerts.

### Configuring SMTP Email Notifications

DockPilot keeps credentials strictly outside source control. Configure your email provider using `.env`:

1. Copy `.env.example` to `.env`:
   ```cmd
   copy .env.example .env
   ```

2. Edit `.env` with your SMTP provider details:
   ```env
   SMTP_SMARTHOST=smtp.gmail.com
   SMTP_PORT=587
   SMTP_AUTH_USERNAME=your-email@gmail.com
   SMTP_AUTH_PASSWORD=your-16-char-app-password
   SMTP_FROM=your-email@gmail.com
   ALERT_RECEIVER_CRITICAL_EMAIL=devops-critical@yourdomain.com
   ALERT_RECEIVER_WARNING_EMAIL=devops-warning@yourdomain.com
   SMTP_REQUIRE_TLS=true
   ```

3. Synchronize credentials into Alertmanager:
   ```cmd
   python scripts/apply_alertmanager_env.py
   ```
   The script updates `alertmanager/alertmanager.yml` and calls `POST http://localhost:9093/-/reload` to hot-reload without container downtime.

> [!TIP]
> **Gmail Setup:** Enable 2-Step Verification in Google Account Settings, navigate to **Security → App Passwords**, generate a password for "DockPilot Alertmanager", and paste the 16-character token into `SMTP_AUTH_PASSWORD`.

### Example PromQL Alert Expressions

**Host CPU Usage**
```promql
100 - (avg by (instance) (rate(node_cpu_seconds_total{mode="idle"}[1m])) * 100) > 85
```

**Host Memory Usage**
```promql
((1 - (node_memory_MemAvailable_bytes / node_memory_MemTotal_bytes)) * 100) > 85
```

**Filesystem Available Space**
```promql
((node_filesystem_avail_bytes{fstype!~"tmpfs|rootfs|ramfs", mountpoint=~"/var/lib|/mnt/host/[cd]"} / node_filesystem_size_bytes{...}) * 100) < 10
```

**Docker Container Health Status (DockPilot Exporter)**
```promql
dockpilot_container_health_status == 0
```

**Monitoring Infrastructure Targets Availability**
```promql
up == 0
```

---

## 9. Testing and Validation

DockPilot uses application-level and monitoring-level validation.

Testing scope:

- Backend API testing.
- Docker container operation testing.
- Metrics endpoint validation.
- Prometheus target health checks.
- Prometheus alert rule validation.
- PromQL query validation.
- Grafana datasource validation.
- Dashboard provisioning validation.
- Alertmanager routing validation.
- Email notification testing.
- Alert resolution testing.
- Installation and restart testing.
- Historical metrics persistence testing.

Run backend tests:

```cmd
pytest -v
```

Run monitoring checks:

```cmd
check-monitoring.bat
```

---

## 10. Security Considerations

- Bind local services to localhost when external access is unnecessary.
- Do not expose Docker Engine APIs publicly.
- Avoid privileged containers unless explicitly required.
- Review host filesystem mounts.
- Use secure container configurations.
- Protect Grafana credentials.
- Store notification credentials outside source control.
- Restrict access to monitoring interfaces.
- Avoid committing environment files containing secrets.

---

## 11. Expected Project Deliverables

1. DockPilot Docker management dashboard.
2. Docker-based monitoring environment.
3. Prometheus configuration and metric collection.
4. Node Exporter and cAdvisor integration.
5. Preconfigured Grafana dashboards.
6. Prometheus alert rule configuration.
7. Alertmanager notification and routing configuration.
8. Automated installation scripts or Vagrantfile.
9. Startup, shutdown, and health-check procedures.
10. Installation and configuration documentation.
11. GitHub source repository.
12. Testing results and screenshots.
13. Project demonstration.

---

## 12. Future Scope

- Advanced incident correlation.
- Explainable root-cause analysis.
- Machine-learning-based failure prediction.
- Human-approved container recovery.
- Advanced security analytics.
- Multi-host Docker monitoring.

---

## 13. Project Information

| | |
|---|---|
| **Project Name** | DockPilot |
| **Project Domain** | DevOps Monitoring, Docker Management and Container Security |
| **Project Type** | Local DevOps Monitoring Sandbox |
| **Primary Technologies** | Docker, Prometheus, Grafana, cAdvisor, Node Exporter and Alertmanager |
| **Repository** | https://github.com/kanishkaramesh60/DockPilot |
| **Deployment Model** | Local environment / All-in-One VM |

---

## 14. Conclusion

DockPilot brings Docker container management, infrastructure monitoring, metric visualization, and alert notification into one centralized local environment.

By integrating Docker Engine with Prometheus, Grafana, exporters, and Alertmanager, the platform provides visibility into system performance, container health, and infrastructure availability.

The project demonstrates practical DevOps monitoring concepts, infrastructure automation, container management, observability, and alerting in a reproducible local environment.
