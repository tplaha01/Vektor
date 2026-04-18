from __future__ import annotations

import math
import re
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Iterable
from uuid import uuid4

from app.fund.ai_role_adapter import ai_role_adapter
from app.fund.contracts import ResearchReport as ContractResearchReport
from app.storage import db as storage_db


def _utc_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


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

    # Keep suffix room for retries while preserving readability.
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
        "blog_writer": "Vektor Blog Agent",
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
        "blog_writer": "Market Analysis",
    }
    return role_map.get(str(role or "").strip().lower(), "Market Analysis")


class BlogService:
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

        ai_title = ""
        ai_summary = ""
        ai_findings: tuple[str, ...] = tuple()
        ai_metadata: dict[str, Any] = {"used": False}
        try:
            ai_result = ai_role_adapter.analyze_specialist(
                role="insight_researcher",
                symbol=symbol,
                run_id=run_id or f"run-blog-{uuid4().hex[:8]}",
                payload={
                    "command": command or "Write an expert blog post from research insights.",
                    "report_id": report_id,
                    "author_role": agent_role,
                    "trigger_source": trigger_source,
                },
                context={"report": report_row},
                fallback_summary=summary,
                fallback_findings=tuple(findings or [summary]),
                fallback_confidence=Decimal(str(max(min(confidence, 1.0), 0.0))),
                fallback_provenance=tuple(),
            )
            if ai_result:
                ai_summary = ai_result.summary
                ai_findings = ai_result.findings
                ai_title = ai_result.summary.split(".")[0].strip()
                ai_metadata = dict(ai_result.metadata or {"used": True})
        except Exception:
            ai_metadata = {"used": False, "error": ai_role_adapter.health().get("last_error")}

        final_summary = ai_summary or summary
        final_findings = list(ai_findings or tuple(findings))
        if not final_findings:
            final_findings = [final_summary] if final_summary else ["Research update generated by Vektor."]
        title_prefix = "/".join(assets[:3]) if assets else "Market"
        title = ai_title if ai_title else f"{title_prefix}: {final_findings[0][:72]}"
        title = title[:100].strip() or f"{title_prefix} Research Update"
        excerpt = final_summary[:220].strip() or f"Latest research update on {title_prefix}."

        body_lines = [
            final_summary,
            "",
            "Key Findings:",
            *[f"- {item}" for item in final_findings[:8]],
            "",
            "What This Means:",
            "This post is generated from live Vektor research workflows and is intended for paper-first decision support.",
            "",
            "Risk Note:",
            "Signals and views can fail in real markets; validate thesis, risk limits, and execution controls before any live deployment.",
        ]
        content = "\n".join(body_lines).strip()
        read_time = max(3, min(12, int(math.ceil(len(content.split()) / 220.0))))

        post_id = f"blog-{uuid4().hex[:12]}"
        slug = _ensure_unique_slug(title)
        now = _utc_iso()
        post = {
            "id": post_id,
            "source_report_id": report_id or None,
            "source_run_id": run_id,
            "slug": slug,
            "title": title,
            "excerpt": excerpt,
            "category": _category_for_role(agent_role),
            "author": _author_name_for_role(agent_role),
            "author_role": agent_role,
            "content": content,
            "tags": list(dict.fromkeys([*assets[:5], "vektor", "ai-native", "research"])),
            "views": 0,
            "read_time_minutes": read_time,
            "status": "published",
            "metadata": {
                "trigger_source": trigger_source,
                "command": command,
                "confidence": confidence,
                "report_id": report_id,
                "assets": assets,
                "ai": ai_metadata,
            },
            "created_at": now,
            "published_at": now,
            "updated_at": now,
        }
        # Slug is unique in DB. Retry with a unique suffix if a concurrent
        # writer inserted the same slug between check and save.
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
        }

    def _to_blog_detail_item(self, row: dict[str, Any]) -> dict[str, Any]:
        return {
            **self._to_blog_list_item(row),
            "authorRole": row.get("author_role"),
            "status": row.get("status"),
            "sourceReportId": row.get("source_report_id"),
            "sourceRunId": row.get("source_run_id"),
            "content": row.get("content"),
            "metadata": dict(row.get("metadata") or {}),
            "createdAt": row.get("created_at"),
            "updatedAt": row.get("updated_at"),
        }


blog_service = BlogService()
