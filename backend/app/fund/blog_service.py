from __future__ import annotations

import math
import re
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any, Iterable
from uuid import uuid4

from app.data.news import latest_news
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
    if "high-grade multi-signal report" in blob or "specialist analyst swarm" in blob:
        topic = "Cross-Signal Case Study and Trade Construction"
        image_query = "hedge fund research desk multi factor analysis"
        tags = ("case study", "signal fusion", "trade construction")
    elif any(token in blob for token in ("liquidity", "order book", "spread", "volatility regime", "volatility")):
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


def _blend_plain_english(topic: str, thesis: str, confidence: float) -> str:
    confidence_pct = max(0, min(100, int(round(float(confidence or 0.0) * 100))))
    anchor = thesis.strip() or f"{topic} remains active but not fully confirmed."
    return (
        f"In plain English: {anchor} "
        f"That does not mean a trade is automatically justified. It means the desk has enough evidence to pay attention, "
        f"measure risk, and decide whether the setup deserves capital. Current conviction is {confidence_pct}%."
    )


def _build_fallback_content(
    *,
    symbol: str,
    topic: str,
    summary: str,
    findings: list[str],
    thesis: str = "",
    confidence: float = 0.0,
) -> str:
    cleaned_findings = [str(item).strip() for item in findings if str(item).strip()]
    key_findings = cleaned_findings[:6]
    evidence_rows = [f"- {item}" for item in key_findings]
    if not evidence_rows:
        evidence_rows = ["- No structured findings were available, so conviction remains constrained."]

    scenario_anchor = key_findings[0] if key_findings else summary or thesis or f"{symbol} setup is still under review."
    invalidation_anchor = key_findings[1] if len(key_findings) > 1 else "signal deterioration or adverse macro repricing"
    watch_items = key_findings[2:5] if len(key_findings) > 2 else [
        "price and volume confirmation",
        "estimate revisions and guidance drift",
        "execution quality versus expected slippage",
    ]
    watch_rows = [f"- {item}" for item in watch_items]
    thesis_line = thesis.strip() or summary.strip() or f"{symbol} is under active review inside Vektor's research stack."
    confidence_pct = max(0, min(100, int(round(float(confidence or 0.0) * 100))))

    return "\n".join(
        [
            "## Executive Brief",
            thesis_line,
            "",
            "## In Plain English",
            _blend_plain_english(topic, thesis_line, confidence),
            "",
            "## Why This Matters Now",
            (
                f"{symbol} sits inside the current {topic.lower()} discussion with an assessed confidence of {confidence_pct}%. "
                "For an AI-native hedge fund, that only matters if the evidence can be translated into sleeve-aware sizing, "
                "clear invalidation conditions, and a disciplined decision path before any order is staged."
            ),
            "",
            "## Evidence and Context",
            *evidence_rows,
            "",
            "## Execution Scenarios (30/90 day)",
            (
                f"Base case (30d): {scenario_anchor}. "
                "If that evidence persists, the setup can graduate from observation to tactical allocation. "
                f"Downside case (90d): the thesis fails if {invalidation_anchor.lower()} becomes the dominant condition."
            ),
            "",
            "## Risk Controls and Failure Modes",
            (
                "Use hard risk gates: sleeve budgets, concentration caps, and explicit invalidation triggers. "
                "Failure modes here are evidence drift, stale narrative anchoring, liquidity deterioration, and overconfident sizing "
                "relative to what the underlying report actually supports."
            ),
            "",
            "## What to Track Next",
            *watch_rows,
            "",
            "## Bottom Line",
            (
                f"The setup around {symbol} is interesting, but the only defensible action is evidence-led. "
                "If the signal confirms with price, liquidity, and risk alignment, the desk can act. If not, the correct decision is to wait."
            ),
        ]
    ).strip()


