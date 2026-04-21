from __future__ import annotations

import ast
import json
import re
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from time import monotonic, time
from typing import Any, Callable

import requests

from app.config import get_settings
from app.fund.contracts import ProvenanceRef


AnalystRole = (
    "technical_analyst",
    "fundamental_analyst",
    "sentiment_analyst",
    "ml_timeseries_analyst",
    "insight_researcher",
    "hedge_fund_researcher",
)

_ROUTED_ROLE_ALIASES: dict[str, str] = {
    "composite_synthesis": "fund_manager",
    "research_judge": "fund_manager",
}


def _utc_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _utc_iso_from_ts(value: float | None) -> str | None:
    if not value:
        return None
    try:
        return datetime.fromtimestamp(float(value), timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    except Exception:
        return None


class TemporaryProviderCapacityError(RuntimeError):
    def __init__(
        self,
        message: str,
        *,
        retry_after_seconds: float,
        reasons: list[str] | None = None,
        providers: list[str] | None = None,
    ) -> None:
        super().__init__(message)
        self.retry_after_seconds = max(1.0, float(retry_after_seconds))
        self.reasons = list(reasons or [])
        self.providers = list(providers or [])


def _clamp(value: float, lower: float, upper: float) -> float:
    return max(lower, min(upper, value))


def _safe_decimal(value: Any, fallback: Decimal) -> Decimal:
    try:
        return Decimal(str(value))
    except Exception:
        return fallback


def _extract_json_object(text: str) -> dict[str, Any] | None:
    raw = str(text or "").strip()
    if not raw:
        return None
    if raw.startswith("```"):
        raw = re.sub(r"^```[a-zA-Z0-9_-]*\s*", "", raw, flags=re.IGNORECASE)
        raw = re.sub(r"\s*```$", "", raw)
        raw = raw.strip()
    try:
        loaded = json.loads(raw)
        if isinstance(loaded, dict):
            return loaded
    except Exception:
        pass

    match = re.search(r"\{[\s\S]*\}", raw)
    if not match:
        try:
            repaired = ast.literal_eval(raw)
            return repaired if isinstance(repaired, dict) else None
        except Exception:
            return None
    try:
        loaded = json.loads(match.group(0))
        return loaded if isinstance(loaded, dict) else None
    except Exception:
        try:
            repaired = ast.literal_eval(match.group(0))
            return repaired if isinstance(repaired, dict) else None
        except Exception:
            return None


def _normalize_findings(value: Any, fallback: tuple[str, ...]) -> tuple[str, ...]:
    rows: list[str] = []
    if isinstance(value, list):
        rows = [str(item).strip() for item in value if str(item).strip()]
    elif isinstance(value, str) and value.strip():
        rows = [value.strip()]
    rows = list(dict.fromkeys(rows))
    if rows:
        return tuple(rows[:12])
    return fallback


def _normalize_citations(value: Any) -> tuple[str, ...]:
    rows: list[str] = []
    if isinstance(value, list):
        rows = [str(item).strip() for item in value if str(item).strip()]
    elif isinstance(value, str) and value.strip():
        rows = [value.strip()]
    return tuple(dict.fromkeys(rows))[:12]


def _normalize_tags(value: Any) -> tuple[str, ...]:
    rows: list[str] = []
    if isinstance(value, list):
        rows = [str(item).strip().lower() for item in value if str(item).strip()]
    elif isinstance(value, str) and value.strip():
        rows = [item.strip().lower() for item in re.split(r"[,\n]+", value) if item.strip()]
    cleaned: list[str] = []
    seen: set[str] = set()
    for item in rows:
        token = re.sub(r"[^a-z0-9\-_ ]", "", item).strip()
        if not token or token in seen:
            continue
        seen.add(token)
        cleaned.append(token)
    return tuple(cleaned[:12])


def _parse_http_status(exc: Exception) -> int | None:
    response = getattr(exc, "response", None)
    status_code = getattr(response, "status_code", None)
    if isinstance(status_code, int):
        return status_code
    match = re.search(r"(?:http_error:|status(?:_code)?[=: ]|HTTP )(?P<code>\d{3})", str(exc), re.IGNORECASE)
    if not match:
        return None
    try:
        return int(match.group("code"))
    except Exception:
        return None


def _quota_state(*, api_key_configured: bool, status_code: int | None, had_error: bool) -> str:
    if not api_key_configured:
        return "missing_api_key"
    if status_code == 429:
        return "throttled"
    if status_code in {401, 403}:
        return "auth_error"
    if had_error:
        return "error"
    return "available"


def _parse_route(value: Any) -> tuple[str, ...]:
    if value is None:
        return tuple()
    if isinstance(value, (list, tuple, set)):
        items = [str(item).strip() for item in value if str(item).strip()]
    else:
        items = [item.strip() for item in str(value).split(",") if item.strip()]
    out: list[str] = []
    seen: set[str] = set()
    for item in items:
        normalized = item.lower()
        if normalized in seen:
            continue
        seen.add(normalized)
        out.append(normalized)
    return tuple(out)


@dataclass(frozen=True)
class AIRoleAnalysis:
    summary: str
    findings: tuple[str, ...]
    confidence: Decimal
    citations: tuple[str, ...]
    metadata: dict[str, Any]
    provider: str
    model: str
    raw_text: str


@dataclass(frozen=True)
class AIBlogDraft:
    title: str
    excerpt: str
    content_markdown: str
    tags: tuple[str, ...]
    image_query: str
    metadata: dict[str, Any]
    provider: str
    model: str
    raw_text: str


@dataclass(frozen=True)
class ProviderConfig:
    name: str
    provider_type: str
    base_url: str
    api_key: str | None
    default_model: str
    enabled: bool = True
    max_concurrency: int = 1
    cooldown_seconds: float = 45.0
    transient_cooldown_seconds: float = 8.0
    requests_per_window: int = 0
    tokens_per_window: int = 0
    window_seconds: float = 60.0


@dataclass
class ProviderRuntimeState:
    attempts: int = 0
    successes: int = 0
    failures: int = 0
    failovers: int = 0
    in_flight: int = 0
    last_model: str | None = None
    last_error: str | None = None
    last_status_code: int | None = None
    last_success_at: str | None = None
    last_failure_at: str | None = None
    quota_state: str = "unknown"
    cooldown_until: float = 0.0
    window_started_at: float = 0.0
    window_reset_at: float = 0.0
    requests_in_window: int = 0
    estimated_tokens_in_window: int = 0

    def to_dict(self, *, config: ProviderConfig) -> dict[str, Any]:
        remaining = max(0.0, float(self.cooldown_until or 0.0) - time())
        window_remaining = max(0.0, float(self.window_reset_at or 0.0) - time())
        return {
            "name": config.name,
            "provider_type": config.provider_type,
            "enabled": config.enabled,
            "base_url": config.base_url,
            "api_key_configured": bool(config.api_key),
            "default_model": config.default_model,
            "max_concurrency": max(1, int(config.max_concurrency)),
            "in_flight": self.in_flight,
            "attempts": self.attempts,
            "successes": self.successes,
            "failures": self.failures,
            "failovers": self.failovers,
            "last_model": self.last_model,
            "last_error": self.last_error,
            "last_status_code": self.last_status_code,
            "last_success_at": self.last_success_at,
            "last_failure_at": self.last_failure_at,
            "quota_state": self.quota_state,
            "cooldown_until": _utc_iso_from_ts(self.cooldown_until),
            "cooldown_remaining_seconds": round(remaining, 2),
            "requests_per_window": max(0, int(config.requests_per_window)),
            "tokens_per_window": max(0, int(config.tokens_per_window)),
            "window_seconds": round(max(1.0, float(config.window_seconds)), 2),
            "window_started_at": _utc_iso_from_ts(self.window_started_at),
            "window_reset_at": _utc_iso_from_ts(self.window_reset_at),
            "window_remaining_seconds": round(window_remaining, 2),
            "requests_in_window": int(self.requests_in_window),
            "estimated_tokens_in_window": int(self.estimated_tokens_in_window),
        }


@dataclass
class RunBudgetState:
    run_id: str
    requests_used: int = 0
    estimated_tokens_used: int = 0
    window_started_at: float = 0.0
    window_reset_at: float = 0.0
    last_role: str | None = None
    last_provider: str | None = None
    last_attempt_at: str | None = None

    def to_dict(self, *, requests_limit: int, tokens_limit: int, window_seconds: float) -> dict[str, Any]:
        remaining = max(0.0, float(self.window_reset_at or 0.0) - time())
        return {
            "run_id": self.run_id,
            "requests_limit": max(0, int(requests_limit)),
            "tokens_limit": max(0, int(tokens_limit)),
            "window_seconds": round(max(1.0, float(window_seconds)), 2),
            "requests_used": int(self.requests_used),
            "estimated_tokens_used": int(self.estimated_tokens_used),
            "window_started_at": _utc_iso_from_ts(self.window_started_at),
            "window_reset_at": _utc_iso_from_ts(self.window_reset_at),
            "window_remaining_seconds": round(remaining, 2),
            "last_role": self.last_role,
            "last_provider": self.last_provider,
            "last_attempt_at": self.last_attempt_at,
        }


@dataclass
class RoleRuntimeState:
    route: tuple[str, ...] = field(default_factory=tuple)
    last_provider: str | None = None
    last_model: str | None = None
    last_error: str | None = None
    last_attempt_at: str | None = None
    last_success_at: str | None = None
    failover_count: int = 0
    fallback_used: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "route": list(self.route),
            "last_provider": self.last_provider,
            "last_model": self.last_model,
            "last_error": self.last_error,
            "last_attempt_at": self.last_attempt_at,
            "last_success_at": self.last_success_at,
            "failover_count": self.failover_count,
            "fallback_used": self.fallback_used,
        }


