
import concurrent.futures
import re
import shutil
import subprocess
import tempfile
from pathlib import Path
from time import monotonic

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse, PlainTextResponse
from pydantic import BaseModel, Field
from docker.errors import DockerException, NotFound, APIError

from compose_security import (
    ComposeSecurityError,
    analyze_compose_security,
)

from docker_service import (
    list_containers,
    get_container_details,
    perform_action,
    get_container_logs,
    get_container_stats,
    get_system_overview,
    list_images,
    pull_image,
    create_container,
    list_networks,
    list_volumes,
    audit_container_security,
    get_docker_client,
)

from container_health import (
    _inspect_containers,
    check_containers,
    get_recent_health_events,
)

from security_audit_history import (
    initialize_security_audit_history,
    save_security_audit,
    list_security_audits,
    get_security_audit,
)
from contextlib import asynccontextmanager
from metrics_collector import start_metrics_collector, stop_metrics_collector
from resilience_lab import (
    is_eligible_container,
    validate_experiment_target,
    save_experiment,
    get_experiment_history,
    utc_now,
)
from incident_engine import (
    initialize_incidents,
    scan_for_incidents,
    get_incidents,
)
from incident_recovery import (
    initialize_recovery,
    create_recommendation,
    execute_approved_recovery,
    get_recovery_history,
)
import threading
from metrics_history import (
    initialize_history,
    record_metrics,
    get_all_metric_history,
    get_metric_history,
)
from failure_predictor import analyze_all_containers
# --------------------------------------------------
# REQUEST MODELS
# --------------------------------------------------

class PullImageRequest(BaseModel):
    image: str = Field(min_length=1, max_length=255)


class CreateContainerRequest(BaseModel):
    image: str = Field(min_length=1, max_length=255)
    name: str | None = Field(default=None, max_length=128)
    host_port: int | None = Field(default=None, ge=1, le=65535)
    container_port: int | None = Field(default=80, ge=1, le=65535)
    environment: list[str] = Field(default_factory=list, max_length=50)
    restart_policy: str = Field(
        default="no",
        pattern="^(no|on-failure|always|unless-stopped)$",
    )


class ComposeRequest(BaseModel):
    project_name: str = Field(
        min_length=1,
        max_length=63,
        pattern="^[a-z0-9][a-z0-9_-]*$",
    )
    compose_yaml: str = Field(min_length=1, max_length=100000)
    confirm: bool = False


class ResilienceExperimentRequest(BaseModel):
    container_id: str = Field(min_length=1, max_length=128)
    confirm: bool = False

class IncidentRecoveryApproval(BaseModel):
    action_id: str = Field(min_length=36, max_length=36)
    approved: bool
    
# --------------------------------------------------
# APPLICATION
# --------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    start_metrics_collector()
    try:
        yield
    finally:
        stop_metrics_collector()
        
app = FastAPI(
    title="DockPilot API",
    description=(
        "Local Docker container management, monitoring, "
        "runtime security auditing, Compose security, "
        "and controlled resilience experiments."
    ),
    version="1.0.0",
    lifespan=lifespan,
)
initialize_history()
initialize_incidents()
initialize_recovery()

_metrics_history_lock = threading.Lock()

# --------------------------------------------------
# HISTORICAL DOCKER METRICS
# --------------------------------------------------

@app.get("/api/autoscaling/history/metrics")
def historical_metrics(
    project_name: str = Query(default="dockpilot"),
    service_name: str = Query(default="all"),
    limit: int = Query(default=100, ge=1, le=1000),
):
    """
    Collect current metrics from running Docker containers
    and return saved historical CPU and memory samples.

    This endpoint does not enable or control autoscaling.
    A sample is recorded when this endpoint is requested.
    """
    client = None

    try:
        client = get_docker_client()

        containers = client.containers.list(all=False)

        def _fetch_and_record(c):
            try:
                stats = c.stats(stream=False)
                cpu_stats = stats.get("cpu_stats", {})
                precpu_stats = stats.get("precpu_stats", {})
                cpu_usage = cpu_stats.get("cpu_usage", {})
                precpu_usage = precpu_stats.get("cpu_usage", {})

                cpu_delta = (
                    cpu_usage.get("total_usage", 0)
                    - precpu_usage.get("total_usage", 0)
                )
                system_delta = (
                    cpu_stats.get("system_cpu_usage", 0)
                    - precpu_stats.get("system_cpu_usage", 0)
                )
                online_cpus = (
                    cpu_stats.get("online_cpus")
                    or len(cpu_usage.get("percpu_usage", []) or [])
                    or 1
                )

                if system_delta > 0 and cpu_delta >= 0:
                    cpu_percent = (
                        cpu_delta / system_delta
                    ) * online_cpus * 100
                else:
                    cpu_percent = 0.0

                memory_stats = stats.get("memory_stats", {})
                memory_usage = memory_stats.get("usage", 0)
                memory_limit = memory_stats.get("limit", 0)
                memory_percent = (
                    memory_usage / memory_limit * 100
                    if memory_limit > 0
                    else 0.0
                )

                with _metrics_history_lock:
                    record_metrics(
                        project_name=project_name,
                        service_name=c.name,
                        cpu_percent=round(cpu_percent, 2),
                        memory_percent=round(memory_percent, 2),
                        running_replicas=1,
                    )
            except Exception:
                pass

        if containers:
            with concurrent.futures.ThreadPoolExecutor(max_workers=min(8, len(containers))) as executor:
                list(executor.map(_fetch_and_record, containers))

        # "all" returns samples for every container recorded under
        # this project name. A specific service filters by its name.
        if service_name.lower() == "all":
            items = get_all_metric_history(
                project_name=project_name,
                limit=limit,
            )
        else:
            items = get_metric_history(
                project_name=project_name,
                service_name=service_name,
                limit=limit,
            )

        return {"items": items}

    except DockerException as exc:
        raise HTTPException(
            status_code=503,
            detail=f"Could not collect Docker metrics: {exc}",
        ) from exc

    finally:
        if client is not None:
            client.close()


