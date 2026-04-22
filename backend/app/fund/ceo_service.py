from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.core.context import broker
from app.data.market_data import FEED
from app.data.news import latest_news
from app.fund.agent_runtime import fund_agent_runtime
from app.fund.ai_role_adapter import ai_role_adapter
from app.fund.blog_service import blog_service
from app.fund.orchestrator import firm_orchestrator
from app.fund.performance_tracker import performance_tracker


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
        runtime_status = fund_agent_runtime.status()
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
            "pending_editorial": pending_editorial.get("items", [])[:5],
            "provider_rail": {
                "mode": (llm or {}).get("mode"),
                "providers": providers,
            },
        }

    def market_watch(self) -> dict[str, Any]:
        positions = self._positions()
        portfolio_symbols = [_symbol_key(item.get("symbol")) for item in positions if _symbol_key(item.get("symbol"))]
        watchlist = ["SPY", "QQQ", "IWM", "DIA", "AAPL", "MSFT", "NVDA", "AMZN", "GOOGL", "META"]
        chart_symbols = list(dict.fromkeys([*watchlist, *portfolio_symbols]))[:12]
        news_rows: list[dict[str, Any]] = []
        for symbol in chart_symbols[:6]:
            try:
                for item in latest_news(symbol, limit=4):
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
            "news": news_rows[:24],
        }


vektor_ceo_service = VektorCeoService()