def _markdown_to_excerpt(markdown: str, fallback: str) -> str:
    text = re.sub(r"^#+\s*", "", str(markdown or ""), flags=re.MULTILINE)
    text = re.sub(r"[*_`>-]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text[:220] if text else fallback


def _hero_image_url(image_query: str) -> str:
    # Store a semantic descriptor, not a third-party image host URL.
    # blog-next converts this into a locally rendered blog visual so images remain available.
    return f"vektor://blog-image/{str(image_query or 'market-analysis').strip()}"


def _inline_image_urls(symbol: str, topic: str, image_query: str) -> tuple[str, str]:
    primary = _hero_image_url(f"{image_query} {symbol} trading desk")
    secondary = _hero_image_url(f"{topic} institutional research charts")
    return primary, secondary


def _inject_inline_images(*, markdown: str, symbol: str, topic: str, image_query: str) -> str:
    content = str(markdown or "").strip()
    if not content:
        return content
    if re.search(r"!\[[^\]]*\]\(([^)]+)\)", content):
        return content

    primary_url, secondary_url = _inline_image_urls(symbol, topic, image_query)
    figure_one = "\n".join(
        [
            f"![{symbol} market structure and operating context]({primary_url})",
            f"*Figure 1. {symbol} setup framing across market structure, narrative pressure, and execution context.*",
        ]
    )
    figure_two = "\n".join(
        [
            f"![{topic} evidence map and execution discipline]({secondary_url})",
            "*Figure 2. Evidence map, execution scenarios, and risk discipline for the live thesis.*",
        ]
    )

    def insert_before_heading(markdown_text: str, heading: str, block: str) -> str:
        anchor = f"## {heading}"
        idx = markdown_text.find(anchor)
        if idx == -1:
            return markdown_text + "\n\n" + block
        return markdown_text[:idx].rstrip() + "\n\n" + block + "\n\n" + markdown_text[idx:].lstrip()

    def insert_after_section(markdown_text: str, heading: str, block: str) -> str:
        anchor = f"## {heading}"
        start = markdown_text.find(anchor)
        if start == -1:
            return markdown_text + "\n\n" + block
        next_heading = markdown_text.find("\n## ", start + len(anchor))
        if next_heading == -1:
            return markdown_text.rstrip() + "\n\n" + block
        return markdown_text[:next_heading].rstrip() + "\n\n" + block + "\n\n" + markdown_text[next_heading:].lstrip()

    content = insert_after_section(content, "Why This Matters Now", figure_one)
    content = insert_before_heading(content, "Execution Scenarios (30/90 day)", figure_two)
    return content.strip()


def _schedule_display_name(kind: str) -> str:
    normalized = str(kind or "").strip().lower()
    mapping = {
        "premarket": "Premarket Report",
        "postmarket": "Postmarket Report",
        "week_ahead": "Week Ahead Report",
    }
    return mapping.get(normalized, "Market Report")


def _schedule_image_query(kind: str) -> str:
    normalized = str(kind or "").strip().lower()
    if normalized == "premarket":
        return "premarket trading desk overnight news"
    if normalized == "postmarket":
        return "postmarket trading desk closing bell"
    if normalized == "week_ahead":
        return "macro calendar market strategy board"
    return "market report institutional trading desk"


def _human_market_label(kind: str) -> str:
    normalized = str(kind or "").strip().lower()
    if normalized == "premarket":
        return "before the US cash session opens"
    if normalized == "postmarket":
        return "after the US cash session closes"
    if normalized == "week_ahead":
        return "for the coming trading week"
    return "for the live market session"


def _build_market_brief_content(
    *,
    schedule_kind: str,
    market_date: str,
    symbols: list[str],
    summary: str,
    findings: list[str],
    confidence: float,
) -> str:
    cleaned_findings = [str(item).strip() for item in findings if str(item).strip()]
    key_rows = cleaned_findings[:8]
    watch_rows = key_rows[:4] if key_rows else ["No strong cross-asset catalyst has separated from the noise yet."]
    impact_rows = key_rows[4:8] if len(key_rows) > 4 else [
        "Index futures direction",
        "mega-cap tech reaction",
        "rates and dollar behavior",
        "whether leadership broadens beyond one theme",
    ]
    date_label = _format_market_date(market_date)
    symbols_line = ", ".join(symbols[:8]) if symbols else "SPY, QQQ, rates, and major index leaders"
    confidence_pct = max(0, min(100, int(round(float(confidence or 0.0) * 100))))
    session_label = _human_market_label(schedule_kind)

    return "\n".join(
        [
            "## Quick Take",
            f"{summary.strip()} This note is written for {date_label} and focuses on {symbols_line}.",
            "",
            "## In Plain English",
            (
                f"Here is the simple version: Vektor is tracking what changed {session_label}, "
                "what that could do to positioning, and whether the evidence is strong enough to justify taking risk. "
                f"Current confidence is {confidence_pct}%."
            ),
            "",
            "## What Moved Overnight",
            *[f"- {item}" for item in watch_rows],
            "",
            "## What It Could Mean For Markets",
            *[f"- {item}" for item in impact_rows],
            "",
            "## Technical View",
            (
                "The desk should watch index futures, opening range behavior, liquidity depth, and whether leadership confirms "
                "across sectors instead of relying on one noisy headline."
            ),
            "",
            "## Risk View",
            (
                "Do not force a trade because the narrative sounds good. The correct approach is to wait for confirmation, "
                "respect sleeve budgets, and stay in cash if price action does not validate the thesis."
            ),
            "",
            "## What To Watch Today",
            "- Opening range expansion or failure in the main index ETFs.",
            "- Whether leadership broadens or narrows after the first hour.",
            "- Rates, dollar, and commodity responses to the same headlines.",
            "- Whether volume confirms the move or fades into chop.",
            "",
            "## Bottom Line",
            (
                "The goal is not to predict every move. The goal is to identify whether the overnight information creates a real edge, "
                "and to stay patient if the market does not confirm it."
            ),
        ]
    ).strip()


def _report_by_id(report_id: str) -> dict[str, Any] | None:
    key = str(report_id or "").strip()
    if not key:
        return None
    rows = storage_db.load_research_reports(limit=500)
    for row in rows:
        if str(row.get("report_id") or "").strip() == key:
            return row
    return None


def _normalize_sentence(text: str, *, limit: int = 220) -> str:
    raw = re.sub(r"\s+", " ", str(text or "").strip())
    if not raw:
        return ""
    raw = raw.replace("AI-native hedge fund", "the desk").replace("Vektor", "the desk")
    if len(raw) <= limit:
        return raw
    clipped = raw[:limit].rsplit(" ", 1)[0].strip()
    return f"{clipped}..."


def _source_label(source: str, external_id: str) -> str:
    normalized = str(source or "").strip().lower()
    external = str(external_id or "").strip().lower()
    if normalized == "research":
        return "Research signal"
    if normalized == "sentiment":
        return "Sentiment signal"
    if normalized == "data":
        if external.startswith("fmp-fundamentals"):
            return "Fundamental data snapshot"
        if external.startswith("price-series"):
            return "Price and volatility snapshot"
        return "Market data snapshot"
    if normalized == "news":
        return "News flow"
    return normalized.replace("_", " ").title() or "Research input"


def _summarize_provenance_item(item: dict[str, Any]) -> str:
    source = str(item.get("source") or "research").strip()
    external_id = str(item.get("external_id") or "").strip()
    confidence = item.get("confidence")
    confidence_str = ""
    if confidence is not None:
        try:
            confidence_str = f" ({int(round(float(confidence) * 100))}% confidence)"
        except Exception:
            confidence_str = ""

    if source.lower() == "research" and external_id:
        child = _report_by_id(external_id)
        if child:
            child_summary = _normalize_sentence(child.get("summary") or child.get("thesis") or "")
            child_assets = [str(asset).upper() for asset in (child.get("assets") or []) if str(asset).strip()]
            role = str(child.get("agent_role") or child.get("agent_id") or "research").replace("_", " ").strip()
            role = role.replace("agent", "").strip().title() or "Research"
            asset_prefix = f"{', '.join(child_assets[:2])}: " if child_assets else ""
            if child_summary:
                return f"{role}{confidence_str}: {asset_prefix}{child_summary}"

    label = _source_label(source, external_id)
    if external_id and source.lower() != "research":
        return f"{label}{confidence_str}: {external_id.replace('_', ' ')}"
    return f"{label}{confidence_str}"


def _derive_report_findings(report_row: dict[str, Any]) -> list[str]:
    findings: list[str] = []
    metadata = dict(report_row.get("metadata") or {})
    raw_findings = metadata.get("findings")
    if isinstance(raw_findings, list):
        findings.extend(str(item).strip() for item in raw_findings if str(item).strip())

    summary = str(report_row.get("summary") or "").strip()
    thesis = str(report_row.get("thesis") or "").strip()
    for candidate in [summary, thesis]:
        if candidate and candidate not in findings:
            findings.append(candidate)

    for item in list(report_row.get("provenance") or [])[:6]:
        if not isinstance(item, dict):
            continue
        line = _summarize_provenance_item(item)
        if line:
            findings.append(line)

    unique: list[str] = []
    seen: set[str] = set()
    for item in findings:
        token = _normalize_sentence(item)
        if not token or token in seen:
            continue
        seen.add(token)
        unique.append(token)
    return unique[:10]


def _classify_signal_bucket(text: str) -> str:
    blob = str(text or "").lower()
    if any(token in blob for token in ("technical", "momentum", "volatility", "price action", "structure", "support", "resistance", "trend")):
        return "technical"
    if any(token in blob for token in ("fundamental", "valuation", "earnings", "revenue", "margin", "cash flow", "debt", "balance sheet")):
        return "fundamental"
    if any(token in blob for token in ("sentiment", "narrative", "crowding", "news flow", "social", "headline")):
        return "sentiment"
    if any(token in blob for token in ("quant", "model", "forecast", "probability", "regime", "timeseries", "ml")):
        return "quant"
    return "market"


def _derive_structured_report_sections(report_row: dict[str, Any]) -> dict[str, list[str]]:
    buckets: dict[str, list[str]] = {
        "technical": [],
        "fundamental": [],
        "sentiment": [],
        "quant": [],
        "market": [],
    }
    seen: set[str] = set()

    def add(bucket: str, line: str) -> None:
        text = _normalize_sentence(line)
        if not text or text in seen:
            return
        seen.add(text)
        buckets[bucket].append(text)

    metadata = dict(report_row.get("metadata") or {})
    raw_findings = metadata.get("findings")
    if isinstance(raw_findings, list):
        for item in raw_findings:
            bucket = _classify_signal_bucket(str(item))
            add(bucket, str(item))

    for seed in [report_row.get("summary"), report_row.get("thesis")]:
        if seed:
            bucket = _classify_signal_bucket(str(seed))
            add(bucket, str(seed))

    for item in list(report_row.get("provenance") or [])[:8]:
        if not isinstance(item, dict):
            continue
        summary = _summarize_provenance_item(item)
        bucket = _classify_signal_bucket(summary)
        add(bucket, summary)

    return buckets


def _build_research_house_content(
    *,
    symbol: str,
    topic: str,
    title: str,
    summary: str,
    thesis: str,
    confidence: float,
    findings: list[str],
    structured_sections: dict[str, list[str]] | None = None,
) -> str:
    confidence_pct = max(0, min(100, int(round(float(confidence or 0.0) * 100))))
    cleaned_findings = [str(item).strip() for item in findings if str(item).strip()]
    sections = structured_sections or {}
    technical_rows = list(sections.get("technical") or [])[:3]
    fundamental_rows = list(sections.get("fundamental") or [])[:3]
    sentiment_rows = list(sections.get("sentiment") or [])[:3]
    quant_rows = list(sections.get("quant") or [])[:3]
    market_rows = list(sections.get("market") or [])[:3]

    if not any([technical_rows, fundamental_rows, sentiment_rows, quant_rows, market_rows]):
        market_rows = cleaned_findings[:5] if cleaned_findings else ["The current report has sparse structured evidence, so the thesis remains conditional."]

    overflow = cleaned_findings[:]
    watch_rows = overflow[5:9] if len(overflow) > 5 else [
        "follow-through in price and volume",
        "macro crosscurrents that can override the single-name thesis",
        "whether the catalyst is new information or recycled narrative",
    ]
    headline = summary.strip() or thesis.strip() or title.strip() or f"{symbol} remains under active review."
    simple = thesis.strip() or summary.strip() or headline

    parts: list[str] = [
        "## Quick Take",
        headline,
        "",
        "## In Plain English",
        (
            f"The short version: Vektor believes {symbol} is worth watching because of the current {topic.lower()} setup. "
            f"That does not mean the trade is automatic. It means there may be an edge if the market confirms the idea. "
            f"Current conviction is {confidence_pct}%."
        ),
        "",
    ]

    section_defs = [
        ("Technical Signal", technical_rows),
        ("Fundamental Signal", fundamental_rows),
        ("Sentiment Read", sentiment_rows),
        ("Quant Read", quant_rows),
        ("Market Context", market_rows),
    ]
    for heading, rows in section_defs:
        if not rows:
            continue
        parts.extend([f"## {heading}", *[f"- {item}" for item in rows], ""])

    parts.extend(
        [
            "## Why It Matters",
            (
                f"{simple} The question for the desk is whether that edge is large enough, durable enough, and liquid enough "
                "to deserve capital after risk filters are applied."
            ),
            "",
            "## Risk View",
            (
                "The failure mode is usually not a dramatic surprise. It is forcing size into a thesis that is only half-confirmed. "
                "The right response is smaller sizing, tighter invalidation, or no trade at all."
            ),
            "",
            "## What To Track Next",
            *[f"- {item}" for item in watch_rows],
            "",
            "## Bottom Line",
            (
                f"{symbol} has a usable research angle, but the real decision is whether the market validates it. "
                "If not, the disciplined choice is to wait."
            ),
        ]
    )

    return "\n".join(parts).strip()


def _format_market_date(value: str) -> str:
    raw = str(value or "").strip()
    if not raw:
        return datetime.now(timezone.utc).strftime("%B %d, %Y")
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00")).strftime("%B %d, %Y")
    except Exception:
        pass
    try:
        return datetime.strptime(raw, "%Y-%m-%d").strftime("%B %d, %Y")
    except Exception:
        return raw


def _news_digest_for_symbols(symbols: Iterable[str], *, per_symbol_limit: int = 4) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for symbol in list(dict.fromkeys(str(item).upper().strip() for item in symbols if str(item).strip()))[:8]:
        try:
            items = latest_news(symbol, limit=per_symbol_limit)
        except Exception:
            continue
        for item in items:
            headline = str(item.get("headline") or "").strip()
            if not headline:
                continue
            rows.append(
                {
                    "symbol": symbol,
                    "headline": headline,
                    "source": str(item.get("source") or "Unknown"),
                    "url": str(item.get("url") or ""),
                    "published_at": str(item.get("published_at") or ""),
                }
            )
    rows.sort(key=lambda item: item.get("published_at") or "", reverse=True)
    return rows[:24]


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

    def has_scheduled_post(self, *, schedule_kind: str, schedule_key: str) -> bool:
        normalized_kind = str(schedule_kind or "").strip().lower()
        normalized_key = str(schedule_key or "").strip()
        if not normalized_kind or not normalized_key:
            return False
        rows = storage_db.load_blog_posts(limit=200, offset=0)
        for row in rows:
            metadata = dict(row.get("metadata") or {})
            if (
                str(metadata.get("schedule_kind") or "").strip().lower() == normalized_kind
                and str(metadata.get("schedule_key") or "").strip() == normalized_key
            ):
                return True
        return False

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
            agent_role = str(row.get("agent_role") or "").strip().lower()
            agent_id = str(row.get("agent_id") or "").strip().lower()
            is_composite = agent_role == "researcher" or "signal_committee" in agent_id
            if not is_composite:
                # Editorial should default to composite/institutional outputs, not isolated analyst notes.
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
        thesis = str(report_row.get("thesis") or "").strip()

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
            thesis=thesis,
            confidence=confidence,
        )
        fallback_excerpt = _first_sentence(summary, f"Research update on {symbol} for AI-native hedge-fund operators.")
        fallback_tags = tuple(topic_bundle["tags"])
        fallback_image_query = str(topic_bundle["image_query"])
        fallback_content = _inject_inline_images(
            markdown=fallback_content,
            symbol=symbol,
            topic=str(topic_bundle["topic"]),
            image_query=fallback_image_query,
        )

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
        image_query = str(ai_draft.image_query if ai_draft else fallback_image_query).strip() or fallback_image_query
        final_content = str(ai_draft.content_markdown if ai_draft else fallback_content).strip() or fallback_content
        final_content = _inject_inline_images(
            markdown=final_content,
            symbol=symbol,
            topic=str(topic_bundle["topic"]),
            image_query=image_query,
        )
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

    def rewrite_posts_to_house_style(self, *, limit: int | None = None) -> list[dict[str, Any]]:
        rows = storage_db.load_blog_posts(limit=(limit if limit is not None else 500), offset=0)
        rewritten: list[dict[str, Any]] = []
        for row in rows:
            metadata = dict(row.get("metadata") or {})
            schedule_kind = str(metadata.get("schedule_kind") or "").strip().lower()
            category = str(row.get("category") or "").strip()
            title = str(row.get("title") or "").strip()
            excerpt = str(row.get("excerpt") or "").strip()

            if schedule_kind:
                symbols = [str(item).upper().strip() for item in (metadata.get("symbols") or []) if str(item).strip()]
                digest = metadata.get("news_digest") or []
                findings: list[str] = []
                for item in digest[:12]:
                    if isinstance(item, dict):
                        symbol = str(item.get("symbol") or "").strip().upper()
                        headline = str(item.get("headline") or "").strip()
                        source = str(item.get("source") or "").strip()
                        if headline:
                            findings.append(f"{symbol}: {headline} ({source or 'Unknown'})" if symbol else f"{headline} ({source or 'Unknown'})")
                content = _build_market_brief_content(
                    schedule_kind=schedule_kind,
                    market_date=str(metadata.get("market_date") or row.get("published_at") or ""),
                    symbols=symbols,
                    summary=excerpt or title,
                    findings=findings or ["No strong cross-asset catalyst has separated from the noise yet."],
                    confidence=float(metadata.get("confidence") or 0.62),
                )
                image_query = str(metadata.get("image_query") or _schedule_image_query(schedule_kind)).strip() or _schedule_image_query(schedule_kind)
                content = _inject_inline_images(
                    markdown=content,
                    symbol=(symbols[0] if symbols else "MARKET"),
                    topic=_schedule_display_name(schedule_kind),
                    image_query=image_query,
                )
                row["content"] = content
                row["excerpt"] = _first_sentence(excerpt or title, title)
                metadata["hero_image_url"] = _hero_image_url(image_query)
                metadata["image_query"] = image_query
                row["metadata"] = metadata
                storage_db.save_blog_post(row)
                rewritten.append({"slug": row.get("slug"), "title": row.get("title"), "kind": "market_brief"})
                continue

            report_id = str(row.get("source_report_id") or metadata.get("report_id") or "").strip()
            report_row = _report_by_id(report_id) if report_id else None
            assets = [str(item).upper() for item in ((report_row or {}).get("assets") or metadata.get("assets") or []) if str(item).strip()]
            symbol = assets[0] if assets else str((row.get("tags") or ["MARKET"])[0]).upper()
            topic = str(metadata.get("topic") or category or "Research Brief").strip() or "Research Brief"
            summary = str((report_row or {}).get("summary") or excerpt or title).strip()
            thesis = str((report_row or {}).get("thesis") or summary).strip()
            confidence = float((report_row or {}).get("confidence") or metadata.get("confidence") or 0.6)
            findings = _derive_report_findings(report_row or {})
            structured_sections = _derive_structured_report_sections(report_row or {})
            content = _build_research_house_content(
                symbol=symbol,
                topic=topic,
                title=title,
                summary=summary,
                thesis=thesis,
                confidence=confidence,
                findings=findings,
                structured_sections=structured_sections,
            )
            image_query = str(metadata.get("image_query") or _topic_bundle(summary, findings, assets).get("image_query") or "market research").strip()
            content = _inject_inline_images(
                markdown=content,
                symbol=symbol,
                topic=topic,
                image_query=image_query,
            )
            row["content"] = content
            row["excerpt"] = _first_sentence(summary, title)
            metadata["hero_image_url"] = _hero_image_url(image_query)
            metadata["image_query"] = image_query
            metadata["topic"] = topic
            row["metadata"] = metadata
            storage_db.save_blog_post(row)
            rewritten.append({"slug": row.get("slug"), "title": row.get("title"), "kind": "research"})
        return rewritten

    def publish_market_brief(
        self,
        *,
        schedule_kind: str,
        schedule_key: str,
        market_date: str,
        run_id: str,
        symbols: Iterable[str],
        command: str,
        trigger_source: str = "scheduled_market_report",
    ) -> dict[str, Any]:
        normalized_kind = str(schedule_kind or "").strip().lower()
        normalized_key = str(schedule_key or "").strip()
        normalized_symbols = [str(item).upper().strip() for item in symbols if str(item).strip()]
        if not normalized_kind or not normalized_key:
            raise RuntimeError("invalid_market_brief_schedule")
        if self.has_scheduled_post(schedule_kind=normalized_kind, schedule_key=normalized_key):
            existing = storage_db.load_blog_posts(limit=200, offset=0)
            for row in existing:
                metadata = dict(row.get("metadata") or {})
                if (
                    str(metadata.get("schedule_kind") or "").strip().lower() == normalized_kind
                    and str(metadata.get("schedule_key") or "").strip() == normalized_key
                ):
                    return self._to_blog_detail_item(row)

        news_digest = _news_digest_for_symbols(normalized_symbols, per_symbol_limit=4)
        headline_rows = [f"{item['symbol']}: {item['headline']} ({item['source']})" for item in news_digest[:12]]
        market_date_label = _format_market_date(market_date)
        title = f"{_schedule_display_name(normalized_kind)}: {market_date_label}"
        summary = (
            f"{_schedule_display_name(normalized_kind)} for {market_date_label}, covering overnight and cross-session "
            f"developments across {', '.join(normalized_symbols[:6]) or 'core market indices'}."
        )
        findings = headline_rows or ["No provider headlines were available at generation time."]
        pseudo_report = {
            "report_id": f"market-brief-{normalized_kind}-{normalized_key}",
            "run_id": run_id,
            "agent_id": "blog_writer_agent",
            "asset_universe": normalized_symbols or ["SPY", "QQQ"],
            "summary": summary,
            "findings": findings,
            "confidence": 0.62,
            "thesis": (
                "Translate overnight headlines, session context, and crowd positioning into a disciplined market brief with "
                "explicit uncertainty and scenario framing."
            ),
            "metadata": {
                "schedule_kind": normalized_kind,
                "schedule_key": normalized_key,
                "market_date": market_date,
                "news_digest": news_digest,
            },
        }
        fallback_content = _build_market_brief_content(
            schedule_kind=normalized_kind,
            market_date=market_date,
            symbols=normalized_symbols,
            summary=summary,
            findings=findings,
            confidence=0.62,
        )
        fallback_content = _inject_inline_images(
            markdown=fallback_content,
            symbol=(normalized_symbols[0] if normalized_symbols else "MARKET"),
            topic=_schedule_display_name(normalized_kind),
            image_query=_schedule_image_query(normalized_kind),
        )

        ai_metadata: dict[str, Any] = {"used": False}
        draft = None
        try:
            draft = ai_role_adapter.draft_blog_post(
                run_id=run_id,
                symbol=normalized_symbols[0] if normalized_symbols else "SPY",
                command=command,
                report=pseudo_report,
                fallback_title=title,
                fallback_excerpt=_first_sentence(summary, summary),
                fallback_content_markdown=fallback_content,
                fallback_tags=("market brief", normalized_kind.replace("_", "-"), "vektor", "macro"),
                fallback_image_query=_schedule_image_query(normalized_kind),
            )
            if draft:
                ai_metadata = dict(draft.metadata or {"used": True})
        except Exception:
            ai_metadata = {"used": False, "error": ai_role_adapter.health().get("last_error")}

        final_title = str(draft.title if draft else title).strip()[:120] or title
        final_excerpt = str(draft.excerpt if draft else _first_sentence(summary, summary)).strip()[:240]
        final_content = str(draft.content_markdown if draft else fallback_content).strip() or fallback_content
        image_query = str(draft.image_query if draft else _schedule_image_query(normalized_kind)).strip() or _schedule_image_query(normalized_kind)
        final_content = _inject_inline_images(
            markdown=final_content,
            symbol=(normalized_symbols[0] if normalized_symbols else "MARKET"),
            topic=_schedule_display_name(normalized_kind),
            image_query=image_query,
        )
        hero_url = _hero_image_url(image_query)
        read_time = max(4, min(16, int(math.ceil(len(final_content.split()) / 220.0))))
        now = _utc_iso()
        post = {
            "id": f"blog-{uuid4().hex[:12]}",
            "source_report_id": None,
            "source_run_id": run_id,
            "slug": _ensure_unique_slug(final_title),
            "title": final_title,
            "excerpt": final_excerpt,
            "category": "Market Reports",
            "author": "Vektor Market Intelligence",
            "author_role": "blog_writer",
            "content": final_content,
            "tags": list(dict.fromkeys(["market brief", normalized_kind.replace("_", "-"), *normalized_symbols[:4], "vektor"]))[:12],
            "views": 0,
            "read_time_minutes": read_time,
            "status": "published",
            "metadata": {
                "trigger_source": trigger_source,
                "command": command,
                "schedule_kind": normalized_kind,
                "schedule_key": normalized_key,
                "market_date": market_date,
                "symbols": normalized_symbols,
                "news_digest": news_digest[:12],
                "hero_image_url": hero_url,
                "image_query": image_query,
                "ai": ai_metadata,
            },
            "created_at": now,
            "published_at": now,
            "updated_at": now,
        }
        storage_db.save_blog_post(post)
        return storage_db.load_blog_post(str(post["id"])) or post

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
        ai = dict(metadata.get("ai") or {})
        provider_used = ai.get("provider") or ("fallback" if ai.get("used") is False else None)
        model_used = ai.get("model") or ("model-unresolved" if ai.get("used") is False else None)
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
            "providerUsed": provider_used,
            "modelUsed": model_used,
            "aiTrace": ai,
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
