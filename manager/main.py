from pathlib import Path
import re
import subprocess
import shutil
import tempfile

from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel, Field
from fastapi.responses import FileResponse
from docker.errors import DockerException, NotFound, APIError

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

class PullImageRequest(BaseModel):
    image: str = Field(min_length=1, max_length=255)


class CreateContainerRequest(BaseModel):
    image: str = Field(min_length=1, max_length=255)
    name: str | None = Field(default=None, max_length=128)
    host_port: int | None = Field(default=None, ge=1, le=65535)
    container_port: int | None = Field(default=80, ge=1, le=65535)
    environment: list[str] = Field(default_factory=list, max_length=50)
    restart_policy: str = Field(default="no", pattern="^(no|on-failure|always|unless-stopped)$")


app = FastAPI(
    title="DockPilot API",
    description="Local Docker container management and monitoring API",
    version="1.0.0",
)


@app.get("/")
def home():
    dashboard_file = (
        Path(__file__).resolve().parent.parent / "dashboard" / "index.html"
    )
    return FileResponse(dashboard_file)


@app.get("/health")
def health():
    return {"status": "healthy"}


def docker_request(operation, *args):
    try:
        return operation(*args)
    except NotFound as exc:
        raise HTTPException(
            status_code=404, detail="Container not found in Docker Engine"
        ) from exc
    except APIError as exc:
        raise HTTPException(
            status_code=409, detail=f"Docker rejected the operation: {exc}"
        ) from exc
    except DockerException as exc:
        raise HTTPException(
            status_code=503, detail=f"Docker Engine error: {exc}"
        ) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


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


@app.get("/api/system/overview")
def system_overview():
    return docker_request(get_system_overview)


@app.get("/api/images")
def images():
    return docker_request(list_images)


@app.post("/api/images/pull")
def image_pull(request: PullImageRequest):
    return docker_request(pull_image, request.image)


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


@app.get("/api/networks")
def networks():
    return docker_request(list_networks)


@app.get("/api/volumes")
def volumes():
    return docker_request(list_volumes)


class ComposeRequest(BaseModel):
    project_name: str = Field(min_length=1, max_length=63, pattern="^[a-z0-9][a-z0-9_-]*$")
    compose_yaml: str = Field(min_length=1, max_length=100000)
    confirm: bool = False


COMPOSE_ROOT = Path(__file__).resolve().parent.parent / "compose_projects"


def _compose_path(project_name: str) -> Path:
    # project_name is constrained by Pydantic to lowercase letters, digits, _ and -.
    return COMPOSE_ROOT / project_name / "compose.yaml"


def _run_compose(project_name: str, args, compose_text: str | None = None):
    """Run Compose with a persistent, project-specific YAML file; never invokes a shell."""
    if not shutil.which("docker"):
        raise HTTPException(status_code=503, detail="Docker CLI was not found. Ensure Docker Desktop is installed and available in PATH.")
    compose_file = _compose_path(project_name)
    if compose_text is not None:
        compose_file.parent.mkdir(parents=True, exist_ok=True)
        compose_file.write_text(compose_text, encoding="utf-8")
    if not compose_file.is_file():
        raise HTTPException(status_code=404, detail=f"No saved Compose file exists for '{project_name}'. Save or deploy its YAML first.")
    command = ["docker", "compose", "-f", str(compose_file), "-p", project_name] + args
    try:
        result = subprocess.run(command, capture_output=True, text=True, timeout=180, check=False)
    except subprocess.TimeoutExpired as exc:
        raise HTTPException(status_code=504, detail="Docker Compose timed out after 180 seconds.") from exc
    if result.returncode != 0:
        message = (result.stderr or result.stdout or "Docker Compose failed.").strip()
        raise HTTPException(status_code=400, detail=message[-5000:])
    return result.stdout.strip()


def _saved_compose_projects():
    COMPOSE_ROOT.mkdir(parents=True, exist_ok=True)
    projects = []
    for folder in sorted(COMPOSE_ROOT.iterdir()):
        compose_file = folder / "compose.yaml"
        if folder.is_dir() and re.fullmatch(r"[a-z0-9][a-z0-9_-]{0,62}", folder.name) and compose_file.is_file():
            projects.append({"name": folder.name, "config_file": str(compose_file), "saved": True})
    return projects


