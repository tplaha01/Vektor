import json

from fastapi import FastAPI
from fastapi.testclient import TestClient

import app.admin_research_routes as admin_routes


class _Settings:
    BROKER = "paper"
    ALPACA_FEED = "iex"


class _StubPipeline:
    def __init__(self, *, feed: str = "iex", providers: list[dict] | None = None, news_started: bool = True):
        self._feed = feed
        self._providers = providers if providers is not None else []
        self._news_started = news_started

    def status(self) -> dict:
        return {
            "mode": "live_stream_first",
            "running": True,
            "stream": {
                "subscribed": True,
                "started": True,
                "feed": self._feed,
            },
            "news_stream": {
                "enabled": True,
                "started": self._news_started,
                "disable_reason": None,
            },
            "provider_health": self._providers,
        }


class _StubBroker:
    order_history = [{"id": "order-1"}]

    def list_positions(self, _price_lookup):
        return [{"symbol": "AAPL", "qty": 2.0, "market_value": 300.0}]

    def get_cash(self):
        return 1000.0


def _client() -> TestClient:
    app = FastAPI()
    app.include_router(admin_routes.router)
    return TestClient(app)


def test_component_readiness_exposes_remaining_production_blockers(tmp_path, monkeypatch):
    feature_list = tmp_path / "feature_list.json"
    feature_list.write_text(
        json.dumps(
            [
                {"id": 1, "passes": True},
                {"id": 2, "passes": True},
            ]
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(admin_routes, "_FEATURE_LIST_PATH", feature_list)
    monkeypatch.setattr(admin_routes, "get_settings", lambda: _Settings())
    monkeypatch.setattr(admin_routes, "data_pipeline", _StubPipeline(feed="iex", providers=[]))
    monkeypatch.setattr(admin_routes, "broker", _StubBroker())

    response = _client().get("/api/admin/system/component-readiness")

    assert response.status_code == 200
    body = response.json()
    assert body["components"]["feature_inventory"]["status"] == "complete"
    assert body["production_ready"] is False
    blocker_ids = {item["id"] for item in body["remaining"]}
    assert "market_data_sip_entitlement" in blocker_ids
    assert "provider_redundancy" in blocker_ids
    assert body["components"]["paper_broker"]["positions_count"] == 1
    assert body["components"]["paper_broker"]["orders_count"] == 1


def test_component_readiness_can_report_ready_when_runtime_requirements_are_met(tmp_path, monkeypatch):
    feature_list = tmp_path / "feature_list.json"
    feature_list.write_text(json.dumps([{"id": 1, "passes": True}]), encoding="utf-8")
    monkeypatch.setattr(admin_routes, "_FEATURE_LIST_PATH", feature_list)
    monkeypatch.setattr(admin_routes, "get_settings", lambda: _Settings())
    monkeypatch.setattr(
        admin_routes,
        "data_pipeline",
        _StubPipeline(
            feed="sip",
            providers=[
                {"provider": "alpaca_sip", "status": "healthy"},
                {"provider": "polygon_rest", "status": "healthy"},
            ],
        ),
    )
    monkeypatch.setattr(admin_routes, "broker", _StubBroker())

    response = _client().get("/api/admin/system/component-readiness")

    assert response.status_code == 200
    body = response.json()
    assert body["production_ready"] is True
    assert body["remaining"] == []
    assert body["summary"]["high_blockers"] == 0
