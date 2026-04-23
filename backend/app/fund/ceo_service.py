from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.core.context import broker
from app.data.market_data import FEED
from app.data.news import latest_news
from app.fund.ai_role_adapter import ai_role_adapter
from app.fund.approval_center import approval_center
from app.fund.blog_service import blog_service
from app.fund.orchestrator import firm_orchestrator
from app.fund.performance_tracker import performance_tracker
from app.risk.engine import risk
from app.storage import db as storage_db


def _utc_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _safe_float(value: Any, fallback: float = 0.0) -> float:
    try:
        return float(value)
    except Exception:
        return fallback


def _symbol_key(value: str | None) -> str:
    return str(value or "").strip().upper()


def _brief_number(value: float) -> float:
    return round(_safe_float(value), 2)


def _runtime_status() -> dict[str, Any]:
    from app.fund.agent_runtime import fund_agent_runtime

    return fund_agent_runtime.status()


class VektorCeoService:
    def _positions(self) -> list[dict[str, Any]]:
        return broker.list_positions(FEED.price)

    def _orders(self) -> list[dict[str, Any]]:
        return broker.list_orders()

    def position_brief(self, symbol: str) -> dict[str, Any]:
        target = _symbol_key(symbol)
        positions = self._positions()
        row = next((item for item in positions if _symbol_key(item.get("symbol")) == target), None)
        if row is None:
            return {
                "accepted": False,
                "reason": "position_not_found",
                "symbol": target,
            }

        equity = _safe_float(broker.get_portfolio_value(FEED.price), 0.0)
        market_value = _safe_float(row.get("market_value"), 0.0)
        allocation_pct = (market_value / equity * 100.0) if equity > 0 else 0.0
        recent_orders = [
            order
            for order in self._orders()
            if _symbol_key(order.get("symbol")) == target
        ][:5]
        recent_tasks = [
            task
            for task in firm_orchestrator.list_task_history(limit=80, status=None)
            if _symbol_key((task.get("details") or {}).get("symbol") or (task.get("payload") or {}).get("symbol")) == target
        ][:8]
        news = []
        try:
            news = latest_news(target, limit=6)
        except Exception:
            news = []

        return {
            "accepted": True,
            "symbol": target,
            "briefed_at": _utc_iso(),
            "position": {
                "symbol": target,
                "quantity": _safe_float(row.get("qty"), 0.0),
                "average_price": _brief_number(row.get("avg_price")),
                "market_price": _brief_number(row.get("market_price")),
                "market_value": _brief_number(market_value),
                "unrealized_pnl": _brief_number(row.get("unrealized_pnl")),
                "asset_class": row.get("asset_class") or "equities",
                "instrument_type": row.get("instrument_type") or "equity",
                "routing_mode": row.get("routing_mode") or "paper_equity",
                "allocation_pct": round(allocation_pct, 2),
            },
            "recent_orders": recent_orders,
            "recent_tasks": recent_tasks,
            "news": news,
        }

    def portfolio_performance_breakdown(self) -> dict[str, Any]:
        positions = self._positions()
        if not positions:
            return {
                "accepted": True,
                "areas": [],
                "best_area": None,
                "worst_area": None,
                "total_unrealized_pnl": 0.0,
                "briefed_at": _utc_iso(),
            }

        buckets: dict[str, dict[str, Any]] = {}
        for row in positions:
            asset_class = str(row.get("asset_class") or "equities").strip().lower() or "equities"
            bucket = buckets.setdefault(
                asset_class,
                {
                    "asset_class": asset_class,
                    "symbols": [],
                    "market_value": 0.0,
                    "unrealized_pnl": 0.0,
                    "count": 0,
                },
            )
            bucket["symbols"].append(row.get("symbol"))
            bucket["market_value"] += _safe_float(row.get("market_value"))
            bucket["unrealized_pnl"] += _safe_float(row.get("unrealized_pnl"))
            bucket["count"] += 1

        areas = sorted(
            [
                {
                    **payload,
                    "symbols": list(dict.fromkeys(str(item) for item in payload["symbols"] if item)),
                    "market_value": _brief_number(payload["market_value"]),
                    "unrealized_pnl": _brief_number(payload["unrealized_pnl"]),
                }
                for payload in buckets.values()
            ],
            key=lambda item: item["unrealized_pnl"],
            reverse=True,
        )
        best_area = areas[0] if areas else None
        worst_area = areas[-1] if areas else None
        return {
            "accepted": True,
            "briefed_at": _utc_iso(),
            "areas": areas,
            "best_area": best_area,
            "worst_area": worst_area,
            "total_unrealized_pnl": _brief_number(sum(item["unrealized_pnl"] for item in areas)),
        }

    def positions_summary(self) -> dict[str, Any]:
        positions = self._positions()
        rows = []
        total_market_value = 0.0
        for row in positions:
            market_value = _safe_float(row.get("market_value"))
            unrealized = _safe_float(row.get("unrealized_pnl"))
            total_market_value += max(0.0, market_value)
            rows.append(
                {
                    "symbol": str(row.get("symbol") or "").upper(),
                    "asset_class": row.get("asset_class") or "equities",
                    "quantity": _safe_float(row.get("qty")),
                    "market_value": _brief_number(market_value),
                    "unrealized_pnl": _brief_number(unrealized),
                    "return_pct": round((unrealized / market_value * 100.0), 2) if market_value else 0.0,
                }
            )
        rows.sort(key=lambda item: item["unrealized_pnl"], reverse=True)
        return {
            "accepted": True,
            "briefed_at": _utc_iso(),
            "count": len(rows),
            "total_market_value": _brief_number(total_market_value),
            "positions": rows,
        }

    def winners_losers(self) -> dict[str, Any]:
        summary = self.positions_summary()
        rows = list(summary.get("positions") or [])
        return {
            "accepted": True,
            "briefed_at": _utc_iso(),
            "winners": rows[:5],
            "losers": list(reversed(rows[-5:])) if rows else [],
        }

    def exposure_by_asset_class(self) -> dict[str, Any]:
        breakdown = self.portfolio_performance_breakdown()
        policy = firm_orchestrator.allocation_policy_status()
        return {
            "accepted": True,
            "briefed_at": _utc_iso(),
            "areas": breakdown.get("areas") or [],
            "allocation": policy.get("asset_classes") or {},
        }

    def pending_approvals(self) -> dict[str, Any]:
        queue = approval_center.list_requests(limit=100, status="pending")
        return {
            "accepted": True,
            "briefed_at": _utc_iso(),
            "count": len(queue),
            "items": queue,
        }

    def risk_alerts(self) -> dict[str, Any]:
        alerts: list[dict[str, Any]] = []
        blocked = firm_orchestrator.list_blocked_trades(limit=10)
        if blocked:
            alerts.append(
                {
                    "severity": "high",
                    "type": "blocked_trades",
                    "message": f"{len(blocked)} blocked trade events require review.",
                }
            )
        dd = risk.status().get("drawdown_breaker") if isinstance(risk.status(), dict) else {}
        if isinstance(dd, dict) and dd.get("halted"):
            alerts.append(
                {
                    "severity": "critical",
                    "type": "drawdown_breaker",
                    "message": "Drawdown breaker is halted. New risk should stay blocked.",
                }
            )
        runtime_status = _runtime_status()
        ai_health = runtime_status.get("ai_role_adapter") if isinstance(runtime_status, dict) else {}
        providers = (ai_health or {}).get("providers") if isinstance(ai_health, dict) else {}
        if isinstance(providers, dict):
            throttled = [name for name, row in providers.items() if str((row or {}).get("quota_state") or "") == "throttled"]
            if throttled:
                alerts.append(
                    {
                        "severity": "medium",
                        "type": "provider_throttle",
                        "message": f"Hosted LLM rails throttled: {', '.join(throttled)}.",
                    }
                )
        pending = self.pending_approvals()
        if int(pending.get("count") or 0) > 0:
            alerts.append(
                {
                    "severity": "medium",
                    "type": "pending_approvals",
                    "message": f"{pending.get('count')} approvals are waiting on CEO review.",
                }
            )
        return {
            "accepted": True,
            "briefed_at": _utc_iso(),
            "count": len(alerts),
            "alerts": alerts,
        }

    def command_help(self) -> dict[str, Any]:
        command_groups = {
            "ceo_queries": [
                "brief me",
                "tell me about our nvidia position",
                "show positions",
                "show winners and losers",
                "what area of our portfolio is performing the best and the worst",
                "show exposure by asset class",
                "show pending approvals",
                "show risk alerts",
                "recent digests",
            ],
            "controls": [
                "runtime status",
                "pause runtime",
                "resume runtime",
                "clear halt",
                "kick autopilot",
                "allocation status",
                "set allocation run_id:<id> equities=40 options=10 commodities=10 forex=10 crypto=5 cash=25",
                "cancel run run_id:<id>",
                "cancel signal pack signal_pack_id:<id>",
                "reroute signal pack signal_pack_id:<id> roles=technical_analyst,sentiment_analyst",
                "discovery status limit:25",
            ],
            "approvals": [
                "approve decision symbol:NVDA",
                "reject decision decision_id:<id>",
                "approval detail request_id:<id>",
                "approve request request_id:<id>",
                "reject request request_id:<id>",
                "approve blog post_id:<id>",
                "reject blog post_id:<id>",
            ],
        }
        return {
            "accepted": True,
            "briefed_at": _utc_iso(),
            "overview": "Vektor is the canonical CEO control layer. Use natural-language portfolio questions or explicit runtime commands.",
            "command_groups": command_groups,
            **command_groups,
        }

    def pending_editorial_queue(self) -> dict[str, Any]:
        rows = blog_service.list_posts(limit=50, offset=0, status="pending_review").get("blogs", [])
        return {
            "accepted": True,
            "count": len(rows),
            "items": rows,
            "briefed_at": _utc_iso(),
        }

    def editorial_detail(self, post_id_or_slug: str) -> dict[str, Any]:
        post = blog_service.get_post_detail(post_id_or_slug, increment_views=False, include_unpublished=True)
        if post is None:
            return {"accepted": False, "reason": "editorial_not_found"}
        return {
            "accepted": True,
            "briefed_at": _utc_iso(),
            "editorial": post,
        }

    def approve_editorial(self, post_id_or_slug: str, *, approved_by: str, notes: str | None = None) -> dict[str, Any]:
        updated = blog_service.approve_post(post_id_or_slug, approved_by=approved_by, notes=notes)
        if updated is None:
            return {"accepted": False, "reason": "editorial_not_found"}
        return {
            "accepted": True,
            "status": "approved",
            "editorial": updated,
        }

    def reject_editorial(self, post_id_or_slug: str, *, rejected_by: str, notes: str | None = None) -> dict[str, Any]:
        updated = blog_service.reject_post(post_id_or_slug, rejected_by=rejected_by, notes=notes)
        if updated is None:
            return {"accepted": False, "reason": "editorial_not_found"}
        return {
            "accepted": True,
            "status": "needs_revision",
            "editorial": updated,
        }

    def digest(self) -> dict[str, Any]:
        positions = self._positions()
        pending_decisions = firm_orchestrator.list_pending_decisions()
        pending_editorial = self.pending_editorial_queue()
        runtime_status = _runtime_status()
        performance = performance_tracker.summary()
        breakdown = self.portfolio_performance_breakdown()
        llm = runtime_status.get("ai_role_adapter") if isinstance(runtime_status, dict) else {}
        providers = list((llm or {}).get("providers") or {})

        return {
            "accepted": True,
            "generated_at": _utc_iso(),
            "summary": {
                "positions_count": len(positions),
                "pending_decisions": len(pending_decisions),
                "pending_editorial": pending_editorial.get("count", 0),
                "active_tasks": len(runtime_status.get("active_contexts") or []),
                "equity": _brief_number((performance.get("latest_snapshot") or {}).get("equity")),
                "total_pnl": _brief_number((performance.get("latest_snapshot") or {}).get("total_pnl")),
            },
            "best_area": breakdown.get("best_area"),
            "worst_area": breakdown.get("worst_area"),
            "pending_decisions": pending_decisions[:5],
            "pending_approvals": self.pending_approvals().get("items", [])[:5],
            "pending_editorial": pending_editorial.get("items", [])[:5],
            "risk_alerts": self.risk_alerts().get("alerts", [])[:5],
            "provider_rail": {
                "mode": (llm or {}).get("mode"),
                "providers": providers,
            },
        }

    def persist_digest(self, *, digest_type: str = "scheduled", generated_by: str = "vektor") -> dict[str, Any]:
        digest = self.digest()
        digest_id = f"dg-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}"
        storage_db.save_ceo_digest(
            {
                "digest_id": digest_id,
                "digest_type": digest_type,
                "generated_by": generated_by,
                "payload": digest,
                "created_at": _utc_iso(),
            }
        )
        return {
            "accepted": True,
            "digest_id": digest_id,
            "digest": digest,
        }

    def list_digests(self, *, limit: int = 20, digest_type: str | None = None) -> dict[str, Any]:
        rows = storage_db.load_ceo_digests(limit=limit, digest_type=digest_type)
        return {
            "accepted": True,
            "count": len(rows),
            "items": rows,
            "briefed_at": _utc_iso(),
        }

    def market_watch(self) -> dict[str, Any]:
        positions = self._positions()
        portfolio_symbols = [_symbol_key(item.get("symbol")) for item in positions if _symbol_key(item.get("symbol"))]
        watchlist = ["SPY", "QQQ", "IWM", "DIA", "GLD", "TLT", "AAPL", "MSFT", "NVDA", "AMZN", "GOOGL", "META"]
        chart_symbols = list(dict.fromkeys([*watchlist, *portfolio_symbols]))[:12]
        ticker_snapshots: list[dict[str, Any]] = []
        for symbol in chart_symbols:
            price = _safe_float(FEED.price(symbol), 0.0)
            prev_close = price
            try:
                history = FEED.history(symbol, bars=5)
                if history is not None and len(history) >= 2:
                    prev_close = _safe_float(history["close"].iloc[-2], price)
            except Exception:
                prev_close = price
            change = price - prev_close
            change_pct = (change / prev_close * 100.0) if prev_close else 0.0
            ticker_snapshots.append(
                {
                    "symbol": symbol,
                    "name": symbol,
                    "price": _brief_number(price),
                    "prev_close": _brief_number(prev_close),
                    "change": _brief_number(change),
                    "change_pct": round(change_pct, 2),
                }
            )
        news_rows: list[dict[str, Any]] = []
        seen_news: set[str] = set()
        for symbol in chart_symbols[:10]:
            try:
                for item in latest_news(symbol, limit=6):
                    dedupe_key = str(item.get("url") or item.get("headline") or "").strip().lower()
                    if dedupe_key and dedupe_key in seen_news:
                        continue
                    if dedupe_key:
                        seen_news.add(dedupe_key)
                    news_rows.append(
                        {
                            "symbol": symbol,
                            "headline": item.get("headline"),
                            "source": item.get("source"),
                            "url": item.get("url"),
                            "published_at": item.get("published_at"),
                        }
                    )
            except Exception:
                continue
        news_rows.sort(key=lambda item: str(item.get("published_at") or ""), reverse=True)
        return {
            "accepted": True,
            "generated_at": _utc_iso(),
            "chart_symbols": chart_symbols,
            "portfolio_symbols": portfolio_symbols,
            "ticker_snapshots": ticker_snapshots,
            "news": news_rows[:48],
        }


vektor_ceo_service = VektorCeoService()
