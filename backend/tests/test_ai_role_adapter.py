from decimal import Decimal

from app.fund.ai_role_adapter import AIRoleAdapter, ProviderConfig
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


def test_ai_role_adapter_retries_after_invalid_json_response():
    calls = {"count": 0}

    def _fake_post(url, json, headers, timeout):  # noqa: ANN001
        calls["count"] += 1
        if calls["count"] == 1:
            content = "summary: invalid-json-first-attempt"
        else:
            content = '{"summary":"Recovered JSON","findings":["Recovered"],"confidence":0.66,"citations":["src-retry"]}'
        return _FakeResponse({"choices": [{"message": {"content": content}}], "usage": {"call": calls["count"]}})

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
        require_success=True,
        http_post=_fake_post,
    )

    result = adapter.analyze_specialist(
        role="fundamental_analyst",
        symbol="MSFT",
        run_id="run-retry-1",
        payload={},
        context={},
        fallback_summary="fallback summary",
        fallback_findings=("fallback finding",),
        fallback_confidence=Decimal("0.50"),
        fallback_provenance=(ProvenanceRef(source_type="research", source_id="src-fallback"),),
    )

    assert result is not None
    assert result.summary == "Recovered JSON"
    assert float(result.confidence) == 0.66
    assert result.metadata["parse_retry_used"] is True
    assert calls["count"] == 2


def test_ai_role_adapter_parses_python_dict_style_output():
    def _fake_post(url, json, headers, timeout):  # noqa: ANN001
        return _FakeResponse(
            {
                "choices": [
                    {
                        "message": {
                            "content": "{'summary': 'Dict Style', 'findings': ['A', 'B'], 'confidence': 0.71, 'citations': ['src-1']}"
                        }
                    }
                ]
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
        require_success=True,
        http_post=_fake_post,
    )

    result = adapter.analyze_specialist(
        role="technical_analyst",
        symbol="AAPL",
        run_id="run-dict-style-1",
        payload={},
        context={},
        fallback_summary="fallback summary",
        fallback_findings=("fallback finding",),
        fallback_confidence=Decimal("0.50"),
        fallback_provenance=(ProvenanceRef(source_type="research", source_id="src-fallback"),),
    )

    assert result is not None
    assert result.summary == "Dict Style"
    assert result.findings == ("A", "B")
    assert float(result.confidence) == 0.71


def test_ai_role_adapter_degrades_to_fallback_after_double_invalid_json():
    def _fake_post(url, json, headers, timeout):  # noqa: ANN001
        return _FakeResponse({"choices": [{"message": {"content": "not-json-response"}}], "usage": {"call": 1}})

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
        require_success=True,
        http_post=_fake_post,
    )

    result = adapter.analyze_specialist(
        role="fundamental_analyst",
        symbol="SPY",
        run_id="run-fallback-1",
        payload={},
        context={},
        fallback_summary="fallback summary",
        fallback_findings=("fallback finding",),
        fallback_confidence=Decimal("0.55"),
        fallback_provenance=(ProvenanceRef(source_type="research", source_id="src-fallback"),),
    )

    assert result is not None
    assert result.summary == "fallback summary"
    assert result.findings == ("fallback finding",)
    assert float(result.confidence) == 0.55
    assert result.metadata["used"] is False
    assert result.metadata["degraded_reason"] == "invalid_json_response"


def test_ai_role_adapter_routes_by_role_and_fails_over_to_groq():
    calls: list[str] = []

    def _fake_post(url, json, headers=None, timeout=0):  # noqa: ANN001
        calls.append(url)
        if "generativelanguage.googleapis.com" in url:
            raise RuntimeError("http_error:429")
        return _FakeResponse(
            {
                "choices": [
                    {
                        "message": {
                            "content": '{"summary":"Fallback worked","findings":["Groq handled request"],"confidence":0.81,"citations":["src-1"]}'
                        }
                    }
                ],
                "usage": {"prompt_tokens": 10, "completion_tokens": 20},
            }
        )

    adapter = AIRoleAdapter(
        enabled=True,
        provider="router",
        base_url="",
        api_key=None,
        timeout_seconds=10,
        temperature=0.1,
        max_tokens=512,
        default_model="",
        role_models={},
        require_success=True,
        http_post=_fake_post,
        provider_configs={
            "gemini_flash_lite": ProviderConfig(
                name="gemini_flash_lite",
                provider_type="openai_compatible",
                base_url="https://generativelanguage.googleapis.com/v1beta/openai",
                api_key="gem-key",
                default_model="gemini-2.5-flash-lite",
                enabled=True,
            ),
            "groq": ProviderConfig(
                name="groq",
                provider_type="openai_compatible",
                base_url="https://api.groq.com/openai/v1",
                api_key="groq-key",
                default_model="gpt-oss-20b",
                enabled=True,
            ),
        },
        role_routes={"technical_analyst": ("gemini_flash_lite", "groq")},
        default_route=("gemini_flash_lite", "groq"),
    )

    result = adapter.analyze_specialist(
        role="technical_analyst",
        symbol="NVDA",
        run_id="run-router-1",
        payload={},
        context={},
        fallback_summary="fallback summary",
        fallback_findings=("fallback finding",),
        fallback_confidence=Decimal("0.50"),
        fallback_provenance=(ProvenanceRef(source_type="research", source_id="src-1"),),
    )

    assert result is not None
    assert result.provider == "groq"
    assert result.model == "gpt-oss-20b"
    assert result.metadata["fallback_used"] is True
    health = adapter.health()
    assert health["mode"] == "multi_vendor_router"
    assert health["providers"]["gemini_flash_lite"]["quota_state"] == "throttled"
    assert health["providers"]["groq"]["successes"] == 1
    assert health["role_runtime"]["technical_analyst"]["last_provider"] == "groq"
    assert health["role_runtime"]["technical_analyst"]["failover_count"] == 1
    assert len(calls) == 2