COMPOSE_ROOT = Path(__file__).resolve().parent.parent / "compose_projects"

# --------------------------------------------------
# PREDICTIVE CONTAINER FAILURE DETECTION
# --------------------------------------------------

@app.get("/api/predictions/container-failures")
def predict_container_failures(
    project_name: str = Query(default="dockpilot"),
    limit: int = Query(default=100, ge=3, le=1000),
):
    """
    Analyze historical Docker CPU and memory metrics
    to identify containers showing early warning signs.
    """

    metric_items = get_all_metric_history(
        project_name=project_name,
        limit=limit,
    )

    result = analyze_all_containers(metric_items)

    result["project_name"] = project_name

    return result

# --------------------------------------------------
# HEALTH MONITORING
# --------------------------------------------------

@app.get("/api/health")
def container_health_status():
    return check_containers(auto_recover=False)


@app.get("/api/health/events")
def container_health_events(
    limit: int = Query(default=100, ge=1, le=1000),
):
    return {"items": get_recent_health_events(limit=limit)}

@app.get("/api/incidents")
def api_get_incidents(
    limit: int = Query(default=100, ge=1, le=500)
):
    return {"items": get_incidents(limit=limit)}


@app.post("/api/incidents/scan")
def api_scan_incidents():
    try:
        items = scan_for_incidents()
        return {
            "message": "Incident scan completed",
            "detected_count": len(items),
            "items": items,
        }
    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail=f"Incident scan failed: {exc}"
        )

@app.post("/api/incidents/{incident_id}/recommendation")
def api_incident_recommendation(incident_id: int):
    try:
        return create_recommendation(incident_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail=f"Recommendation failed: {exc}"
        )


@app.post("/api/incidents/recovery/approve")
def api_approve_incident_recovery(request: IncidentRecoveryApproval):
    if not request.approved:
        raise HTTPException(
            status_code=400,
            detail="Explicit approval is required."
        )

    try:
        return execute_approved_recovery(request.action_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail=f"Recovery failed: {exc}"
        )


@app.get("/api/incidents/recovery/history")
def api_incident_recovery_history(
    limit: int = Query(default=100, ge=1, le=500)
):
    return {"items": get_recovery_history(limit=limit)}
# --------------------------------------------------
# RESILIENCE LAB
# --------------------------------------------------

@app.get("/api/resilience/eligible")
def resilience_eligible_containers():
    """List running containers explicitly opted into experiments."""
    client = None

    try:
        client = get_docker_client()
        eligible = []

        for container in client.containers.list(all=True):
            container.reload()

            if (
                is_eligible_container(container)
                and container.status == "running"
            ):
                eligible.append({
                    "id": container.short_id,
                    "name": container.name,
                    "status": container.status,
                    "eligible": True,
                })

        return {"items": eligible}

    except DockerException as exc:
        raise HTTPException(
            status_code=503,
            detail=f"Could not query Docker Engine: {exc}",
        ) from exc

    finally:
        if client is not None:
            client.close()


@app.get("/api/resilience/history")
def resilience_experiment_history(
    limit: int = Query(default=50, ge=1, le=500),
):
    """Return recent Resilience Lab experiment records."""
    return {"items": get_experiment_history(limit)}


