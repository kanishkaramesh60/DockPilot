"""API tests for DockPilot's persisted security audit history endpoints."""

from fastapi.testclient import TestClient

from manager import main as main_module


client = TestClient(main_module.app)


def test_audit_history_returns_saved_summaries(monkeypatch):
    expected = [
        {
            "id": 12,
            "audited_at": "2026-10-21T10:00:00+00:00",
            "containers_scanned": 4,
            "containers_with_findings": 2,
            "critical": 1,
            "high": 0,
            "medium": 3,
            "low": 0,
            "total_findings": 4,
        }
    ]
    captured = {}

    def fake_list_security_audits(limit):
        captured["limit"] = limit
        return expected

    monkeypatch.setattr(
        main_module, "list_security_audits", fake_list_security_audits
    )

    response = client.get("/api/security/audit-history?limit=25")

    assert response.status_code == 200
    assert response.json() == {"items": expected}
    assert captured["limit"] == 25


def test_audit_history_rejects_limit_outside_allowed_range():
    assert client.get("/api/security/audit-history?limit=0").status_code == 422
    assert client.get("/api/security/audit-history?limit=501").status_code == 422


def test_audit_history_detail_returns_saved_report(monkeypatch):
    expected = {
        "id": 7,
        "audited_at": "2026-10-21T10:00:00+00:00",
        "report": {
            "containers_scanned": 1,
            "containers_with_findings": 1,
            "findings": [{"severity": "medium", "rule": "example-rule"}],
        },
    }
    captured = {}

    def fake_get_security_audit(audit_id):
        captured["audit_id"] = audit_id
        return expected if audit_id == 7 else None

    monkeypatch.setattr(main_module, "get_security_audit", fake_get_security_audit)

    response = client.get("/api/security/audit-history/7")

    assert response.status_code == 200
    assert response.json() == expected
    assert captured["audit_id"] == 7


def test_missing_audit_history_detail_returns_404(monkeypatch):
    monkeypatch.setattr(main_module, "get_security_audit", lambda audit_id: None)

    response = client.get("/api/security/audit-history/999999")

    assert response.status_code == 404
    assert response.json()["detail"] == "Security audit history item not found."


def test_container_audit_saves_report_and_returns_history_metadata(monkeypatch):
    report = {
        "containers_scanned": 2,
        "containers_with_findings": 1,
        "critical": 1,
        "high": 0,
        "medium": 2,
        "low": 0,
        "findings": [],
    }
    saved = {"id": 31, "audited_at": "2026-10-21T10:15:00+00:00"}
    captured = {}

    def fake_docker_request(operation):
        captured["operation"] = operation
        return report

    def fake_save_security_audit(value):
        captured["report"] = value
        return saved

    monkeypatch.setattr(main_module, "docker_request", fake_docker_request)
    monkeypatch.setattr(main_module, "save_security_audit", fake_save_security_audit)

    response = client.get("/api/security/container-audit")

    assert response.status_code == 200
    assert response.json() == {
        **report,
        "audit_id": saved["id"],
        "audited_at": saved["audited_at"],
    }
    assert captured["report"] == report
    assert callable(captured["operation"])
