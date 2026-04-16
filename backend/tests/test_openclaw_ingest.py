from app.fund.audit_log import AuditLog
from app.fund.openclaw_ingest import OpenClawIngestService


def test_openclaw_rejects_unauthorized_and_trading_payloads():
    service = OpenClawIngestService(token="secret-token", log=AuditLog())

    unauthorized = service.ingest(
        kind="research_report",
        payload={"run_id": "run-1", "agent_id": "openclaw-1"},
        token="wrong-token",
    )
    assert unauthorized["accepted"] is False
    assert unauthorized["reason"] == "unauthorized"

    disallowed = service.ingest(
        kind="trade",
        payload={"run_id": "run-1", "agent_id": "openclaw-1", "symbol": "AAPL"},
        token="secret-token",
    )
    assert disallowed["accepted"] is False
    assert disallowed["reason"] == "trading_authority_not_allowed"

    allowed = service.ingest(
        kind="research_report",
        payload={"run_id": "run-1", "agent_id": "openclaw-1", "topic": "macro"},
        token="secret-token",
    )
    assert allowed["accepted"] is True