@app.post("/api/resilience/experiments")
def run_resilience_experiment(
    request: ResilienceExperimentRequest,
):
    """
    Stop and restart an explicitly opted-in container.

    Use only disposable test containers. This operation can interrupt
    service. Runtime recovery does not prove application health.
    """
    if not request.confirm:
        raise HTTPException(
            status_code=400,
            detail=(
                "Explicit confirmation is required before "
                "running an experiment."
            ),
        )

    client = None
    start_clock = None

    record = {
        "container_id": request.container_id,
        "container_name": "",
        "started_at": utc_now(),
        "finished_at": None,
        "outcome": "failed",
        "recovery_verified": False,
        "recovery_seconds": None,
        "message": "",
    }

    try:
        client = get_docker_client()
        container = client.containers.get(request.container_id)
        container.reload()

        target = validate_experiment_target(container)

        record["container_id"] = target["container_id"]
        record["container_name"] = target["container_name"]

        # Start measuring immediately before the disruptive operation.
        start_clock = monotonic()
        container.stop(timeout=5)

        # Always attempt a restart after a successful stop.
        try:
            container.start()
            container.reload()

            if container.status != "running":
                raise RuntimeError(
                    "Docker did not report the container as running "
                    "after restart."
                )

            record["outcome"] = "recovered"
            record["recovery_verified"] = True
            record["recovery_seconds"] = round(
                monotonic() - start_clock, 3
            )
            record["message"] = (
                "Container returned to running state. "
                "Application health has not been verified."
            )

        except Exception as recovery_error:
            record["message"] = (
                "Recovery could not be verified. Check the container "
                "manually. Details: "
                f"{recovery_error}"
            )
            raise HTTPException(
                status_code=503,
                detail=record["message"],
            ) from recovery_error

        record["finished_at"] = utc_now()
        save_experiment(record)
        return record

    except HTTPException:
        if record["finished_at"] is None:
            record["finished_at"] = utc_now()
            if not record["message"]:
                record["message"] = "Experiment was not completed."
            save_experiment(record)
        raise

    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc

    except NotFound as exc:
        raise HTTPException(
            status_code=404,
            detail="Experiment target was not found in Docker Engine.",
        ) from exc

    except DockerException as exc:
        record["finished_at"] = utc_now()
        record["message"] = f"Docker operation failed: {exc}"
        save_experiment(record)

        raise HTTPException(
            status_code=503,
            detail=record["message"],
        ) from exc

    finally:
        if client is not None:
            client.close()


# --------------------------------------------------
# HOME AND HEALTH
# --------------------------------------------------

@app.get("/")
def home():
    dashboard_file = (
        Path(__file__).resolve().parent.parent
        / "dashboard"
        / "index.html"
    )
    return FileResponse(dashboard_file)


@app.get("/health")
def health():
    return {"status": "healthy"}


@app.get("/metrics", response_class=PlainTextResponse)
def metrics():
    """
    Prometheus metrics endpoint exposing real-time container health and monitoring telemetry.
    """
    lines = [
        "# HELP dockpilot_container_health_status Health status of Docker containers (1=healthy, 0=unhealthy, -1=no healthcheck)",
        "# TYPE dockpilot_container_health_status gauge"
    ]
    try:
        containers = _inspect_containers()
        for c in containers:
            c_name = c.get("name", "")
            c_id = c.get("id", "")
            health_str = c.get("health", "not_configured")
            if health_str == "healthy":
                val = 1
            elif health_str == "unhealthy":
                val = 0
            else:
                val = -1
            lines.append(f'dockpilot_container_health_status{{container_name="{c_name}",container_id="{c_id}",health="{health_str}"}} {val}')
    except Exception as exc:
        lines.append(f"# Error collecting container health metrics: {exc}")
    lines.append("")
    return "\n".join(lines)


# --------------------------------------------------
# DOCKER ERROR HANDLING
# --------------------------------------------------

def docker_request(operation, *args):
    try:
        return operation(*args)

    except NotFound as exc:
        raise HTTPException(
            status_code=404,
            detail="Container not found in Docker Engine",
        ) from exc

    except APIError as exc:
        raise HTTPException(
            status_code=409,
            detail=f"Docker rejected the operation: {exc}",
        ) from exc

    except DockerException as exc:
        raise HTTPException(
            status_code=503,
            detail=f"Docker Engine error: {exc}",
        ) from exc

    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc


# --------------------------------------------------
# CONTAINER MANAGEMENT
# --------------------------------------------------

@app.get("/api/containers")
def containers():
    return docker_request(list_containers)


@app.get("/api/containers/{container_id}")
def container_details(container_id: str):
    return docker_request(get_container_details, container_id)


@app.get("/api/containers/{container_id}/logs")
def container_logs(
    container_id: str,
    tail: int = Query(default=100, ge=1, le=1000),
):
    return {
        "container_id": container_id,
        "logs": docker_request(
            get_container_logs, container_id, tail
        ),
    }


@app.get("/api/containers/{container_id}/stats")
def container_stats(container_id: str):
    return docker_request(get_container_stats, container_id)


@app.post("/api/containers/{container_id}/{action}")
def container_action(container_id: str, action: str):
    if action not in {"start", "stop", "restart"}:
        raise HTTPException(
            status_code=400,
            detail="Action must be start, stop, or restart",
        )

    return docker_request(perform_action, container_id, action)


# --------------------------------------------------
# SYSTEM MONITORING
# --------------------------------------------------

@app.get("/api/system/overview")
def system_overview():
    return docker_request(get_system_overview)


# --------------------------------------------------
# RUNTIME CONTAINER SECURITY AUDIT
# --------------------------------------------------

@app.get("/api/security/container-audit")
def container_security_audit():
    """Run a read-only audit and save it for historical comparison."""
    report = docker_request(audit_container_security)
    saved = save_security_audit(report)

    return {
        **report,
        "audit_id": saved["id"],
        "audited_at": saved["audited_at"],
    }


# --------------------------------------------------
# SECURITY AUDIT HISTORY
# --------------------------------------------------

initialize_security_audit_history()