class AIRoleAdapter:
    def __init__(
        self,
        *,
        enabled: bool,
        provider: str,
        base_url: str,
        api_key: str | None,
        timeout_seconds: int,
        temperature: float,
        max_tokens: int,
        default_model: str,
        role_models: dict[str, str],
        require_success: bool,
        http_post: Callable[..., Any] | None = None,
        provider_configs: dict[str, ProviderConfig] | None = None,
        role_routes: dict[str, tuple[str, ...]] | None = None,
        default_route: tuple[str, ...] | None = None,
        gateway: dict[str, Any] | None = None,
        run_request_envelope: int = 0,
        run_tokens_envelope: int = 0,
        run_window_seconds: float = 120.0,
    ) -> None:
        self._enabled = bool(enabled)
        self._provider = str(provider or "openai_compatible").strip().lower()
        self._base_url = str(base_url or "").strip().rstrip("/")
        self._api_key = str(api_key).strip() if api_key else None
        self._timeout_seconds = max(5, int(timeout_seconds))
        self._temperature = float(_clamp(float(temperature), 0.0, 1.0))
        self._max_tokens = max(128, int(max_tokens))
        self._default_model = str(default_model or "").strip()
        self._role_models = dict(role_models)
        self._require_success = bool(require_success)
        self._http_post = http_post or requests.post
        self._last_error: str | None = None
        self._gateway = dict(gateway or {})

        self._router_enabled = bool(provider_configs)
        self._provider_configs = dict(provider_configs or {})
        self._provider_runtime: dict[str, ProviderRuntimeState] = {
            name: ProviderRuntimeState() for name in self._provider_configs
        }
        self._provider_limiters: dict[str, threading.BoundedSemaphore] = {
            name: threading.BoundedSemaphore(max(1, int(config.max_concurrency)))
            for name, config in self._provider_configs.items()
        }
        self._provider_state_lock = threading.RLock()
        self._role_routes = {str(role).strip(): tuple(route) for role, route in (role_routes or {}).items()}
        self._default_route = tuple(default_route or ())
        self._role_runtime: dict[str, RoleRuntimeState] = {}
        self._run_request_envelope = max(0, int(run_request_envelope))
        self._run_tokens_envelope = max(0, int(run_tokens_envelope))
        self._run_window_seconds = max(1.0, float(run_window_seconds))
        self._run_budget_runtime: dict[str, RunBudgetState] = {}
        self._run_budget_lock = threading.RLock()

        if not self._router_enabled:
            self._default_route = tuple()

    def health(self) -> dict[str, Any]:
        if not self._router_enabled:
            return {
                "enabled": self._enabled,
                "mode": "single_provider",
                "provider": self._provider,
                "base_url": self._base_url,
                "api_key_configured": bool(self._api_key),
                "default_model": self._default_model,
                "role_models": dict(self._role_models),
                "require_success": self._require_success,
                "last_error": self._last_error,
                "gateway": dict(self._gateway),
            }

        with self._run_budget_lock:
            active_runs = [
                state.to_dict(
                    requests_limit=self._run_request_envelope,
                    tokens_limit=self._run_tokens_envelope,
                    window_seconds=self._run_window_seconds,
                )
                for _, state in sorted(
                    self._run_budget_runtime.items(),
                    key=lambda item: item[1].window_reset_at,
                    reverse=True,
                )[:12]
            ]

        return {
            "enabled": self._enabled,
            "mode": "multi_vendor_router",
            "provider": "router",
            "base_url": None,
            "api_key_configured": any(bool(config.api_key) for config in self._provider_configs.values()),
            "default_model": None,
            "role_models": dict(self._role_models),
            "require_success": self._require_success,
            "last_error": self._last_error,
            "default_route": list(self._default_route),
            "role_routes": {role: list(route) for role, route in sorted(self._role_routes.items())},
            "gateway": dict(self._gateway),
            "providers": {
                name: self._provider_runtime[name].to_dict(config=config)
                for name, config in sorted(self._provider_configs.items())
            },
            "scheduler": {
                "run_request_envelope": self._run_request_envelope,
                "run_tokens_envelope": self._run_tokens_envelope,
                "run_window_seconds": round(self._run_window_seconds, 2),
                "active_runs": active_runs,
            },
            "role_runtime": {
                role: state.to_dict()
                for role, state in sorted(self._role_runtime.items())
            },
        }

    def analyze_specialist(
        self,
        *,
        role: str,
        symbol: str,
        run_id: str,
        payload: dict[str, Any],
        context: dict[str, Any],
        fallback_summary: str,
        fallback_findings: tuple[str, ...],
        fallback_confidence: Decimal,
        fallback_provenance: tuple[ProvenanceRef, ...],
    ) -> AIRoleAnalysis | None:
        if not self._enabled:
            return None

        route_context = self._route_context_for_role(role)
        if not route_context["model"]:
            self._last_error = "missing_model"
            if self._require_success:
                raise RuntimeError("ai_role_adapter_missing_model")
            return None

        source_ids = [ref.source_id for ref in fallback_provenance]
        system_prompt = self._system_prompt_for_role(role)
        user_payload = {
            "role": role,
            "symbol": symbol,
            "run_id": run_id,
            "task_payload": dict(payload),
            "context": dict(context),
            "fallback_summary": fallback_summary,
            "fallback_findings": list(fallback_findings),
            "fallback_confidence": float(fallback_confidence),
            "source_ids": source_ids,
            "output_schema": {
                "summary": "string",
                "findings": ["string"],
                "confidence": "float_0_to_1",
                "citations": ["source_id_string"],
                "trade_setup": {
                    "bias": "long|short|neutral",
                    "entry": "string",
                    "exit": "string",
                    "risk_controls": "string",
                    "time_horizon": "string",
                },
                "risk_flags": ["string"],
            },
        }
        user_prompt = (
            "Return only JSON matching output_schema. No markdown, no prose outside JSON.\n"
            "Use only the supplied context and source_ids. Do not invent catalysts, prices, dates, filings, or citations.\n"
            "If evidence is thin, say so explicitly in findings and reduce confidence.\n"
            + json.dumps(user_payload, sort_keys=True, default=str)
        )

        started = monotonic()
        try:
            response_meta = self._invoke_model(
                role=role,
                run_id=run_id,
                model=route_context["model"],
                system_prompt=system_prompt,
                user_prompt=user_prompt,
            )
            raw_text = str(response_meta["text"])
            usage = response_meta["usage"]
            provider_name = str(response_meta["provider"])
            provider_type = str(response_meta["provider_type"])
            resolved_model = str(response_meta["model"])
            duration_ms = int((monotonic() - started) * 1000)
            parsed = _extract_json_object(raw_text)
            parse_retry_used = False
            if not parsed:
                parse_retry_used = True
                retry_prompt = (
                    f"{user_prompt}\n"
                    "Previous response was invalid JSON. Return exactly one strict JSON object with double-quoted keys."
                )
                retry_meta = self._invoke_model(
                    role=role,
                    run_id=run_id,
                    model=resolved_model,
                    system_prompt=system_prompt,
                    user_prompt=retry_prompt,
                    preferred_provider=provider_name,
                )
                parsed = _extract_json_object(str(retry_meta["text"]))
                if parsed:
                    raw_text = str(retry_meta["text"])
                    usage = {"initial": usage, "retry": retry_meta["usage"]}
                    provider_name = str(retry_meta["provider"])
                    provider_type = str(retry_meta["provider_type"])
                    resolved_model = str(retry_meta["model"])
                else:
                    self._last_error = "invalid_json_response"
                    return AIRoleAnalysis(
                        summary=fallback_summary,
                        findings=fallback_findings,
                        confidence=fallback_confidence.quantize(Decimal("0.01")),
                        citations=tuple(dict.fromkeys(source_ids))[:12],
                        metadata={
                            "used": False,
                            "provider": provider_name,
                            "provider_type": provider_type,
                            "model": resolved_model,
                            "duration_ms": duration_ms,
                            "usage": usage,
                            "route": response_meta["route"],
                            "fallback_used": response_meta["fallback_used"],
                            "parse_retry_used": parse_retry_used,
                            "degraded_reason": "invalid_json_response",
                            "trade_setup": {},
                            "risk_flags": ["invalid_json_response"],
                        },
                        provider=provider_name,
                        model=resolved_model,
                        raw_text=raw_text,
                    )

            summary = str(parsed.get("summary") or "").strip() or fallback_summary
            findings = _normalize_findings(parsed.get("findings"), fallback_findings)
            confidence = _safe_decimal(parsed.get("confidence"), fallback_confidence)
            confidence = Decimal(str(_clamp(float(confidence), 0.0, 1.0))).quantize(Decimal("0.01"))
            citations = _normalize_citations(parsed.get("citations"))
            trade_setup = parsed.get("trade_setup") if isinstance(parsed.get("trade_setup"), dict) else {}
            risk_flags = parsed.get("risk_flags") if isinstance(parsed.get("risk_flags"), list) else []

            self._last_error = None
            return AIRoleAnalysis(
                summary=summary,
                findings=findings,
                confidence=confidence,
                citations=citations,
                metadata={
                    "used": True,
                    "provider": provider_name,
                    "provider_type": provider_type,
                    "model": resolved_model,
                    "duration_ms": duration_ms,
                    "usage": usage,
                    "route": response_meta["route"],
                    "fallback_used": response_meta["fallback_used"],
                    "parse_retry_used": parse_retry_used,
                    "trade_setup": trade_setup,
                    "risk_flags": [str(item) for item in risk_flags][:12],
                },
                provider=provider_name,
                model=resolved_model,
                raw_text=raw_text,
            )
        except Exception as exc:
            self._last_error = str(exc)
            if self._require_success:
                raise
            return None

    def draft_blog_post(
        self,
        *,
        run_id: str,
        symbol: str,
        command: str,
        report: dict[str, Any],
        fallback_title: str,
        fallback_excerpt: str,
        fallback_content_markdown: str,
        fallback_tags: tuple[str, ...],
        fallback_image_query: str,
    ) -> AIBlogDraft | None:
        if not self._enabled:
            return None

        route_context = self._route_context_for_role("blog_writer")
        if not route_context["model"]:
            self._last_error = "missing_model"
            if self._require_success:
                raise RuntimeError("ai_role_adapter_missing_model")
            return None

        system_prompt = (
            "You are Vektor's principal editorial analyst for AI, fintech, and hedge-fund research. "
            "Write specific, high-signal content for serious operators. "
            "Avoid generic motivation, filler, broad beginner advice, and vague futurism. "
            "Every section must connect directly to the supplied report facts. "
            "The writing must be easy to read: short paragraphs, explicit transitions, and a clear blend of technical explanation and layman explanation."
        )
        user_payload = {
            "run_id": run_id,
            "symbol": symbol,
            "command": command,
            "report": report,
            "editorial_constraints": {
                "minimum_words": 900,
                "tone": "institutional, precise, operator-focused",
                "must_include_sections": [
                    "Executive Brief",
                    "In Plain English",
                    "Why This Matters Now",
                    "Evidence and Context",
                    "Execution Scenarios (30/90 day)",
                    "Risk Controls and Failure Modes",
                    "What to Track Next",
                    "Bottom Line",
                ],
                "must_include_visuals": [
                    "at least 2 standalone markdown images using ![alt](url)",
                    "short italic caption directly under each image",
                ],
                "domain_scope": "ai-fintech-hedge-fund",
                "must_avoid": [
                    "generic introductions about AI changing finance",
                    "content not grounded in the supplied report",
                    "marketing filler",
                    "empty conclusions",
                ],
            },
            "fallback": {
                "title": fallback_title,
                "excerpt": fallback_excerpt,
                "tags": list(fallback_tags),
                "image_query": fallback_image_query,
            },
            "output_schema": {
                "title": "string",
                "excerpt": "string_<=240_chars",
                "tags": ["string"],
                "image_query": "string_2_to_8_words",
                "content_markdown": "markdown_string_with_required_sections_and_2_or_3_inline_images",
            },
        }
        user_prompt = (
            "Return only JSON matching output_schema. No markdown fences. "
            "content_markdown must be full article body, not outline. "
            "Use standalone markdown image blocks inside content_markdown, not HTML. "
            "Keep paragraphs short and readable. Include one section literally titled 'In Plain English' that explains the technical point simply without dumbing it down. "
            "Use concrete symbols, catalysts, constraints, and risks from the supplied report. "
            "Do not fabricate numbers or citations not present in the report.\n"
            + json.dumps(user_payload, sort_keys=True, default=str)
        )

        try:
            response_meta = self._invoke_model(
                role="blog_writer",
                run_id=run_id,
                model=route_context["model"],
                system_prompt=system_prompt,
                user_prompt=user_prompt,
            )
            raw_text = str(response_meta["text"])
            usage = response_meta["usage"]
            provider_name = str(response_meta["provider"])
            provider_type = str(response_meta["provider_type"])
            resolved_model = str(response_meta["model"])
            parsed = _extract_json_object(raw_text)
            parse_retry_used = False
            if not parsed:
                parse_retry_used = True
                retry_meta = self._invoke_model(
                    role="blog_writer",
                    run_id=run_id,
                    model=resolved_model,
                    system_prompt=system_prompt,
                    user_prompt=(
                        f"{user_prompt}\n"
                        "Previous output was invalid JSON. Return exactly one strict JSON object with double-quoted keys."
                    ),
                    preferred_provider=provider_name,
                )
                parsed = _extract_json_object(str(retry_meta["text"]))
                if parsed:
                    raw_text = str(retry_meta["text"])
                    usage = {"initial": usage, "retry": retry_meta["usage"]}
                    provider_name = str(retry_meta["provider"])
                    provider_type = str(retry_meta["provider_type"])
                    resolved_model = str(retry_meta["model"])
                else:
                    self._last_error = "invalid_blog_json_response"
                    return None

            title = str(parsed.get("title") or "").strip()[:120] or fallback_title
            excerpt = str(parsed.get("excerpt") or "").strip()[:240] or fallback_excerpt
            content_markdown = str(parsed.get("content_markdown") or "").strip() or fallback_content_markdown
            lower_content = content_markdown.lower()
            if len(content_markdown.split()) < 600 or str(symbol or "").lower() not in lower_content:
                content_markdown = fallback_content_markdown
            tags = _normalize_tags(parsed.get("tags")) or fallback_tags
            image_query = str(parsed.get("image_query") or "").strip()[:80] or fallback_image_query

            self._last_error = None
            return AIBlogDraft(
                title=title,
                excerpt=excerpt,
                content_markdown=content_markdown,
                tags=tuple(tags),
                image_query=image_query,
                metadata={
                    "used": True,
                    "provider": provider_name,
                    "provider_type": provider_type,
                    "model": resolved_model,
                    "usage": usage,
                    "route": response_meta["route"],
                    "fallback_used": response_meta["fallback_used"],
                    "parse_retry_used": parse_retry_used,
                },
                provider=provider_name,
                model=resolved_model,
                raw_text=raw_text,
            )
        except Exception as exc:
            self._last_error = str(exc)
            if self._require_success:
                raise
            return None

    def _invoke_model(
        self,
        *,
        role: str,
        run_id: str,
        model: str,
        system_prompt: str,
        user_prompt: str,
        preferred_provider: str | None = None,
    ) -> dict[str, Any]:
        if not self._router_enabled:
            text, usage = self._invoke_legacy_provider(model=model, system_prompt=system_prompt, user_prompt=user_prompt)
            self._record_role_success(
                role=role,
                provider=self._provider,
                model=model,
                route=(self._provider,),
                fallback_used=False,
            )
            return {
                "text": text,
                "usage": usage,
                "provider": self._provider,
                "provider_type": self._provider,
                "model": model,
                "route": [self._provider],
                "fallback_used": False,
            }

        route = self._route_for_role(role)
        if preferred_provider:
            preferred = str(preferred_provider).strip().lower()
            if preferred in route:
                route = (preferred, *tuple(name for name in route if name != preferred))
        if not route:
            raise RuntimeError(f"ai_role_adapter_missing_route:{role}")

        errors: list[str] = []
        estimated_request_tokens = self._estimate_request_tokens(system_prompt=system_prompt, user_prompt=user_prompt)
        run_budget_available, run_skip_reason, run_retry_after = self._try_reserve_run_budget(
            run_id=run_id,
            role=role,
            estimated_tokens=estimated_request_tokens,
        )
        if not run_budget_available:
            failure = str(run_skip_reason or "run_budget_unavailable")
            self._record_role_failure(role=role, route=route, error=failure)
            raise TemporaryProviderCapacityError(
                failure,
                retry_after_seconds=run_retry_after,
                reasons=[failure],
                providers=list(route),
            )

        for index, provider_name in enumerate(route):
            provider = self._provider_configs.get(provider_name)
            if provider is None:
                errors.append(f"{provider_name}:provider_unconfigured")
                continue
            if not provider.enabled:
                errors.append(f"{provider_name}:provider_disabled")
                continue
            available, skip_reason = self._try_enter_provider(provider_name)
            if not available:
                errors.append(f"{provider_name}:{skip_reason}")
                continue
            provider_model = self._model_for_role(role, provider_name=provider_name, fallback=model)
            budget_reserved, budget_reason, budget_retry_after = self._try_reserve_provider_budget(
                provider_name=provider_name,
                estimated_tokens=estimated_request_tokens,
            )
            if not budget_reserved:
                self._record_provider_budget_skip(provider_name, reason=str(budget_reason))
                errors.append(f"{provider_name}:{budget_reason}")
                self._exit_provider(provider_name)
                continue
            self._record_provider_attempt(provider_name, provider_model)
            self._record_role_attempt(role=role, route=route)
            try:
                text, usage = self._invoke_provider(
                    provider=provider,
                    model=provider_model,
                    system_prompt=system_prompt,
                    user_prompt=user_prompt,
                )
                self._record_provider_success(provider_name, provider_model)
                self._record_budget_success(
                    provider_name=provider_name,
                    run_id=run_id,
                    role=role,
                    usage=usage,
                    fallback_estimated_tokens=estimated_request_tokens,
                )
                self._record_role_success(
                    role=role,
                    provider=provider_name,
                    model=provider_model,
                    route=route,
                    fallback_used=index > 0,
                )
                return {
                    "text": text,
                    "usage": usage,
                    "provider": provider_name,
                    "provider_type": provider.provider_type,
                    "model": provider_model,
                    "route": list(route),
                    "fallback_used": index > 0,
                }
            except Exception as exc:
                status_code = _parse_http_status(exc)
                self._record_provider_failure(provider_name, exc, status_code=status_code, failover=index < len(route) - 1)
                errors.append(f"{provider_name}:{exc}")
                continue
            finally:
                self._exit_provider(provider_name)

        failure = " | ".join(errors) if errors else "provider_invocation_failed"
        self._record_role_failure(role=role, route=route, error=failure)
        if self._route_temporarily_unavailable(route=route, errors=errors):
            raise TemporaryProviderCapacityError(
                failure,
                retry_after_seconds=self._earliest_retry_after(route),
                reasons=errors,
                providers=list(route),
            )
        raise RuntimeError(failure)

    def _route_temporarily_unavailable(self, *, route: tuple[str, ...], errors: list[str]) -> bool:
        if not route or not errors:
            return False
        if any("run_request_budget_exhausted" in item or "run_token_budget_exhausted" in item for item in errors):
            return True
        temporary_markers = (
            "provider_cooling_down",
            "provider_saturated",
            "provider_budget_window_exhausted",
            "provider_token_window_exhausted",
            ":429 ",
            "http_error:429",
        )
        for provider_name in route:
            provider_errors = [item for item in errors if item.startswith(f"{provider_name}:")]
            if not provider_errors:
                return False
            if not all(any(marker in item for marker in temporary_markers) for item in provider_errors):
                return False
        return True

    def _earliest_retry_after(self, route: tuple[str, ...]) -> float:
        candidates: list[float] = []
        now = time()
        with self._provider_state_lock:
            for provider_name in route:
                config = self._provider_configs.get(provider_name)
                state = self._provider_runtime.get(provider_name)
                if config is None or state is None:
                    continue
                if state.cooldown_until and state.cooldown_until > now:
                    candidates.append(max(1.0, float(state.cooldown_until - now)))
                    continue
                if state.window_reset_at and state.window_reset_at > now and (
                    (config.requests_per_window and state.requests_in_window >= max(0, int(config.requests_per_window)))
                    or (config.tokens_per_window and state.estimated_tokens_in_window >= max(0, int(config.tokens_per_window)))
                ):
                    candidates.append(max(1.0, float(state.window_reset_at - now)))
                    continue
                max_concurrency = max(1, int(config.max_concurrency))
                if int(state.in_flight) >= max_concurrency:
                    candidates.append(1.0)
        return min(candidates) if candidates else 5.0

    def _estimate_request_tokens(self, *, system_prompt: str, user_prompt: str) -> int:
        # Cheap approximation is sufficient for free-tier budget control.
        return max(1, int((len(system_prompt or "") + len(user_prompt or "")) / 4))

    def _estimate_total_tokens(self, *, usage: dict[str, Any], fallback_estimated_tokens: int, response_text: str = "") -> int:
        prompt_tokens = int(usage.get("prompt_tokens") or 0) if isinstance(usage, dict) else 0
        completion_tokens = int(usage.get("completion_tokens") or 0) if isinstance(usage, dict) else 0
        total_tokens = int(usage.get("total_tokens") or 0) if isinstance(usage, dict) else 0
        if total_tokens > 0:
            return max(1, total_tokens)
        if prompt_tokens > 0 or completion_tokens > 0:
            return max(1, prompt_tokens + completion_tokens)
        completion_estimate = max(1, int(len(response_text or "") / 4)) if response_text else 0
        return max(1, int(fallback_estimated_tokens) + completion_estimate)

    def _reset_provider_window_if_needed(self, state: ProviderRuntimeState, config: ProviderConfig, *, now: float | None = None) -> None:
        current = float(now if now is not None else time())
        if state.window_reset_at and current < state.window_reset_at:
            return
        state.window_started_at = current
        state.window_reset_at = current + max(1.0, float(config.window_seconds))
        state.requests_in_window = 0
        state.estimated_tokens_in_window = 0

    def _reset_run_window_if_needed(self, state: RunBudgetState, *, now: float | None = None) -> None:
        current = float(now if now is not None else time())
        if state.window_reset_at and current < state.window_reset_at:
            return
        state.window_started_at = current
        state.window_reset_at = current + self._run_window_seconds
        state.requests_used = 0
        state.estimated_tokens_used = 0

    def _try_reserve_provider_budget(self, *, provider_name: str, estimated_tokens: int) -> tuple[bool, str | None, float]:
        provider = self._provider_configs.get(provider_name)
        if provider is None:
            return False, "provider_unconfigured", 5.0
        now = time()
        with self._provider_state_lock:
            state = self._provider_runtime.setdefault(provider_name, ProviderRuntimeState())
            self._reset_provider_window_if_needed(state, provider, now=now)
            request_limit = max(0, int(provider.requests_per_window))
            token_limit = max(0, int(provider.tokens_per_window))
            if request_limit and state.requests_in_window >= request_limit:
                retry_after = max(1.0, float(state.window_reset_at - now))
                return False, f"provider_budget_window_exhausted:{retry_after:.1f}s", retry_after
            if token_limit and state.estimated_tokens_in_window + max(1, int(estimated_tokens)) > token_limit:
                retry_after = max(1.0, float(state.window_reset_at - now))
                return False, f"provider_token_window_exhausted:{retry_after:.1f}s", retry_after
            state.requests_in_window += 1
            state.estimated_tokens_in_window += max(1, int(estimated_tokens))
        return True, None, 0.0

    def _try_reserve_run_budget(self, *, run_id: str, role: str, estimated_tokens: int) -> tuple[bool, str | None, float]:
        if not run_id or (self._run_request_envelope <= 0 and self._run_tokens_envelope <= 0):
            return True, None, 0.0
        now = time()
        with self._run_budget_lock:
            state = self._run_budget_runtime.setdefault(str(run_id), RunBudgetState(run_id=str(run_id)))
            self._reset_run_window_if_needed(state, now=now)
            if self._run_request_envelope and state.requests_used >= self._run_request_envelope:
                retry_after = max(1.0, float(state.window_reset_at - now))
                return False, f"run_request_budget_exhausted:{retry_after:.1f}s", retry_after
            if self._run_tokens_envelope and state.estimated_tokens_used + max(1, int(estimated_tokens)) > self._run_tokens_envelope:
                retry_after = max(1.0, float(state.window_reset_at - now))
                return False, f"run_token_budget_exhausted:{retry_after:.1f}s", retry_after
            state.requests_used += 1
            state.estimated_tokens_used += max(1, int(estimated_tokens))
            state.last_role = role
            state.last_attempt_at = _utc_iso()
        return True, None, 0.0

    def _record_provider_budget_skip(self, provider_name: str, *, reason: str) -> None:
        with self._provider_state_lock:
            state = self._provider_runtime.setdefault(provider_name, ProviderRuntimeState())
            state.failovers += 1
            state.last_error = reason
            state.quota_state = "budget_window_exhausted"

    def _record_budget_success(
        self,
        *,
        provider_name: str,
        run_id: str,
        role: str,
        usage: dict[str, Any],
        fallback_estimated_tokens: int,
    ) -> None:
        total_tokens = self._estimate_total_tokens(usage=usage, fallback_estimated_tokens=fallback_estimated_tokens)
        additional_tokens = max(0, int(total_tokens) - max(1, int(fallback_estimated_tokens)))
        with self._provider_state_lock:
            state = self._provider_runtime.setdefault(provider_name, ProviderRuntimeState())
            state.estimated_tokens_in_window += additional_tokens
        if run_id and (self._run_request_envelope > 0 or self._run_tokens_envelope > 0):
            with self._run_budget_lock:
                state = self._run_budget_runtime.setdefault(str(run_id), RunBudgetState(run_id=str(run_id)))
                self._reset_run_window_if_needed(state)
                state.estimated_tokens_used += additional_tokens
                state.last_role = role
                state.last_provider = provider_name
                state.last_attempt_at = _utc_iso()

    def _invoke_legacy_provider(self, *, model: str, system_prompt: str, user_prompt: str) -> tuple[str, dict[str, Any]]:
        if self._provider in {"openai_compatible", "openai"}:
            return self._invoke_openai_compatible(
                base_url=self._base_url,
                api_key=self._api_key,
                model=model,
                system_prompt=system_prompt,
                user_prompt=user_prompt,
            )
        if self._provider in {"ollama", "ollama_native"}:
            return self._invoke_ollama(
                base_url=self._base_url,
                model=model,
                system_prompt=system_prompt,
                user_prompt=user_prompt,
            )
        raise ValueError(f"unsupported_ai_role_provider:{self._provider}")

    def _invoke_provider(
        self,
        *,
        provider: ProviderConfig,
        model: str,
        system_prompt: str,
        user_prompt: str,
    ) -> tuple[str, dict[str, Any]]:
        provider_type = provider.provider_type.strip().lower()
        if provider_type in {"openai_compatible", "openai"}:
            return self._invoke_openai_compatible(
                base_url=provider.base_url,
                api_key=provider.api_key,
                model=model,
                system_prompt=system_prompt,
                user_prompt=user_prompt,
            )
        if provider_type in {"ollama", "ollama_native"}:
            return self._invoke_ollama(
                base_url=provider.base_url,
                model=model,
                system_prompt=system_prompt,
                user_prompt=user_prompt,
            )
        raise ValueError(f"unsupported_provider_type:{provider.provider_type}")

    def _invoke_openai_compatible(
        self,
        *,
        base_url: str,
        api_key: str | None,
        model: str,
        system_prompt: str,
        user_prompt: str,
    ) -> tuple[str, dict[str, Any]]:
        url = f"{base_url.rstrip('/')}/chat/completions"
        headers = {"Content-Type": "application/json"}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        payload = {
            "model": model,
            "temperature": self._temperature,
            "max_tokens": self._max_tokens,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        }
        response = self._http_post(url, json=payload, headers=headers, timeout=self._timeout_seconds)
        response.raise_for_status()
        body = response.json()
        choices = body.get("choices") if isinstance(body, dict) else None
        if not isinstance(choices, list) or not choices:
            raise ValueError("no_choices_in_openai_response")
        message = (choices[0] or {}).get("message") or {}
        content = message.get("content")
        if isinstance(content, list):
            text_parts = []
            for item in content:
                if isinstance(item, dict) and item.get("type") == "text":
                    text_parts.append(str(item.get("text") or ""))
            text = "\n".join(part for part in text_parts if part).strip()
        else:
            text = str(content or "").strip()
        usage = body.get("usage") if isinstance(body.get("usage"), dict) else {}
        if not text:
            raise ValueError("empty_openai_response_text")
        return text, usage

    def _invoke_ollama(
        self,
        *,
        base_url: str,
        model: str,
        system_prompt: str,
        user_prompt: str,
    ) -> tuple[str, dict[str, Any]]:
        url = f"{base_url.rstrip('/')}/api/chat"
        payload = {
            "model": model,
            "stream": False,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "options": {
                "temperature": self._temperature,
                "num_predict": self._max_tokens,
            },
        }
        response = self._http_post(url, json=payload, timeout=self._timeout_seconds)
        response.raise_for_status()
        body = response.json()
        message = body.get("message") if isinstance(body, dict) else None
        text = ""
        if isinstance(message, dict):
            text = str(message.get("content") or "").strip()
        if not text:
            text = str(body.get("response") or "").strip() if isinstance(body, dict) else ""
        if not text:
            raise ValueError("empty_ollama_response_text")
        usage = {
            "prompt_eval_count": body.get("prompt_eval_count"),
            "eval_count": body.get("eval_count"),
        }
        return text, usage

    def _route_context_for_role(self, role: str) -> dict[str, Any]:
        if not self._router_enabled:
            return {"route": (self._provider,), "model": self._model_for_role(role, fallback=self._default_model)}
        route = self._route_for_role(role)
        first_provider = route[0] if route else None
        first_model = self._model_for_role(role, provider_name=first_provider, fallback="")
        return {"route": route, "model": first_model}

    def _route_for_role(self, role: str) -> tuple[str, ...]:
        normalized = _ROUTED_ROLE_ALIASES.get(str(role or "").strip(), str(role or "").strip())
        route = self._role_routes.get(normalized) or self._default_route
        return tuple(route)

    def _model_for_role(self, role: str, *, provider_name: str | None = None, fallback: str = "") -> str:
        if not self._router_enabled:
            if role in self._role_models and self._role_models[role]:
                return self._role_models[role]
            return self._default_model or fallback
        if provider_name and provider_name in self._provider_configs:
            config_model = self._provider_configs[provider_name].default_model
            if config_model:
                return config_model
        return fallback

    def _try_enter_provider(self, provider_name: str) -> tuple[bool, str | None]:
        config = self._provider_configs.get(provider_name)
        limiter = self._provider_limiters.get(provider_name)
        if config is None or limiter is None:
            return False, "provider_unconfigured"
        with self._provider_state_lock:
            state = self._provider_runtime.setdefault(provider_name, ProviderRuntimeState())
            now = time()
            if state.cooldown_until and state.cooldown_until > now:
                remaining = max(0.0, state.cooldown_until - now)
                return False, f"provider_cooling_down:{remaining:.1f}s"
        acquired = limiter.acquire(blocking=False)
        if not acquired:
            return False, "provider_saturated"
        with self._provider_state_lock:
            state = self._provider_runtime.setdefault(provider_name, ProviderRuntimeState())
            state.in_flight += 1
        return True, None

    def _exit_provider(self, provider_name: str) -> None:
        limiter = self._provider_limiters.get(provider_name)
        if limiter is None:
            return
        with self._provider_state_lock:
            state = self._provider_runtime.setdefault(provider_name, ProviderRuntimeState())
            state.in_flight = max(0, int(state.in_flight) - 1)
        limiter.release()

    def _record_provider_attempt(self, provider_name: str, model: str) -> None:
        with self._provider_state_lock:
            state = self._provider_runtime.setdefault(provider_name, ProviderRuntimeState())
            state.attempts += 1
            state.last_model = model

    def _record_provider_success(self, provider_name: str, model: str) -> None:
        provider = self._provider_configs.get(provider_name)
        with self._provider_state_lock:
            state = self._provider_runtime.setdefault(provider_name, ProviderRuntimeState())
            state.successes += 1
            state.last_model = model
            state.last_error = None
            state.last_status_code = None
            state.last_success_at = _utc_iso()
            state.cooldown_until = 0.0
            state.quota_state = _quota_state(
                api_key_configured=bool(provider.api_key) if provider else False,
                status_code=None,
                had_error=False,
            )

    def _record_provider_failure(
        self,
        provider_name: str,
        exc: Exception,
        *,
        status_code: int | None,
        failover: bool,
    ) -> None:
        provider = self._provider_configs.get(provider_name)
        with self._provider_state_lock:
            state = self._provider_runtime.setdefault(provider_name, ProviderRuntimeState())
            state.failures += 1
            if failover:
                state.failovers += 1
            state.last_error = str(exc)
            state.last_status_code = status_code
            state.last_failure_at = _utc_iso()
            if provider:
                if status_code == 429:
                    state.cooldown_until = max(state.cooldown_until, time() + max(0.0, float(provider.cooldown_seconds)))
                elif status_code in {408, 500, 502, 503, 504} or isinstance(exc, requests.RequestException):
                    state.cooldown_until = max(
                        state.cooldown_until,
                        time() + max(0.0, float(provider.transient_cooldown_seconds)),
                    )
            state.quota_state = _quota_state(
                api_key_configured=bool(provider.api_key) if provider else False,
                status_code=status_code,
                had_error=True,
            )

    def _record_role_attempt(self, *, role: str, route: tuple[str, ...]) -> None:
        state = self._role_runtime.setdefault(role, RoleRuntimeState())
        state.route = tuple(route)
        state.last_attempt_at = _utc_iso()

    def _record_role_success(
        self,
        *,
        role: str,
        provider: str,
        model: str,
        route: tuple[str, ...],
        fallback_used: bool,
    ) -> None:
        state = self._role_runtime.setdefault(role, RoleRuntimeState())
        state.route = tuple(route)
        state.last_provider = provider
        state.last_model = model
        state.last_error = None
        state.last_success_at = _utc_iso()
        state.fallback_used = fallback_used
        if fallback_used:
            state.failover_count += 1

    def _record_role_failure(self, *, role: str, route: tuple[str, ...], error: str) -> None:
        state = self._role_runtime.setdefault(role, RoleRuntimeState())
        state.route = tuple(route)
        state.last_error = error
        state.fallback_used = False
        self._last_error = error

    def _system_prompt_for_role(self, role: str) -> str:
        expertise_map = {
            "technical_analyst": "You are an elite technical analyst. Use objective chart, momentum, volatility, liquidity, and risk-reward logic.",
            "fundamental_analyst": "You are an elite fundamental analyst. Focus on quality, valuation, earnings durability, cash generation, and balance-sheet strength.",
            "sentiment_analyst": "You are an elite sentiment analyst. Separate signal from noise, identify narrative crowding, and quantify uncertainty.",
            "ml_timeseries_analyst": "You are an elite quantitative timeseries analyst. Discuss regime, forecast uncertainty, model drift, and failure modes without overclaiming.",
            "insight_researcher": "You are an elite research analyst. Synthesize catalysts, cross-asset implications, and decision relevance for a portfolio manager.",
            "hedge_fund_researcher": "You are an elite hedge-fund research strategist. Provide scenario-driven, risk-aware views with explicit invalidation conditions.",
            "blog_writer": "You are an elite financial research editor writing for sophisticated AI-fintech-hedge-fund readers.",
            "fund_manager": "You are an elite hedge-fund portfolio manager. Synthesize cross-role evidence into a decision memo with explicit risks and invalidation.",
        }
        base = expertise_map.get(role, "You are an elite investment analyst.")
        return (
            f"{base} "
            "Be concise, specific, and decision-usable. "
            "Never fabricate sources; cite only provided source_ids. "
            "State when evidence is insufficient instead of guessing."
        )


