from __future__ import annotations

import math
import re
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any, Iterable
from urllib.parse import quote_plus
from uuid import uuid4

from app.fund.ai_role_adapter import ai_role_adapter
from app.fund.contracts import ResearchReport as ContractResearchReport
from app.storage import db as storage_db


def _utc_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _utc_date_start_iso() -> str:
    now = datetime.now(timezone.utc)
    return now.replace(hour=0, minute=0, second=0, microsecond=0).isoformat().replace("+00:00", "Z")


def _slugify(value: str) -> str:
    text = re.sub(r"[^a-zA-Z0-9\s-]", "", str(value or "").strip().lower())
    text = re.sub(r"\s+", "-", text)
    text = re.sub(r"-+", "-", text).strip("-")
    if not text:
        return f"post-{uuid4().hex[:8]}"
    return text[:80]


def _ensure_unique_slug(value: str) -> str:
    base = _slugify(value)
    if not storage_db.load_blog_post(base):
        return base

    trimmed_base = base[:70].rstrip("-")
    for idx in range(2, 100):
        candidate = f"{trimmed_base}-{idx}"
        if not storage_db.load_blog_post(candidate):
            return candidate
    return f"{trimmed_base}-{uuid4().hex[:8]}"


def _to_report_dict(report: ContractResearchReport | dict[str, Any]) -> dict[str, Any]:
    if isinstance(report, ContractResearchReport):
        return report.model_dump(mode="json")
    return dict(report)


def _author_name_for_role(role: str) -> str:
    role_map = {
        "technical_analyst": "Technical Analyst Agent",
        "fundamental_analyst": "Fundamental Analyst Agent",
        "sentiment_analyst": "Sentiment Analyst Agent",
        "ml_timeseries_analyst": "ML Timeseries Analyst Agent",
        "insight_researcher": "Insight Research Agent",
        "hedge_fund_researcher": "Hedge Fund Research Agent",
        "signal_committee": "Signal Committee Agent",
        "blog_writer": "Vektor Editorial Agent",
    }
    return role_map.get(str(role or "").strip().lower(), "Vektor Research Agent")


def _category_for_role(role: str) -> str:
    role_map = {
        "technical_analyst": "Technical Strategy",
        "fundamental_analyst": "Fundamental Analysis",
        "sentiment_analyst": "Sentiment Intelligence",
        "ml_timeseries_analyst": "Quant Research",
        "insight_researcher": "Market Analysis",
        "hedge_fund_researcher": "Hedge Fund Research",
        "signal_committee": "Multi-Signal Intelligence",
        "blog_writer": "AI-Fintech Research",
    }
    return role_map.get(str(role or "").strip().lower(), "AI-Fintech Research")


def _first_sentence(text: str, fallback: str) -> str:
    raw = str(text or "").strip()
    if not raw:
        return fallback
    sentence = re.split(r"(?<=[.!?])\s+", raw, maxsplit=1)[0].strip()
    return sentence[:240] if sentence else fallback


def _topic_bundle(summary: str, findings: list[str], assets: list[str]) -> dict[str, Any]:
    blob = " ".join([summary, *findings]).lower()
    if any(token in blob for token in ("liquidity", "order book", "spread", "volatility regime", "volatility")):
        topic = "Liquidity Regime and Volatility Structure"
        image_query = "trading desk market volatility chart"
        tags = ("market microstructure", "liquidity", "volatility")
    elif any(token in blob for token in ("valuation", "earnings", "margin", "cash flow", "balance sheet")):
        topic = "Fundamental Drift and Valuation Repricing"
        image_query = "equity valuation financial statements analysis"
        tags = ("fundamental analysis", "valuation", "earnings")
    elif any(token in blob for token in ("sentiment", "news", "x ", "twitter", "narrative")):
        topic = "Narrative Rotation and Sentiment Regime Shift"
        image_query = "financial news sentiment dashboard"
        tags = ("sentiment", "market narrative", "alt data")
    elif any(token in blob for token in ("ml", "timeseries", "forecast", "probability", "regime")):
        topic = "Model Drift, Forecast Reliability, and Regime Detection"
        image_query = "quantitative model time series analysis"
        tags = ("quant research", "time series", "regime detection")
    else:
        topic = "AI-Native Hedge Fund Operations and Signal Discipline"
        image_query = "ai fintech hedge fund operations"
        tags = ("ai hedge fund", "portfolio operations", "risk")

    asset_tags = tuple(item.lower() for item in assets[:4] if item)
    return {"topic": topic, "image_query": image_query, "tags": tuple(dict.fromkeys((*tags, *asset_tags)))[:12]}