@app.get("/api/security/audit-history")
def security_audit_history(
    limit: int = Query(default=50, ge=1, le=500),
):
    """List saved audit summaries, newest first."""
    return {"items": list_security_audits(limit=limit)}


@app.get("/api/security/audit-history/{audit_id}")
def security_audit_history_detail(audit_id: int):
    """Read a saved audit without rerunning it."""
    saved = get_security_audit(audit_id)

    if saved is None:
        raise HTTPException(
            status_code=404,
            detail="Security audit history item not found.",
        )

    return saved


# --------------------------------------------------
# IMAGE MANAGEMENT
# --------------------------------------------------

@app.get("/api/images")
def images():
    return docker_request(list_images)


@app.post("/api/images/pull")
def image_pull(request: PullImageRequest):
    return docker_request(pull_image, request.image)


# --------------------------------------------------
# CREATE CONTAINER
# --------------------------------------------------

@app.post("/api/containers")
def container_create(request: CreateContainerRequest):
    return docker_request(
        create_container,
        request.image,
        request.name,
        request.host_port,
        request.container_port,
        request.environment,
        request.restart_policy,
    )


# --------------------------------------------------
# NETWORKS AND VOLUMES
# --------------------------------------------------

@app.get("/api/networks")
def networks():
    return docker_request(list_networks)


@app.get("/api/volumes")
def volumes():
    return docker_request(list_volumes)


# --------------------------------------------------
# COMPOSE PATH HELPERS
# --------------------------------------------------

def _compose_path(project_name: str) -> Path:
    if not re.fullmatch(
        r"[a-z0-9][a-z0-9_-]{0,62}",
        project_name,
    ):
        raise HTTPException(
            status_code=400,
            detail="Invalid Compose project name.",
        )

    return COMPOSE_ROOT / project_name / "compose.yaml"


# --------------------------------------------------
# COMPOSE SECURITY
# --------------------------------------------------

def _check_compose_security(compose_yaml: str):
    """Analyze Compose YAML before validation, saving, or starting."""
    try:
        report = analyze_compose_security(compose_yaml)

    except ComposeSecurityError as exc:
        raise HTTPException(
            status_code=400,
            detail=f"Compose security analysis failed: {exc}",
        ) from exc

    if report.get("blocked"):
        raise HTTPException(
            status_code=400,
            detail={
                "message": (
                    "Compose security validation blocked this "
                    "configuration. Fix high-risk settings before "
                    "saving or deploying."
                ),
                "security": report,
            },
        )

    return report


# --------------------------------------------------
# RUN DOCKER COMPOSE
# --------------------------------------------------

def _run_compose(
    project_name: str,
    args,
    compose_text: str | None = None,
):
    """Execute Docker Compose without invoking a shell."""
    if not shutil.which("docker"):
        raise HTTPException(
            status_code=503,
            detail=(
                "Docker CLI was not found. Ensure Docker Desktop "
                "is installed and available in PATH."
            ),
        )

    compose_file = _compose_path(project_name)

    if compose_text is not None:
        compose_file.parent.mkdir(parents=True, exist_ok=True)
        compose_file.write_text(
            compose_text,
            encoding="utf-8",
        )

    if not compose_file.is_file():
        raise HTTPException(
            status_code=404,
            detail=(
                f"No saved Compose file exists for '{project_name}'. "
                "Save or deploy its YAML first."
            ),
        )

    command = [
        "docker",
        "compose",
        "-f",
        str(compose_file),
        "-p",
        project_name,
    ] + args

    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=180,
            check=False,
        )

    except subprocess.TimeoutExpired as exc:
        raise HTTPException(
            status_code=504,
            detail="Docker Compose timed out after 180 seconds.",
        ) from exc

    if result.returncode != 0:
        message = (
            result.stderr
            or result.stdout
            or "Docker Compose failed."
        ).strip()

        raise HTTPException(
            status_code=400,
            detail=message[-5000:],
        )

    return result.stdout.strip()


# --------------------------------------------------
# LIST SAVED COMPOSE PROJECTS
# --------------------------------------------------

def _saved_compose_projects():
    COMPOSE_ROOT.mkdir(parents=True, exist_ok=True)
    projects = []

    for folder in sorted(COMPOSE_ROOT.iterdir()):
        compose_file = folder / "compose.yaml"

        if (
            folder.is_dir()
            and re.fullmatch(
                r"[a-z0-9][a-z0-9_-]{0,62}",
                folder.name,
            )
            and compose_file.is_file()
        ):
            projects.append({
                "name": folder.name,
                "config_file": str(compose_file),
                "saved": True,
            })

    return projects


@app.get("/api/compose/saved")
def compose_saved():
    return _saved_compose_projects()


# --------------------------------------------------
# COMPOSE VALIDATION
# --------------------------------------------------

