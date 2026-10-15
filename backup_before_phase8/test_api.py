
from fastapi.testclient import TestClient
from unittest.mock import patch
import main


client = TestClient(main.app)


# 1. Health endpoint
def test_health_endpoint():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}


# 2. Dashboard route
def test_dashboard_route():
    response = client.get("/")
    assert response.status_code == 200
    assert "text/html" in response.headers.get("content-type", "")
    assert response.text.strip()


# 3. Reject invalid container action
def test_invalid_container_action():
    response = client.post("/api/containers/fake-id/delete")
    assert response.status_code == 400


# 4. Reject invalid container port
def test_invalid_container_port():
    response = client.post(
        "/api/containers",
        json={
            "image": "nginx:alpine",
            "host_port": 70000
        }
    )
    assert response.status_code == 422


# 5. Reject invalid Compose project name
def test_compose_invalid_project_name():
    response = client.post(
        "/api/compose/save",
        json={
            "project_name": "../outside",
            "compose_yaml": "services:\n  web:\n    image: nginx:alpine\n"
        }
    )
    assert response.status_code == 422


# 6. Require confirmation before Compose deployment
def test_compose_deployment_requires_confirmation():
    response = client.post(
        "/api/compose/up",
        json={
            "project_name": "unit-test-project",
            "compose_yaml": "services:\n  web:\n    image: nginx:alpine\n",
            "confirm": False
        }
    )
    assert response.status_code == 400


# 7. List Docker images
def test_list_images():
    with patch(
        "main.list_images",
        return_value=[{"id": "sha256:test123", "tags": ["nginx:alpine"]}]
    ):
        response = client.get("/api/images")

    assert response.status_code == 200
    assert isinstance(response.json(), list)


# 8. List Docker networks
def test_list_networks():
    with patch("main.list_networks", return_value=[]):
        response = client.get("/api/networks")

    assert response.status_code == 200
    assert isinstance(response.json(), list)


# 9. List Docker volumes
def test_list_volumes():
    with patch("main.list_volumes", return_value=[]):
        response = client.get("/api/volumes")

    assert response.status_code == 200
    assert isinstance(response.json(), list)


# 10. List saved Compose configurations
def test_list_saved_compose_projects():
    response = client.get("/api/compose/saved")

    assert response.status_code == 200
    assert isinstance(response.json(), list)


# 11. List deployed Compose projects

def test_list_compose_projects():
    response = client.get("/api/compose/projects")

    assert response.status_code == 200
    assert isinstance(response.json(), list)
