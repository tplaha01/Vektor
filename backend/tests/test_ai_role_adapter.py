from decimal import Decimal

from app.fund.ai_role_adapter import AIRoleAdapter
from app.fund.contracts import ProvenanceRef


class _FakeResponse:
    def __init__(self, payload: dict, status_code: int = 200) -> None:
        self._payload = payload
        self.status_code = status_code

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise RuntimeError(f"http_error:{self.status_code}")

    def json(self) -> dict:
        return self._payload


def test_ai_role_adapter_openai_compatible_parses_structured_output():
    def _fake_post(url, json, headers, timeout):  # noqa: ANN001
        assert url.endswith("/chat/completions")
        assert "messages" in json
        return _FakeResponse(
            {
                "choices": [
                    {
                        "message": {
                            "content": '{"summary":"AI technical summary","findings":["Momentum rising","Risk tightening"],"confidence":0.77,"citations":["src-1"],"trade_setup":{"bias":"long"}}'
                        }
                    }
                ],
                "usage": {"prompt_tokens": 120, "completion_tokens": 80},
            }
        )

    adapter = AIRoleAdapter(
        enabled=True,
        provider="openai_compatible",
        base_url="http://mock-llm/v1",
        api_key="test-key",
        timeout_seconds=10,
        temperature=0.1,
        max_tokens=512,
        default_model="gpt-test",
        role_models={},
        require_success=False,
        http_post=_fake_post,
    )
    result = adapter.analyze_specialist(
        role="technical_analyst",
        symbol="AAPL",
        run_id="run-1",
        payload={},
        context={"seed": "data"},
        fallback_summary="fallback summary",
        fallback_findings=("fallback finding",),
        fallback_confidence=Decimal("0.50"),
        fallback_provenance=(ProvenanceRef(source_type="research", source_id="src-fallback"),),
    )
    assert result is not None
    assert result.summary == "AI technical summary"
    assert result.findings[0] == "Momentum rising"
    assert float(result.confidence) == 0.77
    assert result.citations == ("src-1",)
    assert result.metadata["used"] is True


def test_ai_role_adapter_disabled_returns_none():
    adapter = AIRoleAdapter(
        enabled=False,
        provider="openai_compatible",
        base_url="http://mock-llm/v1",
        api_key="test-key",
        timeout_seconds=10,
        temperature=0.1,
        max_tokens=512,
        default_model="gpt-test",
        role_models={},
        require_success=False,
    )
    result = adapter.analyze_specialist(
        role="technical_analyst",
        symbol="AAPL",
        run_id="run-1",
        payload={},
        context={},
        fallback_summary="fallback summary",
        fallback_findings=("fallback finding",),
        fallback_confidence=Decimal("0.50"),
        fallback_provenance=(ProvenanceRef(source_type="research", source_id="src-fallback"),),
    )
    assert result is None
