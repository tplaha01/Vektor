from fastapi import FastAPI
from fastapi.testclient import TestClient

import app.admin_research_routes as admin_routes


class _Mapped:
    def __init__(self, payload):
        self._payload = payload

    def model_dump(self, mode="json"):  # noqa: ARG002
        return dict(self._payload)


def _client():
    app = FastAPI()
    app.include_router(admin_routes.router)
    return TestClient(app)


def test_research_ideas_list_detail_and_archive(monkeypatch):
    reports = [
        {
            "report_id": "report-1",
            "run_id": "run-1",
            "agent_id": "macro_analyst",
            "created_at": "2026-05-20T00:00:00Z",
            "title": "Fed Pivot Watch",
            "summary": "Fed rate pause thesis",
            "findings": ["Rates cool"],
            "confidence": 0.72,
            "asset_universe": ["TLT"],
            "provenance": [],
        },
        {
            "report_id": "report-2",
            "run_id": "run-2",
            "agent_id": "technical_analyst",
            "created_at": "2026-05-19T00:00:00Z",
            "title": "Momentum Breakout",
            "summary": "Technical setup",
            "findings": ["Breakout pattern"],
            "confidence": 0.35,
            "asset_universe": ["NVDA"],
            "provenance": [],
        },
    ]

    monkeypatch.setattr(admin_routes.firm_orchestrator, "list_recent_research_reports", lambda limit=80: reports[:limit])
    monkeypatch.setattr(
        admin_routes.firm_orchestrator,
        "get_research_report",
        lambda report_id: next((item for item in reports if item["report_id"] == report_id), None),
    )
    monkeypatch.setattr(admin_routes, "_map_live_report", lambda payload, task_history_cache=None: _Mapped(payload))
    monkeypatch.setattr(admin_routes, "_record_runtime_control_event", lambda **kwargs: {})  # noqa: ARG005

    client = _client()

    list_response = client.get("/api/admin/research/ideas")
    assert list_response.status_code == 200
    ideas = list_response.json()["ideas"]
    assert len(ideas) == 2
    assert ideas[0]["idea_id"] == "report-1"
    assert ideas[0]["type"] == "MACRO"

    detail_response = client.get("/api/admin/research/ideas/report-1")
    assert detail_response.status_code == 200
    detail = detail_response.json()
    assert detail["report_id"] == "report-1"
    assert detail["source"] == "AGENT_DISCOVERY"

    archive_response = client.put(
        "/api/admin/research/ideas/report-1",
        json={"status": "ARCHIVED", "reason": "manual archive"},
    )
    assert archive_response.status_code == 200

    list_archived = client.get("/api/admin/research/ideas?status=ARCHIVED")
    assert list_archived.status_code == 200
    archived_rows = list_archived.json()["ideas"]
    assert len(archived_rows) == 1
    assert archived_rows[0]["idea_id"] == "report-1"


def test_create_admin_thesis_from_idea(monkeypatch):
    report = {
        "report_id": "report-9",
        "run_id": "run-9",
        "summary": "Create tactical thesis",
    }
    monkeypatch.setattr(admin_routes.firm_orchestrator, "get_research_report", lambda report_id: report if report_id == "report-9" else None)
    monkeypatch.setattr(
        admin_routes.firm_orchestrator,
        "create_thesis",
        lambda **kwargs: {"thesis_id": "thesis-9", "run_id": kwargs["run_id"], "report_ids": kwargs["report_ids"]},
    )

    client = _client()
    response = client.post(
        "/api/admin/theses",
        json={
            "report_id": "report-9",
            "run_id": "run-9",
            "agent_id": "ceo",
            "sleeve": "tactical",
            "statement": "Promote to tactical thesis",
            "conviction": 0.68,
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "created"
    assert body["thesis"]["thesis_id"] == "thesis-9"
