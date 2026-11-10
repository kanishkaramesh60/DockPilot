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
│   ├── main.py
│   ├── docker_service.py
│   ├── metrics_collector.py
│   ├── metrics_history.py
│   ├── failure_predictor.py
│   ├── incident_engine.py
│   └── compose_security.py
│
├── data/
│   └── dockpilot_history.db
│
├── prometheus/
│   ├── prometheus.yml
│   └── alert_rules.yml
│
├── grafana/
│   └── dashboards/
│       └── dockpilot-monitoring.json
│
├── monitoring-compose.yaml
├── check-monitoring.bat
├── README.md
└── tests/
    └── test_api.py
```

Additional installation scripts, Alertmanager configuration, VM configuration, and notification templates form part of the environment setup and distribution structure.

---

## 7. Installation and Setup

### Prerequisites

- Windows, Linux, or a supported VM environment.
- Docker Desktop or Docker Engine.
- Docker Compose.
- Python 3.10 or later.
- Git.
- A web browser.

For VM-based installation:

- Oracle VirtualBox.
- Vagrant.

### Step 1: Clone the Repository

```cmd
git clone https://github.com/kanishkaramesh60/DockPilot.git
cd DockPilot
```

### Step 2: Create a Python Virtual Environment

```cmd
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

### Step 3: Start the Monitoring Stack

Check the Docker Compose configuration:

```cmd
docker compose -f monitoring-compose.yaml config
```

Start monitoring services:

```cmd
docker compose -f monitoring-compose.yaml up -d
```

### Step 4: Verify Monitoring Containers

```cmd
docker ps
check-monitoring.bat
```

### Step 5: Start the DockPilot Backend

Run the FastAPI application from the project root:

```cmd
uvicorn manager.main:app --host 127.0.0.1 --port 8001
```

### Step 6: Access the Interfaces

| Service | Local URL |
|---|---|
| DockPilot | http://localhost:8000 |
| Prometheus | http://localhost:9090 |
| Grafana | http://localhost:3000 |
| cAdvisor | http://localhost:8085 |

> Grafana credentials depend on the configured environment. Change default credentials before use and keep passwords out of GitHub.

---

## 8. Alert Configuration

| Component | Configuration File |
|---|---|
| Prometheus alert rules | `prometheus/alert_rules.yml` |
| Prometheus configuration | `prometheus/prometheus.yml` |
| Alertmanager configuration | `alertmanager/alertmanager.yml` |

### Example PromQL Expressions

**CPU Usage**

```promql
100 - (avg by (instance) (
  rate(node_cpu_seconds_total{mode="idle"}[1m])
) * 100)
```

**Memory Usage**

```promql
(1 - (
  node_memory_MemAvailable_bytes /
  node_memory_MemTotal_bytes
)) * 100
```

**Available Disk Space**

```promql
(
  node_filesystem_avail_bytes /
  node_filesystem_size_bytes
) * 100
```

**Monitoring Target Status**

```promql
up
```

**Docker Container Health Status (DockPilot Exporter)**

```promql
dockpilot_container_health_status == 0
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