@app.post("/api/compose/validate")
def compose_validate(request: ComposeRequest):
    """Validate security and syntax without deploying."""
    security = _check_compose_security(request.compose_yaml)

    if not shutil.which("docker"):
        raise HTTPException(
            status_code=503,
            detail=(
                "Docker CLI was not found. Ensure Docker Desktop "
                "is installed and available in PATH."
            ),
        )

    with tempfile.TemporaryDirectory(
        prefix="dockpilot-compose-validate-"
    ) as temp_dir:
        compose_file = Path(temp_dir) / "compose.yaml"
        compose_file.write_text(
            request.compose_yaml,
            encoding="utf-8",
        )

        command = [
            "docker",
            "compose",
            "-f",
            str(compose_file),
            "-p",
            request.project_name,
            "config",
            "--quiet",
        ]

        try:
            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=180,
                check=False,
            )

        except subprocess.TimeoutExpired as exc:
            raise HTTPException(
                status_code=504,
                detail="Docker Compose validation timed out after 180 seconds.",
            ) from exc

        if result.returncode != 0:
            message = (
                result.stderr
                or result.stdout
                or "Docker Compose validation failed."
            ).strip()

            raise HTTPException(
                status_code=400,
                detail=message[-5000:],
            )

    return {
        "valid": True,
        "project_name": request.project_name,
        "message": (
            "Compose file is valid and passed high-risk security "
            "checks. No containers were created or changed."
        ),
        "security": security,
    }


# --------------------------------------------------
# SAVE COMPOSE YAML
# --------------------------------------------------

@app.post("/api/compose/save")
def compose_save(request: ComposeRequest):
    validation = compose_validate(request)
    compose_file = _compose_path(request.project_name)

    compose_file.parent.mkdir(parents=True, exist_ok=True)
    compose_file.write_text(
        request.compose_yaml,
        encoding="utf-8",
    )

    return {
        "success": True,
        "project_name": request.project_name,
        "config_file": str(compose_file),
        "message": (
            "Compose YAML validated and saved persistently. "
            "No containers were created or changed."
        ),
        "security": validation["security"],
    }


# --------------------------------------------------
# DEPLOY COMPOSE PROJECT
# --------------------------------------------------

@app.post("/api/compose/up")
def compose_up(request: ComposeRequest):
    if not request.confirm:
        raise HTTPException(
            status_code=400,
            detail=(
                "Explicit confirmation is required before "
                "deploying a Compose project."
            ),
        )

    validation = compose_validate(request)

    output = _run_compose(
        request.project_name,
        ["up", "-d"],
        request.compose_yaml,
    )

    return {
        "success": True,
        "project_name": request.project_name,
        "output": output or "Compose project started.",
        "config_file": str(_compose_path(request.project_name)),
        "warning": (
            "Compose YAML was saved persistently. Deploying may create "
            "or update resources belonging to this project."
        ),
        "security": validation["security"],
    }


# --------------------------------------------------
# START A SAVED COMPOSE PROJECT
# --------------------------------------------------

@app.post("/api/compose/{project_name}/start")
def compose_start_saved(
    project_name: str,
    confirm: bool = False,
):
    if not re.fullmatch(
        r"[a-z0-9][a-z0-9_-]{0,62}",
        project_name,
    ):
        raise HTTPException(
            status_code=400,
            detail="Invalid Compose project name.",
        )

    if not confirm:
        raise HTTPException(
            status_code=400,
            detail=(
                "Explicit confirmation is required before "
                "starting a project."
            ),
        )

    compose_file = _compose_path(project_name)

    if not compose_file.is_file():
        raise HTTPException(
            status_code=404,
            detail=f"No saved Compose file exists for '{project_name}'.",
        )

    security = _check_compose_security(
        compose_file.read_text(encoding="utf-8")
    )

    output = _run_compose(project_name, ["up", "-d"])

    return {
        "success": True,
        "project_name": project_name,
        "output": output or "Compose project started.",
        "security": security,
    }


# --------------------------------------------------
# STOP A SAVED COMPOSE PROJECT
# --------------------------------------------------

@app.post("/api/compose/{project_name}/stop")
def compose_stop_saved(
    project_name: str,
    confirm: bool = False,
):
    if not re.fullmatch(
        r"[a-z0-9][a-z0-9_-]{0,62}",
        project_name,
    ):
        raise HTTPException(
            status_code=400,
            detail="Invalid Compose project name.",
        )

    if not confirm:
        raise HTTPException(
            status_code=400,
            detail=(
                "Explicit confirmation is required before "
                "stopping a project."
            ),
        )

    output = _run_compose(project_name, ["stop"])

    return {
        "success": True,
        "project_name": project_name,
        "output": output or "Compose project stopped.",
        "note": (
            "Containers are stopped but not removed. "
            "Networks and volumes are preserved."
        ),
    }


# --------------------------------------------------
# DETECT REAL COMPOSE PROJECTS
# --------------------------------------------------

@app.get("/api/compose/projects")
def compose_projects():
    """List Compose projects using real Docker container labels."""
    client = None

    try:
        client = get_docker_client()
        projects = {}

        for container in client.containers.list(all=True):
            labels = container.labels or {}
            project = labels.get("com.docker.compose.project")

            if not project:
                continue

            entry = projects.setdefault(
                project,
                {
                    "name": project,
                    "containers": [],
                    "running": 0,
                    "stopped": 0,
                },
            )

            entry["containers"].append({
                "name": container.name,
                "id": container.short_id,
                "status": container.status,
                "service": labels.get(
                    "com.docker.compose.service",
                    "unknown",
                ),
            })

            if container.status == "running":
                entry["running"] += 1
            else:
                entry["stopped"] += 1

        return sorted(
            projects.values(),
            key=lambda item: item["name"],
        )

    except DockerException as exc:
        raise HTTPException(
            status_code=503,
            detail=f"Could not query Docker Engine: {exc}",
        ) from exc

    finally:
        if client is not None:
            client.close()


