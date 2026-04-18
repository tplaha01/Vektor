from __future__ import annotations

import ast
import json
import re
from dataclasses import dataclass
from decimal import Decimal
from time import monotonic
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
        if not token:
            continue
        if token in seen:
            continue
        seen.add(token)
        cleaned.append(token)
    return tuple(cleaned[:12])


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

    def health(self) -> dict[str, Any]:
        return {
            "enabled": self._enabled,
            "provider": self._provider,
            "base_url": self._base_url,
            "api_key_configured": bool(self._api_key),
            "default_model": self._default_model,
            "role_models": dict(self._role_models),
            "require_success": self._require_success,
            "last_error": self._last_error,
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
        model = self._model_for_role(role)
        if not model:
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
            + json.dumps(user_payload, sort_keys=True, default=str)
        )

        started = monotonic()
        try:
            raw_text, usage = self._invoke_model(
                model=model,
                system_prompt=system_prompt,
                user_prompt=user_prompt,
            )
            duration_ms = int((monotonic() - started) * 1000)
            parsed = _extract_json_object(raw_text)
            parse_retry_used = False
            if not parsed:
                parse_retry_used = True
                retry_prompt = (
                    f"{user_prompt}\n"
                    "Previous response was invalid JSON. Return exactly one strict JSON object with double-quoted keys."
                )
                retry_text, retry_usage = self._invoke_model(
                    model=model,
                    system_prompt=system_prompt,
                    user_prompt=retry_prompt,
                )
                parsed = _extract_json_object(retry_text)
                if parsed:
                    raw_text = retry_text
                    usage = {"initial": usage, "retry": retry_usage}
                else:
                    self._last_error = "invalid_json_response"
                    # Parse-format failures should degrade to deterministic fallback output
                    # so analyst workflows can continue with real-data-backed reports.
                    return AIRoleAnalysis(
                        summary=fallback_summary,
                        findings=fallback_findings,
                        confidence=fallback_confidence.quantize(Decimal("0.01")),
                        citations=tuple(dict.fromkeys(source_ids))[:12],
                        metadata={
                            "used": False,
                            "provider": self._provider,
                            "model": model,
                            "duration_ms": duration_ms,
                            "usage": usage,
                            "parse_retry_used": parse_retry_used,
                            "degraded_reason": "invalid_json_response",
                            "trade_setup": {},
                            "risk_flags": ["invalid_json_response"],
                        },
                        provider=self._provider,
                        model=model,
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
                    "provider": self._provider,
                    "model": model,
                    "duration_ms": duration_ms,
                    "usage": usage,
                    "parse_retry_used": parse_retry_used,
                    "trade_setup": trade_setup,
                    "risk_flags": [str(item) for item in risk_flags][:12],
                },
                provider=self._provider,
                model=model,
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
        model = self._model_for_role("blog_writer")
        if not model:
            self._last_error = "missing_model"
            if self._require_success:
                raise RuntimeError("ai_role_adapter_missing_model")
            return None

        system_prompt = (
            "You are Vektor's principal editorial analyst for AI, fintech, and hedge-fund research. "
            "Write specific, high-signal content for serious operators. "
            "Avoid generic motivation, filler, or broad beginner advice."
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
                    "Why This Matters Now",
                    "Evidence and Context",
                    "Execution Scenarios (30/90 day)",
                    "Risk Controls and Failure Modes",
                    "What to Track Next",
                ],
                "domain_scope": "ai-fintech-hedge-fund",
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
                "content_markdown": "markdown_string_with_required_sections",
            },
        }
        user_prompt = (
            "Return only JSON matching output_schema. No markdown fences. "
            "content_markdown must be full article body, not outline.\n"
            + json.dumps(user_payload, sort_keys=True, default=str)
        )

        try:
            raw_text, usage = self._invoke_model(model=model, system_prompt=system_prompt, user_prompt=user_prompt)
            parsed = _extract_json_object(raw_text)
            parse_retry_used = False
            if not parsed:
                parse_retry_used = True
                retry_text, retry_usage = self._invoke_model(
                    model=model,
                    system_prompt=system_prompt,
                    user_prompt=(
                        f"{user_prompt}\n"
                        "Previous output was invalid JSON. Return exactly one strict JSON object with double-quoted keys."
                    ),
                )
                parsed = _extract_json_object(retry_text)
                if parsed:
                    raw_text = retry_text
                    usage = {"initial": usage, "retry": retry_usage}
                else:
                    self._last_error = "invalid_blog_json_response"
                    return None

            title = str(parsed.get("title") or "").strip()[:120] or fallback_title
            excerpt = str(parsed.get("excerpt") or "").strip()[:240] or fallback_excerpt
            content_markdown = str(parsed.get("content_markdown") or "").strip() or fallback_content_markdown
            if len(content_markdown.split()) < 600:
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
                    "provider": self._provider,
                    "model": model,
                    "usage": usage,
                    "parse_retry_used": parse_retry_used,
                },
                provider=self._provider,
                model=model,
                raw_text=raw_text,
            )
        except Exception as exc:
            self._last_error = str(exc)
            if self._require_success:
                raise
            return None

    def _invoke_model(self, *, model: str, system_prompt: str, user_prompt: str) -> tuple[str, dict[str, Any]]:
        if self._provider in {"openai_compatible", "openai"}:
            return self._invoke_openai_compatible(model=model, system_prompt=system_prompt, user_prompt=user_prompt)
        if self._provider in {"ollama", "ollama_native"}:
            return self._invoke_ollama(model=model, system_prompt=system_prompt, user_prompt=user_prompt)
        raise ValueError(f"unsupported_ai_role_provider:{self._provider}")

    def _invoke_openai_compatible(self, *, model: str, system_prompt: str, user_prompt: str) -> tuple[str, dict[str, Any]]:
        url = f"{self._base_url}/chat/completions"
        headers = {"Content-Type": "application/json"}
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"
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

    def _invoke_ollama(self, *, model: str, system_prompt: str, user_prompt: str) -> tuple[str, dict[str, Any]]:
        url = f"{self._base_url}/api/chat"
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

    def _model_for_role(self, role: str) -> str:
        if role in self._role_models and self._role_models[role]:
            return self._role_models[role]
        return self._default_model

    def _system_prompt_for_role(self, role: str) -> str:
        expertise_map = {
            "technical_analyst": "You are an elite technical analyst. Use objective chart/momentum/volatility logic.",
            "fundamental_analyst": "You are an elite fundamental analyst. Focus on quality, valuation, and financial durability.",
            "sentiment_analyst": "You are an elite sentiment analyst. Distinguish noise vs signal and include confidence.",
            "ml_timeseries_analyst": "You are an elite quantitative timeseries analyst. Discuss regime, forecast uncertainty, and failure modes.",
            "insight_researcher": "You are an elite research analyst. Synthesize narrative catalysts and decision relevance.",
            "hedge_fund_researcher": "You are an elite hedge-fund research strategist. Provide scenario-driven, risk-aware views.",
            "blog_writer": "You are an elite financial research editor writing for sophisticated AI-fintech-hedge-fund readers.",
        }
        base = expertise_map.get(role, "You are an elite investment analyst.")
        return (
            f"{base} "
            "Be concise, specific, and decision-usable. "
            "Never fabricate sources; cite only provided source_ids."
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
    }
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


ai_role_adapter = _build_adapter_from_settings()