@app.get("/api/compose/saved")
def compose_saved():
    """List saved persistent Compose configurations, whether or not containers are running."""
    return _saved_compose_projects()


@app.post("/api/compose/save")
def compose_save(request: ComposeRequest):
    """Validate and persist a Compose YAML file without creating or changing containers."""
    compose_validate(request)
    compose_file = _compose_path(request.project_name)
    compose_file.parent.mkdir(parents=True, exist_ok=True)
    compose_file.write_text(request.compose_yaml, encoding="utf-8")
    return {"success": True, "project_name": request.project_name,
            "config_file": str(compose_file),
            "message": "Compose YAML validated and saved persistently. No containers were created or changed."}


@app.post("/api/compose/validate")
def compose_validate(request: ComposeRequest):
    """Validate YAML in a temporary file; does not create or change containers."""
    if not shutil.which("docker"):
        raise HTTPException(status_code=503, detail="Docker CLI was not found. Ensure Docker Desktop is installed and available in PATH.")
    with tempfile.TemporaryDirectory(prefix="dockpilot-compose-validate-") as temp_dir:
        compose_file = Path(temp_dir) / "compose.yaml"
        compose_file.write_text(request.compose_yaml, encoding="utf-8")
        command = ["docker", "compose", "-f", str(compose_file), "-p", request.project_name, "config", "--quiet"]
        try:
            result = subprocess.run(command, capture_output=True, text=True, timeout=180, check=False)
        except subprocess.TimeoutExpired as exc:
            raise HTTPException(status_code=504, detail="Docker Compose validation timed out after 180 seconds.") from exc
        if result.returncode != 0:
            message = (result.stderr or result.stdout or "Docker Compose validation failed.").strip()
            raise HTTPException(status_code=400, detail=message[-5000:])
    return {"valid": True, "project_name": request.project_name, "message": "Compose file is valid. No containers were created or changed."}


@app.post("/api/compose/up")
def compose_up(request: ComposeRequest):
    """Persist validated YAML and start/update the named Compose project after explicit confirmation."""
    if not request.confirm:
        raise HTTPException(status_code=400, detail="Explicit confirmation is required before deploying a Compose project.")
    # Validate in a temp file before saving, so invalid YAML cannot overwrite a working saved file.
    compose_validate(request)
    output = _run_compose(request.project_name, ["up", "-d"], request.compose_yaml)
    return {"success": True, "project_name": request.project_name, "output": output or "Compose project started.",
            "config_file": str(_compose_path(request.project_name)),
            "warning": "Compose YAML was saved persistently. Deploying may create or update resources belonging to this project."}


@app.post("/api/compose/{project_name}/start")
def compose_start_saved(project_name: str, confirm: bool = False):
    if not re.fullmatch(r"[a-z0-9][a-z0-9_-]{0,62}", project_name):
        raise HTTPException(status_code=400, detail="Invalid Compose project name.")
    if not confirm:
        raise HTTPException(status_code=400, detail="Explicit confirmation is required before starting a project.")
    output = _run_compose(project_name, ["up", "-d"])
    return {"success": True, "project_name": project_name, "output": output or "Compose project started."}


@app.post("/api/compose/{project_name}/stop")
def compose_stop_saved(project_name: str, confirm: bool = False):
    if not re.fullmatch(r"[a-z0-9][a-z0-9_-]{0,62}", project_name):
        raise HTTPException(status_code=400, detail="Invalid Compose project name.")
    if not confirm:
        raise HTTPException(status_code=400, detail="Explicit confirmation is required before stopping a project.")
    # `stop` preserves containers, networks, and volumes; it does not remove resources.
    output = _run_compose(project_name, ["stop"])
    return {"success": True, "project_name": project_name, "output": output or "Compose project stopped.",
            "note": "Containers are stopped but not removed. Networks and volumes are preserved."}


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
            project = labels.get("com.docker.compose.project")
            if not project:
                continue
            entry = projects.setdefault(project, {"name": project, "containers": [], "running": 0, "stopped": 0})
            entry["containers"].append({"name": container.name, "id": container.short_id,
                                         "status": container.status,
                                         "service": labels.get("com.docker.compose.service", "unknown")})
            if container.status == "running":
                entry["running"] += 1
            else:
                entry["stopped"] += 1
        return sorted(projects.values(), key=lambda item: item["name"])
    finally:
        if client is not None:
            client.close()
