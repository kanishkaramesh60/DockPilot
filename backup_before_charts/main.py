from pathlib import Path

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse
from docker.errors import DockerException, NotFound, APIError

from docker_service import (
    list_containers,
    get_container_details,
    perform_action,
    get_container_logs,
    get_container_stats,
)

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