# --------------------------------------------------
# UNIFIED DASHBOARD MONITORING & SETTINGS ENDPOINTS
# --------------------------------------------------

import json
import os
import platform
import sys
import urllib.error
import urllib.request
import psutil

PROMETHEUS_URL = os.getenv("PROMETHEUS_URL", "http://localhost:9090")
ALERTMANAGER_URL = os.getenv("ALERTMANAGER_URL", "http://localhost:9093")
GRAFANA_URL = os.getenv("GRAFANA_URL", "http://localhost:3000")
CADVISOR_URL = os.getenv("CADVISOR_URL", "http://localhost:8085")


def _http_get_json(url: str, timeout: float = 2.0):
    """Safely fetch JSON from a local service with quick timeout."""
    try:
        req = urllib.request.Request(url, headers={"Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            if resp.status == 200:
                return json.loads(resp.read().decode("utf-8"))
    except Exception:
        return None
    return None


def _check_service_health(url: str, timeout: float = 1.5):
    """Check if an HTTP service endpoint is reachable."""
    t0 = monotonic()
    try:
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            latency_ms = round((monotonic() - t0) * 1000, 1)
            return {
                "status": "healthy" if resp.status < 400 else "degraded",
                "http_code": resp.status,
                "latency_ms": latency_ms,
            }
    except Exception as e:
        latency_ms = round((monotonic() - t0) * 1000, 1)
        return {
            "status": "unreachable",
            "http_code": None,
            "latency_ms": latency_ms,
            "error": str(e),
        }


@app.get("/api/monitoring/services")
def get_monitoring_services():
    """Return live status of all monitoring stack services."""
    services = [
        {
            "name": "DockPilot Backend",
            "service": "dockpilot",
            "port": 8001,
            "url": "http://localhost:8001",
            "status": "healthy",
            "role": "Management API, Exporter & Dashboard",
        },
        {
            "name": "Prometheus",
            "service": "prometheus",
            "port": 9090,
            "url": PROMETHEUS_URL,
            "container": "dockpilot-prometheus",
            **_check_service_health(f"{PROMETHEUS_URL}/-/healthy"),
            "role": "Time-Series Metrics & Alert Evaluation Engine",
        },
        {
            "name": "Grafana",
            "service": "grafana",
            "port": 3000,
            "url": GRAFANA_URL,
            "container": "dockpilot-grafana",
            **_check_service_health(f"{GRAFANA_URL}/api/health"),
            "role": "Centralized 39-Panel Observability Dashboard",
        },
        {
            "name": "Alertmanager",
            "service": "alertmanager",
            "port": 9093,
            "url": ALERTMANAGER_URL,
            "container": "dockpilot-alertmanager",
            **_check_service_health(f"{ALERTMANAGER_URL}/-/healthy"),
            "role": "Alert Deduplication, Grouping & Email Routing",
        },
        {
            "name": "cAdvisor",
            "service": "cadvisor",
            "port": 8085,
            "url": CADVISOR_URL,
            "container": "dockpilot-cadvisor",
            **_check_service_health(f"{CADVISOR_URL}/api/v1.3/machine"),
            "role": "Container Resource & Cgroup Telemetry",
        },
        {
            "name": "Node Exporter",
            "service": "node-exporter",
            "port": 9100,
            "url": "Internal (dockpilot-monitoring)",
            "container": "dockpilot-node-exporter",
            "status": "healthy",
            "role": "Host Machine Hardware & OS Telemetry",
        },
    ]
    return {"services": services}


@app.get("/api/monitoring/prometheus/targets")
def get_prometheus_targets():
    """Return live scrape targets from Prometheus API."""
    data = _http_get_json(f"{PROMETHEUS_URL}/api/v1/targets")
    if data and data.get("status") == "success":
        active_targets = data.get("data", {}).get("activeTargets", [])
        return {
            "status": "success",
            "count": len(active_targets),
            "targets": [
                {
                    "scrapePool": t.get("scrapePool", ""),
                    "health": t.get("health", "unknown").upper(),
                    "scrapeUrl": t.get("scrapeUrl", ""),
                    "lastScrape": t.get("lastScrape", ""),
                    "lastScrapeDuration": round(float(t.get("lastScrapeDuration", 0)) * 1000, 1),
                    "lastError": t.get("lastError", ""),
                }
                for t in active_targets
            ],
        }
    return {
        "status": "unavailable",
        "count": 6,
        "targets": [
            {"scrapePool": "prometheus", "health": "UNKNOWN", "scrapeUrl": "http://prometheus:9090/metrics"},
            {"scrapePool": "cadvisor", "health": "UNKNOWN", "scrapeUrl": "http://cadvisor:8080/metrics"},
            {"scrapePool": "node-exporter", "health": "UNKNOWN", "scrapeUrl": "http://node-exporter:9100/metrics"},
            {"scrapePool": "grafana", "health": "UNKNOWN", "scrapeUrl": "http://grafana:3000/metrics"},
            {"scrapePool": "dockpilot", "health": "UNKNOWN", "scrapeUrl": "http://host.docker.internal:8001/metrics"},
            {"scrapePool": "alertmanager", "health": "UNKNOWN", "scrapeUrl": "http://alertmanager:9093/metrics"},
        ],
    }


@app.get("/api/monitoring/prometheus/rules")
def get_prometheus_rules():
    """Return active alert rules and evaluation states from Prometheus."""
    data = _http_get_json(f"{PROMETHEUS_URL}/api/v1/rules")
    if data and data.get("status") == "success":
        groups = data.get("data", {}).get("groups", [])
        parsed_rules = []
        for g in groups:
            group_name = g.get("name", "")
            for r in g.get("rules", []):
                labels = r.get("labels", {})
                annotations = r.get("annotations", {})
                parsed_rules.append({
                    "group": group_name,
                    "name": r.get("name", ""),
                    "query": r.get("query", ""),
                    "duration": r.get("duration", 0),
                    "health": r.get("health", "ok"),
                    "state": r.get("state", "inactive"),
                    "severity": labels.get("severity", "info"),
                    "summary": annotations.get("summary", ""),
                    "description": annotations.get("description", ""),
                    "lastEvaluation": r.get("lastEvaluation", ""),
                    "evaluationTime": round(float(r.get("evaluationTime", 0)) * 1000, 2),
                })
        return {"status": "success", "count": len(parsed_rules), "rules": parsed_rules}
    return {"status": "unavailable", "count": 0, "rules": []}


@app.get("/api/monitoring/alertmanager/alerts")
def get_alertmanager_alerts():
    """Return active alerts from Alertmanager."""
    data = _http_get_json(f"{ALERTMANAGER_URL}/api/v2/alerts")
    alerts = data if isinstance(data, list) else []
    critical_alerts = []
    warning_alerts = []
    info_alerts = []

    for a in alerts:
        labels = a.get("labels", {})
        annotations = a.get("annotations", {})
        status = a.get("status", {})
        item = {
            "fingerprint": a.get("fingerprint", ""),
            "alertname": labels.get("alertname", "UnknownAlert"),
            "severity": labels.get("severity", "info"),
            "instance": labels.get("instance", ""),
            "job": labels.get("job", ""),
            "state": status.get("state", "active"),
            "summary": annotations.get("summary", ""),
            "description": annotations.get("description", ""),
            "startsAt": a.get("startsAt", ""),
            "generatorURL": a.get("generatorURL", ""),
        }
        sev = item["severity"].lower()
        if sev == "critical":
            critical_alerts.append(item)
        elif sev == "warning":
            warning_alerts.append(item)
        else:
            info_alerts.append(item)

    return {
        "total": len(alerts),
        "critical_count": len(critical_alerts),
        "warning_count": len(warning_alerts),
        "critical": critical_alerts,
        "warning": warning_alerts,
        "other": info_alerts,
    }


@app.get("/api/monitoring/alertmanager/status")
def get_alertmanager_status():
    """Return Alertmanager status, cluster state, and receiver routing."""
    data = _http_get_json(f"{ALERTMANAGER_URL}/api/v2/status")
    if data:
        config = data.get("config", {})
        route = config.get("route", {})
        receivers = [r.get("name") for r in config.get("receivers", []) if r.get("name")]
        return {
            "status": "healthy",
            "cluster_status": data.get("cluster", {}).get("status", "unknown"),
            "version": data.get("versionInfo", {}).get("version", "unknown"),
            "uptime": data.get("uptime", ""),
            "default_receiver": route.get("receiver", "dockpilot-default-receiver"),
            "receivers": receivers or ["dockpilot-default-receiver", "dockpilot-critical-receiver", "dockpilot-warning-receiver"],
        }
    return {
        "status": "unreachable",
        "cluster_status": "unknown",
        "version": "unknown",
        "uptime": "",
        "default_receiver": "dockpilot-default-receiver",
        "receivers": ["dockpilot-default-receiver", "dockpilot-critical-receiver", "dockpilot-warning-receiver"],
    }


@app.get("/api/monitoring/overview")
def get_unified_overview():
    """Consolidate overview metrics across Docker, Host, Services, Targets, Alerts, and Incidents."""
    from concurrent.futures import ThreadPoolExecutor

    cpu_percent = psutil.cpu_percent(interval=None)
    vm = psutil.virtual_memory()
    du = psutil.disk_usage(".")
    net = psutil.net_io_counters()

    host_stats = {
        "cpu_percent": round(cpu_percent, 1),
        "memory_percent": round(vm.percent, 1),
        "memory_used_gb": round(vm.used / (1024**3), 2),
        "memory_total_gb": round(vm.total / (1024**3), 2),
        "disk_percent": round(du.percent, 1),
        "disk_used_gb": round(du.used / (1024**3), 2),
        "disk_total_gb": round(du.total / (1024**3), 2),
        "net_sent_mb": round(net.bytes_sent / (1024**2), 1),
        "net_recv_mb": round(net.bytes_recv / (1024**2), 1),
    }

    # Execute Docker queries and HTTP service checks in parallel
    with ThreadPoolExecutor(max_workers=8) as ex:
        f_containers = ex.submit(list_containers)
        f_health = ex.submit(check_containers, auto_recover=False)
        f_targets = ex.submit(get_prometheus_targets)
        f_alerts = ex.submit(get_alertmanager_alerts)
        f_prom_h = ex.submit(_check_service_health, f"{PROMETHEUS_URL}/-/healthy")
        f_graf_h = ex.submit(_check_service_health, f"{GRAFANA_URL}/api/health")
        f_am_h = ex.submit(_check_service_health, f"{ALERTMANAGER_URL}/-/healthy")
        f_cad_h = ex.submit(_check_service_health, f"{CADVISOR_URL}/api/v1.3/machine")

        containers = f_containers.result()
        health_status = f_health.result()
        targets_data = f_targets.result()
        alerts_data = f_alerts.result()
        prom_h = f_prom_h.result()
        graf_h = f_graf_h.result()
        am_h = f_am_h.result()
        cad_h = f_cad_h.result()

    total_containers = len(containers)
    running_containers = sum(1 for c in containers if c.get("status") == "running")
    stopped_containers = total_containers - running_containers
    unhealthy_containers = len(health_status.get("stopped_or_unhealthy", []))

    services_summary = {
        "prometheus": prom_h,
        "grafana": graf_h,
        "alertmanager": am_h,
        "cadvisor": cad_h,
        "dockpilot": {"status": "healthy", "latency_ms": 0.1},
    }

    up_targets = sum(1 for t in targets_data.get("targets", []) if t.get("health") == "UP")
    recent_incidents = get_incidents(limit=5)
    recent_events = get_recent_health_events(limit=5)

    return {
        "host": host_stats,
        "containers": {
            "total": total_containers,
            "running": running_containers,
            "stopped": stopped_containers,
            "unhealthy": unhealthy_containers,
        },
        "services": services_summary,
        "prometheus_targets": {
            "total": targets_data.get("count", 6),
            "up": up_targets,
            "targets": targets_data.get("targets", []),
        },
        "alerts": {
            "total": alerts_data.get("total", 0),
            "critical_count": alerts_data.get("critical_count", 0),
            "warning_count": alerts_data.get("warning_count", 0),
            "critical": alerts_data.get("critical", []),
            "warning": alerts_data.get("warning", []),
        },
        "recent_incidents": recent_incidents,
        "recent_events": recent_events,
    }


@app.get("/api/system/settings")
def get_system_settings():
    """Return runtime configuration, storage paths, and masked environment settings."""
    root_dir = Path(__file__).resolve().parent.parent
    db_file = root_dir / "data" / "dockpilot_history.db"
    db_size = db_file.stat().st_size if db_file.exists() else 0

    env_file = root_dir / ".env"
    smtp_info = {
        "configured": False,
        "smarthost": "smtp.gmail.com:587",
        "from": "dockpilot-alerts@example.com",
        "critical_receiver": "devops-critical@example.com",
        "warning_receiver": "devops-warning@example.com",
        "tls_required": True,
    }
    if env_file.exists():
        try:
            for line in env_file.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if "=" in line:
                    k, v = line.split("=", 1)
                    k, v = k.strip(), v.strip()
                    if k == "SMTP_SMARTHOST":
                        smtp_info["smarthost"] = v
                    elif k == "SMTP_FROM":
                        smtp_info["from"] = v
                    elif k == "ALERT_RECEIVER_CRITICAL_EMAIL":
                        smtp_info["critical_receiver"] = v
                    elif k == "ALERT_RECEIVER_WARNING_EMAIL":
                        smtp_info["warning_receiver"] = v
                    elif k == "SMTP_REQUIRE_TLS":
                        smtp_info["tls_required"] = (v.lower() == "true")
                    elif k == "SMTP_AUTH_PASSWORD" and v and v != "your-app-password":
                        smtp_info["configured"] = True
        except Exception:
            pass

    return {
        "version": "1.0.0",
        "platform": platform.platform(),
        "python_version": sys.version.split()[0],
        "backend_port": 8001,
        "ports": {
            "backend": 8001,
            "prometheus": 9090,
            "grafana": 3000,
            "alertmanager": 9093,
            "cadvisor": 8085,
            "node_exporter": 9100,
        },
        "storage": {
            "root_path": str(root_dir),
            "db_path": str(db_file),
            "db_size_bytes": db_size,
            "volumes": [
                "dockpilot_prometheus_data",
                "dockpilot_grafana_data",
                "dockpilot_alertmanager_data",
            ],
        },
        "smtp": smtp_info,
        "grafana_embedding": {
            "enabled": True,
            "dashboard_uid": "dockpilot-monitoring",
            "kiosk_url": f"{GRAFANA_URL}/d/dockpilot-monitoring?kiosk",
        },
    }