def _build_fallback_content(
    *,
    symbol: str,
    topic: str,
    summary: str,
    findings: list[str],
) -> str:
    bullet_rows = [f"- {item}" for item in findings[:10]]
    if not bullet_rows:
        bullet_rows = ["- No structured findings available; confidence is reduced until additional reports arrive."]

    return "\n".join(
        [
            "## Executive Brief",
            summary or f"{symbol} research package updated under {topic}.",
            "",
            "## Why This Matters Now",
            (
                f"{symbol} is showing a transition point in the current market regime. "
                "For a paper-first hedge fund workflow, this matters because position sizing and sleeve-level allocations "
                "must adjust before execution, not after slippage and volatility expansion."
            ),
            "",
            "## Evidence and Context",
            *bullet_rows,
            "",
            "## Execution Scenarios (30/90 day)",
            (
                "Base case (30d): controlled continuation with moderate dispersion. "
                "Upside case (90d): thesis reinforcement through catalyst confirmation and sustained breadth. "
                "Downside case (90d): thesis invalidation via liquidity deterioration and adverse macro repricing."
            ),
            "",
            "## Risk Controls and Failure Modes",
            (
                "Use pre-trade risk gates, sleeve budgets, and concentration caps as hard constraints. "
                "Failure modes include narrative overfitting, stale data latency, and structural breaks in volatility regimes."
            ),
            "",
            "## What to Track Next",
            (
                "Track signal persistence, estimate error drift, cross-asset correlation shifts, and execution quality "
                "versus expected slippage. Promote or demote conviction only on evidence."
            ),
            "",
            "## Reader Takeaway",
            (
                "Treat this as a decision-support memo, not a prediction. "
                "The advantage comes from disciplined iteration, provenance-backed evidence, and strict risk enforcement."
            ),
        ]
    ).strip()


