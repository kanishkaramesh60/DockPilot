<div align="center">

# 🚢 DockPilot

### Docker Container Management, Monitoring & Security Dashboard

*One dashboard for container operations, resource monitoring, Compose management, autoscaling, health checks, and security auditing.*

<br>

![Python](https://img.shields.io/badge/Python-3.13-3776AB?style=for-the-badge&logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-009688?style=for-the-badge&logo=fastapi&logoColor=white)
![Docker](https://img.shields.io/badge/Docker-2496ED?style=for-the-badge&logo=docker&logoColor=white)
![SQLite](https://img.shields.io/badge/SQLite-003B57?style=for-the-badge&logo=sqlite&logoColor=white)
![JavaScript](https://img.shields.io/badge/JavaScript-F7DF1E?style=for-the-badge&logo=javascript&logoColor=black)
![Tests](https://img.shields.io/badge/tests-72%20passed-brightgreen?style=for-the-badge&logo=pytest&logoColor=white)

<br>

[Features](#-features) •
[Architecture](#%EF%B8%8F-system-architecture) •
[Quick Start](#-quick-start) •
[Testing](#-testing) •
[Security](#-security-considerations) •
[Roadmap](#-future-improvements)

</div>

---

## 📖 Table of Contents

- [Overview](#-project-overview)
- [Features](#-features)
- [System Architecture](#%EF%B8%8F-system-architecture)
- [Technology Stack](#-technology-stack)
- [Project Structure](#-project-structure)
- [Quick Start](#-quick-start)
- [Testing](#-testing)
- [Security Considerations](#-security-considerations)
- [Use Cases](#-use-cases)
- [Limitations](#-limitations)
- [Future Improvements](#-future-improvements)
- [Project Status](#-project-status)
- [Author](#-author)
- [License](#-license)

---

## 📌 Project Overview

Managing Docker workloads often means juggling terminal commands and multiple tools to inspect containers, monitor resource usage, troubleshoot health issues, and review security configurations.

**DockPilot** simplifies these workflows with a centralized web dashboard backed by live Docker Engine data. It is built with **Python, FastAPI, HTML, CSS, JavaScript**, and direct **Docker Engine** integration.

The application includes operational safeguards, configuration validation, automated tests, and persistent security audit history.

---

## ✨ Features

<table>
<tr>
<td width="50%" valign="top">

### 🐳 Container Management
- View containers and their states
- Inspect container details and logs
- Perform supported container operations from the dashboard
- Validate requests before executing actions

</td>
<td width="50%" valign="top">

### 📦 Docker Resources
- View images, networks, and volumes
- Review Docker Compose projects
- Access resources through the configured Docker Engine

</td>
</tr>
<tr>
<td width="50%" valign="top">

### 📊 Resource Monitoring
- CPU usage visualization
- Memory consumption monitoring
- Network activity graphs
- Per-container resource utilization

</td>
<td width="50%" valign="top">

### ❤️ Health Monitoring
- Track container health states
- No duplicate alerts for repeated unhealthy checks
- Recovery events when a container becomes healthy
- Stale alert state cleared for deleted containers
- Restart rate limiting to prevent excessive restarts
- Docker command failures reported safely

</td>
</tr>
</table>

### 🔄 Autoscaling

| Rule | Behavior |
|---|---|
| **Scale up** | After 1 minute of sustained high CPU |
| **Scale down** | After 3 minutes of sustained low CPU |
| **Replica limits** | Enforces minimum and maximum replicas |
| **Cooldown** | Applied after every successful scaling action |
| **Validation** | Configuration is validated; failed operations are reported |

### 🛡️ Docker Compose Security Validation

Compose configurations are inspected for risky settings. Depending on the rule, a configuration is either **blocked** or reported with a **warning**.

- 🔓 Privileged containers
- 🌐 Host network, PID, and IPC namespaces
- ⚡ Excessive Linux capabilities
- 🚫 Unconfined seccomp configurations
- 🔌 Device mappings
- 🧦 Docker socket mounts
- 📁 Sensitive host filesystem mounts

### 🔍 Container Security Auditing
- Audit containers from the configured Docker Engine
- See how many containers were scanned
- Summaries grouped by severity
- Detailed security audit reports
- Highlights configurations that need further investigation

### 🗃️ Security Audit History
- Completed audit reports persisted in **SQLite**
- Browse previously saved reports with timestamps and severity summaries
- Severity trend visualization across saved audits
- Report comparison *(when the comparison interface is enabled)*
- Refresh saved history without running a new audit

---

## 🏗️ System Architecture

```text
                  ┌─────────────────────────┐
                  │          User           │
                  └────────────┬────────────┘
                               │
                               ▼
                  ┌─────────────────────────┐
                  │    DockPilot Dashboard  │
                  │      HTML / CSS / JS    │
                  └────────────┬────────────┘
                               │ HTTP Requests
                               ▼
                  ┌─────────────────────────┐
                  │     FastAPI Backend     │
                  │     Python / Uvicorn    │
                  └────────────┬────────────┘
                               │
              ┌────────────────┼─────────────────┐
              │                │                 │
              ▼                ▼                 ▼
      ┌──────────────┐ ┌──────────────┐ ┌────────────────┐
      │ Container &  │ │ Monitoring & │ │ Security Audit │
      │ Compose APIs │ │ Autoscaling  │ │ & Audit History│
      └──────┬───────┘ └──────┬───────┘ └───────┬────────┘
             │                │                 │
             └────────────────┼─────────────────┘
                              ▼
                  ┌─────────────────────────┐
                  │      Docker Engine      │
                  │ Containers, Images,     │
                  │ Networks and Volumes    │
                  └─────────────────────────┘

                  Security Audit History
                              │
                              ▼
                  ┌─────────────────────────┐
                  │     SQLite Database     │
                  │    Saved Audit Reports  │
                  └─────────────────────────┘
```

<details>
<summary><b>📋 Component responsibilities</b></summary>

<br>

| Component | Responsibility |
|---|---|
| Frontend | Displays the dashboard and handles user interactions |
| FastAPI | Provides API endpoints and validates incoming requests |
| Docker integration | Retrieves Docker resource data and supports container operations |
| Monitoring modules | Present resource metrics and container health information |
| Autoscaling logic | Evaluates CPU thresholds, replica limits, and cooldown rules |
| Security validator | Checks Compose configurations against implemented security rules |
| Audit history | Stores and retrieves saved security audit reports |
| SQLite | Provides persistent local storage for audit history |

</details>

---

## 🧰 Technology Stack

| Technology | Purpose |
|---|---|
| ![Python](https://img.shields.io/badge/-Python-3776AB?logo=python&logoColor=white) | Backend and application logic |
| ![FastAPI](https://img.shields.io/badge/-FastAPI-009688?logo=fastapi&logoColor=white) | REST API and request handling |
| ![Uvicorn](https://img.shields.io/badge/-Uvicorn-499848) | ASGI application server |
| ![Docker](https://img.shields.io/badge/-Docker-2496ED?logo=docker&logoColor=white) | Container runtime and resource management (Engine + SDK where used) |
| ![HTML5](https://img.shields.io/badge/-HTML5-E34F26?logo=html5&logoColor=white) ![CSS3](https://img.shields.io/badge/-CSS3-1572B6?logo=css3&logoColor=white) ![JS](https://img.shields.io/badge/-JavaScript-F7DF1E?logo=javascript&logoColor=black) | Dashboard structure, styling, and interactions |
| ![SQLite](https://img.shields.io/badge/-SQLite-003B57?logo=sqlite&logoColor=white) | Persistent security audit history |
| ![pytest](https://img.shields.io/badge/-pytest-0A9EDC?logo=pytest&logoColor=white) | Automated testing |

---

## 📂 Project Structure

```text
dockpilot/
│
├── manager/                  # FastAPI backend
│   ├── main.py
│   ├── docker_service.py
│   └── ...
│
├── dashboard/                # Frontend
│   └── index.html
│
├── tests/                    # pytest suite
│   ├── test_api.py
│   ├── test_autoscaler.py
│   ├── test_autoscaling_controller.py
│   ├── test_compose_security.py
│   ├── test_container_health.py
│   ├── test_security.py
│   ├── test_security_audit_history.py
│   └── ...
│
├── data/
│   └── security_audit_history.db
│
├── pytest.ini
└── README.md
```

> **Note:** This is a representative structure. The SQLite database is created or used at runtime, depending on the configured database path.

---

## 🚀 Quick Start

### Prerequisites

- 🖥️ Windows 10/11 or another supported OS
- 🐍 Python 3.13 (or a compatible project-supported version)
- 🐳 Docker Desktop or an accessible Docker Engine
- 🔧 Git
- ⌨️ A terminal such as Windows Command Prompt

### 1️⃣ Clone the repository

```bash
git clone https://github.com/YOUR_GITHUB_USERNAME/dockpilot.git
cd dockpilot
```

### 2️⃣ Create and activate a virtual environment

```cmd
python -m venv .venv
.venv\Scripts\activate
```

### 3️⃣ Install dependencies

Install the packages listed in your project's dependency file (for example `requirements.txt`), if present.

> 💡 If your repository has no dependency file yet, create one from the packages the project actually uses before publishing.

### 4️⃣ Start Docker Desktop and verify access

```cmd
docker version
docker ps -a
```

### 5️⃣ Start the DockPilot backend

```cmd
cd /d D:\CyberProjects\dockpilot\manager
..\.venv\Scripts\python.exe -m uvicorn main:app --reload --host 127.0.0.1 --port 8001
```

### 6️⃣ Open DockPilot

| Page | URL |
|---|---|
| 🎛️ Dashboard | http://127.0.0.1:8001/ |
| 📚 API docs | http://127.0.0.1:8001/docs |
| 💚 Health endpoint | http://127.0.0.1:8001/health |

> Keep the backend terminal running while you use the dashboard.

---

## 🧪 Testing

DockPilot uses **pytest** to validate API behavior, security rules, autoscaling logic, container health handling, and audit history.

```cmd
.venv\Scripts\python.exe -m pytest -v
```

### ✅ Verified Result: **72 tests passed**

<details>
<summary><b>What the tests cover</b></summary>

<br>

- API health and dashboard routes
- Invalid container actions and ports
- Docker resource listing
- Compose project validation
- Autoscaling thresholds and replica limits
- Autoscaling cooldown behavior
- Compose security checks
- Container health alerts and restart rate limiting
- Confirmation requirements for selected operations
- Security audit-history retrieval and persistence

</details>

The reported run also included one non-fatal Starlette/httpx deprecation warning.

> Passing tests validate the covered code paths. Manual verification against the configured Docker Engine is still recommended.

---

## 🔐 Security Considerations

DockPilot includes input validation and safety checks for selected Docker operations:

- ✔️ Validates container operation requests
- ✔️ Rejects invalid ports and Compose project names
- ✔️ Requires confirmation for selected Compose operations
- ✔️ Detects or blocks risky Compose configurations per implemented rules
- ✔️ Enforces autoscaling limits and cooldowns
- ✔️ Limits repeated health-monitor restart actions
- ✔️ Stores completed audit reports for later review

> [!WARNING]
> Run DockPilot only in Docker environments you are authorized to manage. Do not expose the dashboard to untrusted networks without proper authentication, authorization, and deployment security. Review every operation before confirming it, especially when it affects important containers or host resources.

---

## 🎯 Use Cases

- 🏠 Local Docker container management
- 🛠️ Development environment monitoring
- 📦 Docker Compose project inspection
- 📈 Container resource usage visualization
- 🩺 Container health troubleshooting
- 🔒 Docker configuration security review
- 🕰️ Historical security audit review
- 🎓 Demonstrating Docker automation and backend API development

---

## 🚧 Limitations

- Targets the configured Docker Engine, primarily for local development and management
- Security findings depend on the implemented rules and need contextual review
- Resource graphs are not a substitute for a full long-term observability platform
- Automated tests do not replace end-to-end testing against a real Docker environment
- Not a Kubernetes replacement or a cloud fleet-management system

---

## 🔮 Future Improvements

Possible extensions (not yet claimed as implemented):

- [ ] Authentication and role-based access control
- [ ] More extensive browser-level integration tests
- [ ] Packaging for easier installation
- [ ] Improved operational logging and diagnostics
- [ ] Additional security reporting and documentation

---

## 📌 Project Status

DockPilot has a **working dashboard** and a reported automated test suite with **72 passing tests**, bringing Docker resource management, monitoring, Compose support, autoscaling logic, container health monitoring, and security audit history into one interface.

**Current priorities:** preserve working functionality, complete manual integration verification, fix genuine defects, and prepare the project for demonstration.

---

## 👨‍💻 Author

**Your Name** — *Add your preferred name here*
**GitHub:** [Add your profile link](https://github.com/YOUR_GITHUB_USERNAME)
**Project:** DockPilot — Docker Container Management and Security Dashboard

---

## 📄 License

Add a license before distributing the project publicly. The [MIT License](https://choosealicense.com/licenses/mit/) is a common choice if its terms suit your intended use.

---

<div align="center">

**If you find DockPilot useful, consider giving the repo a ⭐**

</div>