def _build_adapter_from_settings() -> AIRoleAdapter:
    settings = get_settings()
    role_models = {
        "technical_analyst": settings.AI_ROLE_MODEL_TECHNICAL or "",
        "fundamental_analyst": settings.AI_ROLE_MODEL_FUNDAMENTAL or "",
        "sentiment_analyst": settings.AI_ROLE_MODEL_SENTIMENT or "",
        "ml_timeseries_analyst": settings.AI_ROLE_MODEL_ML or "",
        "insight_researcher": settings.AI_ROLE_MODEL_INSIGHT or "",
        "hedge_fund_researcher": settings.AI_ROLE_MODEL_HEDGE_FUND or "",
        "blog_writer": settings.AI_ROLE_MODEL_BLOG or "",
        "fund_manager": settings.AI_ROLE_MODEL_FUND_MANAGER or "",
        "composite_synthesis": settings.AI_ROLE_MODEL_COMPOSITE_SYNTHESIS or "",
        "research_judge": settings.AI_ROLE_MODEL_RESEARCH_JUDGE or "",
    }

    if not settings.AI_ROLE_ROUTER_ENABLED:
        return AIRoleAdapter(
            enabled=settings.AI_ROLE_ADAPTER_ENABLED,
            provider=settings.AI_ROLE_PROVIDER,
            base_url=settings.AI_ROLE_API_BASE_URL,
            api_key=settings.AI_ROLE_API_KEY,
            timeout_seconds=settings.AI_ROLE_TIMEOUT_SECONDS,
            temperature=settings.AI_ROLE_TEMPERATURE,
            max_tokens=settings.AI_ROLE_MAX_TOKENS,
            default_model=settings.AI_ROLE_MODEL_DEFAULT,
            role_models=role_models,
            require_success=settings.AI_ROLE_REQUIRE_SUCCESS,
        )

    provider_configs: dict[str, ProviderConfig] = {
        "gemini_flash_lite": ProviderConfig(
            name="gemini_flash_lite",
            provider_type=settings.AI_ROLE_PROVIDER_GEMINI_FLASH_LITE_TYPE,
            base_url=settings.AI_ROLE_PROVIDER_GEMINI_FLASH_LITE_BASE_URL,
            api_key=settings.AI_ROLE_PROVIDER_GEMINI_FLASH_LITE_API_KEY,
            default_model=settings.AI_ROLE_PROVIDER_GEMINI_FLASH_LITE_MODEL,
            enabled=settings.AI_ROLE_PROVIDER_GEMINI_FLASH_LITE_ENABLED,
            max_concurrency=settings.AI_ROLE_PROVIDER_GEMINI_FLASH_LITE_MAX_CONCURRENCY,
            cooldown_seconds=settings.AI_ROLE_PROVIDER_GEMINI_FLASH_LITE_COOLDOWN_SECONDS,
            transient_cooldown_seconds=settings.AI_ROLE_PROVIDER_GEMINI_FLASH_LITE_TRANSIENT_COOLDOWN_SECONDS,
            requests_per_window=settings.AI_ROLE_PROVIDER_GEMINI_FLASH_LITE_REQUESTS_PER_WINDOW,
            tokens_per_window=settings.AI_ROLE_PROVIDER_GEMINI_FLASH_LITE_TOKENS_PER_WINDOW,
            window_seconds=settings.AI_ROLE_PROVIDER_GEMINI_FLASH_LITE_WINDOW_SECONDS,
        ),
        "gemini_flash": ProviderConfig(
            name="gemini_flash",
            provider_type=settings.AI_ROLE_PROVIDER_GEMINI_FLASH_TYPE,
            base_url=settings.AI_ROLE_PROVIDER_GEMINI_FLASH_BASE_URL,
            api_key=settings.AI_ROLE_PROVIDER_GEMINI_FLASH_API_KEY,
            default_model=settings.AI_ROLE_PROVIDER_GEMINI_FLASH_MODEL,
            enabled=settings.AI_ROLE_PROVIDER_GEMINI_FLASH_ENABLED,
            max_concurrency=settings.AI_ROLE_PROVIDER_GEMINI_FLASH_MAX_CONCURRENCY,
            cooldown_seconds=settings.AI_ROLE_PROVIDER_GEMINI_FLASH_COOLDOWN_SECONDS,
            transient_cooldown_seconds=settings.AI_ROLE_PROVIDER_GEMINI_FLASH_TRANSIENT_COOLDOWN_SECONDS,
            requests_per_window=settings.AI_ROLE_PROVIDER_GEMINI_FLASH_REQUESTS_PER_WINDOW,
            tokens_per_window=settings.AI_ROLE_PROVIDER_GEMINI_FLASH_TOKENS_PER_WINDOW,
            window_seconds=settings.AI_ROLE_PROVIDER_GEMINI_FLASH_WINDOW_SECONDS,
        ),
        "groq": ProviderConfig(
            name="groq",
            provider_type=settings.AI_ROLE_PROVIDER_GROQ_TYPE,
            base_url=settings.AI_ROLE_PROVIDER_GROQ_BASE_URL,
            api_key=settings.AI_ROLE_PROVIDER_GROQ_API_KEY,
            default_model=settings.AI_ROLE_PROVIDER_GROQ_MODEL,
            enabled=settings.AI_ROLE_PROVIDER_GROQ_ENABLED,
            max_concurrency=settings.AI_ROLE_PROVIDER_GROQ_MAX_CONCURRENCY,
            cooldown_seconds=settings.AI_ROLE_PROVIDER_GROQ_COOLDOWN_SECONDS,
            transient_cooldown_seconds=settings.AI_ROLE_PROVIDER_GROQ_TRANSIENT_COOLDOWN_SECONDS,
            requests_per_window=settings.AI_ROLE_PROVIDER_GROQ_REQUESTS_PER_WINDOW,
            tokens_per_window=settings.AI_ROLE_PROVIDER_GROQ_TOKENS_PER_WINDOW,
            window_seconds=settings.AI_ROLE_PROVIDER_GROQ_WINDOW_SECONDS,
        ),
        "github_models": ProviderConfig(
            name="github_models",
            provider_type=settings.AI_ROLE_PROVIDER_GITHUB_MODELS_TYPE,
            base_url=settings.AI_ROLE_PROVIDER_GITHUB_MODELS_BASE_URL,
            api_key=settings.AI_ROLE_PROVIDER_GITHUB_MODELS_API_KEY,
            default_model=settings.AI_ROLE_PROVIDER_GITHUB_MODELS_MODEL,
            enabled=settings.AI_ROLE_PROVIDER_GITHUB_MODELS_ENABLED,
            max_concurrency=settings.AI_ROLE_PROVIDER_GITHUB_MODELS_MAX_CONCURRENCY,
            cooldown_seconds=settings.AI_ROLE_PROVIDER_GITHUB_MODELS_COOLDOWN_SECONDS,
            transient_cooldown_seconds=settings.AI_ROLE_PROVIDER_GITHUB_MODELS_TRANSIENT_COOLDOWN_SECONDS,
            requests_per_window=settings.AI_ROLE_PROVIDER_GITHUB_MODELS_REQUESTS_PER_WINDOW,
            tokens_per_window=settings.AI_ROLE_PROVIDER_GITHUB_MODELS_TOKENS_PER_WINDOW,
            window_seconds=settings.AI_ROLE_PROVIDER_GITHUB_MODELS_WINDOW_SECONDS,
        ),
    }
    role_routes = {
        "technical_analyst": _parse_route(settings.AI_ROLE_ROUTE_TECHNICAL),
        "fundamental_analyst": _parse_route(settings.AI_ROLE_ROUTE_FUNDAMENTAL),
        "sentiment_analyst": _parse_route(settings.AI_ROLE_ROUTE_SENTIMENT),
        "ml_timeseries_analyst": _parse_route(settings.AI_ROLE_ROUTE_ML),
        "insight_researcher": _parse_route(settings.AI_ROLE_ROUTE_INSIGHT),
        "hedge_fund_researcher": _parse_route(settings.AI_ROLE_ROUTE_HEDGE_FUND),
        "fund_manager": _parse_route(settings.AI_ROLE_ROUTE_FUND_MANAGER),
        "composite_synthesis": _parse_route(settings.AI_ROLE_ROUTE_COMPOSITE_SYNTHESIS),
        "research_judge": _parse_route(settings.AI_ROLE_ROUTE_RESEARCH_JUDGE),
        "blog_writer": _parse_route(settings.AI_ROLE_ROUTE_BLOG),
    }
    gateway = {
        "enabled": bool(settings.AI_ROLE_GATEWAY_ENABLED),
        "base_url": settings.AI_ROLE_GATEWAY_BASE_URL or None,
    }
    return AIRoleAdapter(
        enabled=settings.AI_ROLE_ADAPTER_ENABLED,
        provider="router",
        base_url="",
        api_key=None,
        timeout_seconds=settings.AI_ROLE_TIMEOUT_SECONDS,
        temperature=settings.AI_ROLE_TEMPERATURE,
        max_tokens=settings.AI_ROLE_MAX_TOKENS,
        default_model="",
        role_models=role_models,
        require_success=settings.AI_ROLE_REQUIRE_SUCCESS,
        provider_configs=provider_configs,
        role_routes=role_routes,
        default_route=_parse_route(settings.AI_ROLE_ROUTE_DEFAULT),
        gateway=gateway,
        run_request_envelope=settings.AI_ROLE_RUN_REQUEST_ENVELOPE,
        run_tokens_envelope=settings.AI_ROLE_RUN_TOKENS_ENVELOPE,
        run_window_seconds=settings.AI_ROLE_RUN_WINDOW_SECONDS,
    )


ai_role_adapter = _build_adapter_from_settings()