def _markdown_to_excerpt(markdown: str, fallback: str) -> str:
    text = re.sub(r"^#+\s*", "", str(markdown or ""), flags=re.MULTILINE)
    text = re.sub(r"[*_`>-]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text[:220] if text else fallback


def _hero_image_url(image_query: str) -> str:
    query = quote_plus(str(image_query or "ai fintech market analysis"))
    return f"https://source.unsplash.com/1600x900/?{query}"


class BlogService:
    def daily_quota_remaining(self, target_per_day: int) -> int:
        target = max(0, int(target_per_day))
        if target == 0:
            return 0
        published_today = storage_db.count_blog_posts_since(_utc_date_start_iso())
        return max(0, target - int(published_today))

    def has_post_for_report(self, report_id: str) -> bool:
        key = str(report_id or "").strip()
        if not key:
            return False
        return storage_db.load_blog_post_by_source_report(key) is not None

    def select_editorial_candidates(
        self,
        *,
        reports: Iterable[dict[str, Any]],
        min_confidence: float,
        limit: int,
    ) -> list[dict[str, Any]]:
        candidates: list[dict[str, Any]] = []
        for row in reports:
            report_id = str(row.get("report_id") or "").strip()
            if not report_id or self.has_post_for_report(report_id):
                continue
            confidence = float(row.get("confidence") or 0.0)
            if confidence < float(min_confidence):
                continue
            candidates.append(row)
        candidates.sort(
            key=lambda item: (
                float(item.get("confidence") or 0.0),
                str(item.get("created_at") or ""),
            ),
            reverse=True,
        )
        return candidates[: max(0, int(limit))]

    def publish_from_research(
        self,
        *,
        report: ContractResearchReport | dict[str, Any],
        command: str | None = None,
        trigger_source: str = "agent_runtime",
    ) -> dict[str, Any]:
        report_row = _to_report_dict(report)
        report_id = str(report_row.get("report_id") or "").strip()
        run_id = str(report_row.get("run_id") or "").strip() or None
        agent_role = str(report_row.get("agent_id") or "insight_researcher").strip().lower()
        assets = [str(item).upper() for item in (report_row.get("asset_universe") or []) if str(item).strip()]
        symbol = assets[0] if assets else "MARKET"
        summary = str(report_row.get("summary") or "").strip()
        findings = [str(item).strip() for item in (report_row.get("findings") or []) if str(item).strip()]
        confidence = float(report_row.get("confidence") or 0.5)

        existing = storage_db.load_blog_post_by_source_report(report_id) if report_id else None
        if existing:
            return existing

        topic_bundle = _topic_bundle(summary, findings, assets)
        fallback_title = f"{symbol}: {topic_bundle['topic']}"
        fallback_content = _build_fallback_content(
            symbol=symbol,
            topic=str(topic_bundle["topic"]),
            summary=summary,
            findings=findings,
        )
        fallback_excerpt = _first_sentence(summary, f"Research update on {symbol} for AI-native hedge-fund operators.")
        fallback_tags = tuple(topic_bundle["tags"])
        fallback_image_query = str(topic_bundle["image_query"])

        ai_metadata: dict[str, Any] = {"used": False}
        ai_draft = None
        try:
            ai_draft = ai_role_adapter.draft_blog_post(
                run_id=run_id or f"run-blog-{uuid4().hex[:8]}",
                symbol=symbol,
                command=command
                or (
                    "Write a specific, useful article for AI-fintech-hedge-fund operators. "
                    "Avoid generic statements and include execution-relevant context."
                ),
                report=report_row,
                fallback_title=fallback_title,
                fallback_excerpt=fallback_excerpt,
                fallback_content_markdown=fallback_content,
                fallback_tags=fallback_tags,
                fallback_image_query=fallback_image_query,
            )
            if ai_draft:
                ai_metadata = dict(ai_draft.metadata or {"used": True})
        except Exception:
            ai_metadata = {"used": False, "error": ai_role_adapter.health().get("last_error")}

        final_title = str(ai_draft.title if ai_draft else fallback_title)[:120].strip() or fallback_title
        final_content = str(ai_draft.content_markdown if ai_draft else fallback_content).strip() or fallback_content
        final_excerpt = str(ai_draft.excerpt if ai_draft else _markdown_to_excerpt(final_content, fallback_excerpt)).strip()
        final_excerpt = final_excerpt[:240] if final_excerpt else fallback_excerpt
        final_tags = list(
            dict.fromkeys(
                [
                    *(ai_draft.tags if ai_draft else fallback_tags),
                    "vektor",
                    "ai-native",
                    "hedge-fund",
                    "research",
                ]
            )
        )[:12]
        image_query = str(ai_draft.image_query if ai_draft else fallback_image_query).strip() or fallback_image_query
        hero_url = _hero_image_url(image_query)

        read_time = max(4, min(20, int(math.ceil(len(final_content.split()) / 220.0))))
        post_id = f"blog-{uuid4().hex[:12]}"
        slug = _ensure_unique_slug(final_title)
        now = _utc_iso()
        post = {
            "id": post_id,
            "source_report_id": report_id or None,
            "source_run_id": run_id,
            "slug": slug,
            "title": final_title,
            "excerpt": final_excerpt,
            "category": _category_for_role(agent_role),
            "author": _author_name_for_role(agent_role),
            "author_role": agent_role,
            "content": final_content,
            "tags": final_tags,
            "views": 0,
            "read_time_minutes": read_time,
            "status": "published",
            "metadata": {
                "trigger_source": trigger_source,
                "command": command,
                "confidence": confidence,
                "report_id": report_id,
                "assets": assets,
                "topic": topic_bundle["topic"],
                "image_query": image_query,
                "hero_image_url": hero_url,
                "ai": ai_metadata,
            },
            "created_at": now,
            "published_at": now,
            "updated_at": now,
        }

        for _ in range(4):
            try:
                storage_db.save_blog_post(post)
                return storage_db.load_blog_post(post_id) or post
            except Exception as exc:  # pragma: no cover - defensive runtime retry
                if "blog_posts.slug" not in str(exc):
                    raise
                post["slug"] = f"{slug[:70].rstrip('-')}-{uuid4().hex[:8]}"
        raise RuntimeError("unable_to_persist_blog_post_due_to_slug_collisions")

    def list_posts(self, *, limit: int = 50, offset: int = 0, category: str | None = None) -> dict[str, Any]:
        rows = storage_db.load_blog_posts(limit=limit, offset=offset, category=category)
        total = storage_db.count_blog_posts(category=category)
        blogs = [self._to_blog_list_item(row) for row in rows]
        return {"blogs": blogs, "total": total, "limit": limit, "offset": offset}

    def get_post_detail(self, post_id_or_slug: str, *, increment_views: bool = True) -> dict[str, Any] | None:
        row = storage_db.load_blog_post(post_id_or_slug)
        if row is None:
            return None
        if increment_views:
            storage_db.increment_blog_post_views(str(row["id"]))
            row = storage_db.load_blog_post(str(row["id"])) or row
        return self._to_blog_detail_item(row)

    def create_from_reports(
        self,
        *,
        reports: Iterable[ContractResearchReport | dict[str, Any]],
        command: str | None = None,
        trigger_source: str = "agent_runtime",
    ) -> list[dict[str, Any]]:
        published: list[dict[str, Any]] = []
        for report in reports:
            try:
                published.append(
                    self.publish_from_research(
                        report=report,
                        command=command,
                        trigger_source=trigger_source,
                    )
                )
            except Exception:
                continue
        return published

    def _to_blog_list_item(self, row: dict[str, Any]) -> dict[str, Any]:
        metadata = dict(row.get("metadata") or {})
        return {
            "id": row.get("id"),
            "slug": row.get("slug"),
            "title": row.get("title"),
            "excerpt": row.get("excerpt"),
            "category": row.get("category"),
            "author": row.get("author"),
            "publishedAt": row.get("published_at"),
            "views": int(row.get("views") or 0),
            "readTime": int(row.get("read_time_minutes") or 3),
            "tags": list(row.get("tags") or []),
            "heroImageUrl": metadata.get("hero_image_url"),
        }

    def _to_blog_detail_item(self, row: dict[str, Any]) -> dict[str, Any]:
        metadata = dict(row.get("metadata") or {})
        return {
            **self._to_blog_list_item(row),
            "authorRole": row.get("author_role"),
            "status": row.get("status"),
            "sourceReportId": row.get("source_report_id"),
            "sourceRunId": row.get("source_run_id"),
            "content": row.get("content"),
            "metadata": metadata,
            "heroImageUrl": metadata.get("hero_image_url"),
            "createdAt": row.get("created_at"),
            "updatedAt": row.get("updated_at"),
        }


blog_service = BlogService()
