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


def _compose_command(args, compose_text):
    """Run Docker Compose against a temporary file; never invokes a shell."""
    if not shutil.which("docker"):
        raise HTTPException(status_code=503, detail="Docker CLI was not found. Ensure Docker Desktop is installed and available in PATH.")
    with tempfile.TemporaryDirectory(prefix="dockpilot-compose-") as temp_dir:
        compose_file = Path(temp_dir) / "compose.yaml"
        compose_file.write_text(compose_text, encoding="utf-8")
        command = ["docker", "compose", "-f", str(compose_file)] + args
        try:
            result = subprocess.run(command, capture_output=True, text=True, timeout=180, check=False)
        except subprocess.TimeoutExpired as exc:
            raise HTTPException(status_code=504, detail="Docker Compose timed out after 180 seconds.") from exc
        if result.returncode != 0:
            message = (result.stderr or result.stdout or "Docker Compose failed.").strip()
            raise HTTPException(status_code=400, detail=message[-5000:])
        return result.stdout.strip()


@app.get("/api/compose/projects")
def compose_projects():
    """List Compose projects represented by real Docker container labels."""
    containers = docker_request(list_containers)
    client = None
    from docker_service import get_docker_client
    try:
        client = get_docker_client()
        projects = {}
        for container in client.containers.list(all=True):
            labels = container.labels or {}
            project = labels.get("com.docker.compose.project")
            if not project:
                continue
            entry = projects.setdefault(project, {"name": project, "containers": [], "running": 0, "stopped": 0})
            entry["containers"].append({"name": container.name, "id": container.short_id, "status": container.status, "service": labels.get("com.docker.compose.service", "unknown")})
            if container.status == "running":
                entry["running"] += 1
            else:
                entry["stopped"] += 1
        return sorted(projects.values(), key=lambda item: item["name"])
    finally:
        if client is not None:
            client.close()


@app.post("/api/compose/validate")
def compose_validate(request: ComposeRequest):
    """Validate YAML using Docker Compose without creating or changing containers."""
    output = _compose_command(["-p", request.project_name, "config", "--quiet"], request.compose_yaml)
    return {"valid": True, "project_name": request.project_name, "message": "Compose file is valid. No containers were created or changed."}


@app.post("/api/compose/up")
def compose_up(request: ComposeRequest):
    """Start a Compose project only after explicit confirmation."""
    if not request.confirm:
        raise HTTPException(status_code=400, detail="Explicit confirmation is required before deploying a Compose project.")
    # Validate first, then deploy. Compose may create/start/replace resources for this named project.
    _compose_command(["-p", request.project_name, "config", "--quiet"], request.compose_yaml)
    output = _compose_command(["-p", request.project_name, "up", "-d"], request.compose_yaml)
    return {"success": True, "project_name": request.project_name, "output": output or "Compose project started.", "warning": "Docker Compose may create or update resources belonging to this project."}
