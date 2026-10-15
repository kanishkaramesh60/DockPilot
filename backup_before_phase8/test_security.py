
from fastapi.testclient import TestClient
import main


client = TestClient(main.app)


def test_container_action_rejects_delete():
    response = client.post("/api/containers/fake-id/delete")

    assert response.status_code == 400


def test_compose_up_requires_confirmation():
    response = client.post(
        "/api/compose/up",
        json={
            "project_name": "security-test",
            "compose_yaml": (
                "services:\n"
                "  web:\n"
                "    image: nginx:alpine\n"
            ),
            "confirm": False,
        },
    )

    assert response.status_code == 400


def test_compose_stop_requires_confirmation():
    response = client.post(
        "/api/compose/security-test/stop",
        params={"confirm": "false"},
    )

    assert response.status_code == 400


def test_compose_start_requires_confirmation():
    response = client.post(
        "/api/compose/security-test/start",
        params={"confirm": "false"},
    )

    assert response.status_code == 400


def test_compose_rejects_invalid_project_name():
    response = client.post(
        "/api/compose/INVALID_NAME/stop",
        params={"confirm": "true"},
    )

    assert response.status_code == 400
