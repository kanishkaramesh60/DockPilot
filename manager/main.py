
from pathlib import Path
import re
import shutil
import subprocess
import tempfile

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from docker.errors import DockerException, NotFound, APIError

from autoscaling_service import get_service_metrics
from autoscaling_controller import autoscaling_controller

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
)


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


# --------------------------------------------------
# APPLICATION
# --------------------------------------------------

app = FastAPI(
    title="DockPilot API",
    description="Local Docker container management, monitoring, and Compose security",
    version="1.0.0",
)

COMPOSE_ROOT = Path(__file__).resolve().parent.parent / "compose_projects"


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
        "logs": docker_request(get_container_logs, container_id, tail),
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
# PHASE 8: COMPOSE SECURITY
# --------------------------------------------------

def _check_compose_security(compose_yaml: str):
    """
    Analyze Compose YAML before validation, saving, or starting.

    High-risk configurations are blocked.
    Lower-risk findings are returned as warnings.
    """

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
                    "Compose security validation blocked this configuration. "
                    "Fix the high-risk settings before saving or deploying."
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
    """
    Execute Docker Compose without using a shell.

    If compose_text is supplied, save it to the project's persistent
    Compose file before executing the command. Callers must validate
    security and Compose syntax before supplying new YAML.
    """

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
        compose_file.parent.mkdir(
            parents=True,
            exist_ok=True,
        )
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
    COMPOSE_ROOT.mkdir(
        parents=True,
        exist_ok=True,
    )

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
            projects.append(
                {
                    "name": folder.name,
                    "config_file": str(compose_file),
                    "saved": True,
                }
            )

    return projects


@app.get("/api/compose/saved")
def compose_saved():
    """List saved configurations without changing containers."""
    return _saved_compose_projects()


# --------------------------------------------------
# COMPOSE VALIDATION
# --------------------------------------------------

@app.post("/api/compose/validate")
def compose_validate(request: ComposeRequest):
    """
    Check security and Docker Compose syntax.
    Does not create, start, stop, or remove containers.
    """

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
            "Compose file is valid and passed high-risk security checks. "
            "No containers were created or changed."
        ),
        "security": security,
    }


# --------------------------------------------------
# SAVE COMPOSE YAML
# --------------------------------------------------

@app.post("/api/compose/save")
def compose_save(request: ComposeRequest):
    """
    Validate and save Compose YAML persistently.
    Does not deploy or change containers.
    """

    validation = compose_validate(request)

    compose_file = _compose_path(request.project_name)

    compose_file.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

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
    """
    Validate security and syntax before deployment.
    Explicit confirmation is required.
    """

    if not request.confirm:
        raise HTTPException(
            status_code=400,
            detail=(
                "Explicit confirmation is required before "
                "deploying a Compose project."
            ),
        )

    # Validate before persisting the submitted YAML.
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

    # Recheck the saved configuration before starting it.
    security = _check_compose_security(
        compose_file.read_text(encoding="utf-8")
    )

    output = _run_compose(
        project_name,
        ["up", "-d"],
    )

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

    # Docker Compose stop does not remove containers, networks, or volumes.
    output = _run_compose(
        project_name,
        ["stop"],
    )

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
# PHASE 9: READ-ONLY AUTOSCALING METRICS
# --------------------------------------------------

@app.get("/api/autoscaling/metrics")
def autoscaling_metrics(project_name: str, service_name: str):
    """Read real metrics for one explicitly selected Compose service."""
    if not re.fullmatch(r"[a-z0-9][a-z0-9_-]{0,62}", project_name):
        raise HTTPException(status_code=400, detail="Invalid Compose project name.")

    if not re.fullmatch(r"[a-z0-9][a-z0-9_-]{0,62}", service_name):
        raise HTTPException(status_code=400, detail="Invalid Compose service name.")

    compose_file = _compose_path(project_name)
    if not compose_file.is_file():
        raise HTTPException(status_code=404, detail="Saved Compose project not found.")

    try:
        return get_service_metrics(project_name, service_name)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        from docker.errors import DockerException

        if isinstance(exc, DockerException):
            raise HTTPException(status_code=503, detail=f"Docker Engine error: {exc}") from exc
        raise

@app.get("/api/autoscaling/status")
def autoscaling_status():
    return autoscaling_controller.get_status()


@app.post("/api/autoscaling/enable")
def enable_autoscaling(project_name: str, service_name: str):
    try:
        return autoscaling_controller.enable(project_name, service_name)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/autoscaling/disable")
def disable_autoscaling():
    return autoscaling_controller.disable()

# --------------------------------------------------
# DETECT REAL COMPOSE PROJECTS
# --------------------------------------------------

@app.get("/api/compose/projects")
def compose_projects():
    """List Compose projects detected from real Docker container labels."""
    from docker_service import get_docker_client

    client = None

    try:
        client = get_docker_client()
        projects = {}

        for container in client.containers.list(all=True):
            labels = container.labels or {}

            project = labels.get(
                "com.docker.compose.project"
            )

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

            entry["containers"].append(
                {
                    "name": container.name,
                    "id": container.short_id,
                    "status": container.status,
                    "service": labels.get(
                        "com.docker.compose.service",
                        "unknown",
                    ),
                }
            )

            if container.status == "running":
                entry["running"] += 1
            else:
                entry["stopped"] += 1

        return sorted(
            projects.values(),
            key=lambda item: item["name"],
        )

    finally:
        if client is not None:
            client.close()
