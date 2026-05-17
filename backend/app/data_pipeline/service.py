from __future__ import annotations

import asyncio
import logging
import math
import threading
from datetime import datetime, timezone
from typing import Any

from app.config import get_settings

from .models import FeatureVector
from .quality import validate_bars, validate_fundamentals, validate_price, validate_quote, validate_text_event
from .warehouse import stable_id, utc_iso, warehouse

logger = logging.getLogger("alfred.data_pipeline")


def _parse_symbols(value: str | None) -> list[str]:
    symbols = []
    for raw in str(value or "").replace(";", ",").split(","):
        symbol = raw.strip().upper()
        if symbol and symbol not in symbols:
            symbols.append(symbol)
    return symbols


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        number = float(value)
        if math.isfinite(number):
            return number
    except Exception:
        pass
    return default


class QuantDataPipeline:
    """
    Local-first quant data pipeline:
    ingest -> store -> process -> filter -> score -> categorize -> feature engineering.
    """

    def __init__(self) -> None:
        self._settings = get_settings()
        self._task: asyncio.Task | None = None
        self._running = False
        self._last_run: dict[str, Any] | None = None
        self._stream_subscribed = False
        self._stream_tick_count = 0
        self._stream_quote_count = 0
        self._news_stream_started = False
        self._news_stream_count = 0
        self._last_news_stream_event: dict[str, Any] | None = None
        self._last_stream_tick: dict[str, Any] | None = None
        self._last_stream_quote: dict[str, Any] | None = None
        self._last_history_refresh: dict[str, float] = {}
        self._last_fundamentals_refresh: dict[str, float] = {}

    def configured_symbols(self) -> list[str]:
        universe = _parse_symbols(getattr(self._settings, "DATA_PIPELINE_SYMBOLS", None))
        if universe:
            return universe
        scout = _parse_symbols(getattr(self._settings, "AGENT_RUNTIME_AUTOPILOT_SCOUT_SYMBOLS", None))
        return scout or ["SPY", "QQQ", "AAPL", "MSFT", "NVDA"]

    async def start(self) -> None:
        if not bool(getattr(self._settings, "DATA_PIPELINE_ENABLED", True)):
            logger.info("Quant data pipeline disabled by config")
            return
        if self._task and not self._task.done():
            return
        self._subscribe_to_stream()
        self._start_news_stream()
        self._running = True
        self._task = asyncio.create_task(self._run_loop(), name="quant-data-pipeline")
        logger.info("Quant data pipeline started stream_subscribed=%s", self._stream_subscribed)

    async def stop(self) -> None:
        self._running = False
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        self._task = None

    def _subscribe_to_stream(self) -> None:
        if self._stream_subscribed:
            return
        try:
            from app.data.market_data import FEED

            FEED.subscribe(self.record_market_stream_event)
            self._stream_subscribed = True
        except Exception as exc:
            logger.warning("Failed to subscribe data pipeline to market stream: %s", exc)

    def record_market_stream_event(self, symbol: str, price: float, event: dict[str, Any] | None = None) -> None:
        if (event or {}).get("event_type") == "quote":
            self.record_realtime_quote(symbol, event or {})
        else:
            self.record_realtime_tick(symbol, price, event)

    def _start_news_stream(self) -> None:
        if self._news_stream_started or not bool(getattr(self._settings, "DATA_PIPELINE_NEWS_STREAM_ENABLED", True)):
            return
        if not getattr(self._settings, "ALPACA_API_KEY", None):
            logger.warning("Alpaca news stream not started: missing ALPACA_API_KEY")
            return
        thread = threading.Thread(
            target=self._run_news_stream,
            daemon=True,
            name="alpaca-news-stream",
        )
        self._news_stream_started = True
        thread.start()

    def _run_news_stream(self) -> None:
        try:
            from alpaca.data.live import NewsDataStream

            stream = NewsDataStream(
                self._settings.ALPACA_API_KEY,
                self._settings.ALPACA_SECRET_KEY,
            )

            async def _on_news(item):
                self.record_realtime_news(item)

            stream.subscribe_news(_on_news, *self.configured_symbols())
            stream.run()
        except Exception as exc:
            self._news_stream_started = False
            logger.warning("Alpaca news stream failed: %s", exc)

    async def _run_loop(self) -> None:
        interval = max(5.0, float(getattr(self._settings, "DATA_PIPELINE_INTERVAL_SECONDS", 60.0)))
        while self._running:
            try:
                await asyncio.to_thread(self.run_cycle, self.configured_symbols(), "scheduled")
            except Exception as exc:
                logger.warning("Quant data pipeline cycle failed: %s", exc)
            await asyncio.sleep(interval)

    def run_cycle(self, symbols: list[str] | None = None, run_type: str = "manual") -> dict[str, Any]:
        symbols = [symbol.upper().strip() for symbol in (symbols or self.configured_symbols()) if symbol.strip()]
        run = {
            "run_id": stable_id("data-pipeline", run_type, ",".join(symbols), utc_iso()),
            "run_type": run_type,
            "status": "running",
            "started_at": utc_iso(),
            "symbols": symbols,
            "counts": {
                "prices": 0,
                "bars": 0,
                "text_events": 0,
                "fundamentals": 0,
                "features": 0,
                "quality_events": 0,
            },
            "quality": {},
            "metadata": {
                "flow": "ingest->store->process->filter->score->categorize->feature_engineering",
                "warehouse": "sqlite_local_first",
            },
        }
        warehouse.save_run(run)

        try:
            for symbol in symbols:
                try:
                    counts, quality = self.ingest_symbol(symbol)
                    for key, value in counts.items():
                        run["counts"][key] = int(run["counts"].get(key, 0)) + int(value)
                    run["quality"][symbol] = quality
                except Exception as exc:
                    run["quality"][symbol] = {
                        "status": "symbol_failed",
                        "error": str(exc) or exc.__class__.__name__,
                    }
                    logger.warning("Data pipeline symbol ingest failed symbol=%s error=%s", symbol, exc)
            run["status"] = "completed"
        except Exception as exc:
            run["status"] = "failed"
            run["metadata"]["error"] = str(exc)
            raise
        finally:
            run["finished_at"] = utc_iso()
            warehouse.save_run(run)
            self._last_run = run
        return run

    def ingest_symbol(self, symbol: str) -> tuple[dict[str, int], dict[str, Any]]:
        counts = {"prices": 0, "bars": 0, "text_events": 0, "fundamentals": 0, "features": 0, "quality_events": 0}
        quality_summary: dict[str, Any] = {}

        price_quality = self._ingest_price(symbol)
        counts["prices"] += 1
        counts["quality_events"] += 1
        quality_summary["price"] = {"score": price_quality.score, "flags": list(price_quality.flags)}

        if self._should_refresh(self._last_history_refresh, symbol, "DATA_PIPELINE_HISTORY_REFRESH_SECONDS"):
            bars_quality, bars_count = self._ingest_bars(symbol)
            self._last_history_refresh[symbol] = datetime.now(timezone.utc).timestamp()
            counts["bars"] += bars_count
            counts["quality_events"] += 1
            quality_summary["bars"] = {"score": bars_quality.score, "flags": list(bars_quality.flags)}
        else:
            quality_summary["bars"] = {"skipped": "refresh_interval_not_due"}

        text_count, text_quality_scores = self._ingest_news(symbol)
        counts["text_events"] += text_count
        counts["quality_events"] += len(text_quality_scores)
        quality_summary["text"] = {
            "events": text_count,
            "avg_score": round(sum(text_quality_scores) / max(len(text_quality_scores), 1), 4),
        }

        if self._should_refresh(self._last_fundamentals_refresh, symbol, "DATA_PIPELINE_FUNDAMENTALS_REFRESH_SECONDS"):
            fund_quality = self._ingest_fundamentals(symbol)
            self._last_fundamentals_refresh[symbol] = datetime.now(timezone.utc).timestamp()
            counts["fundamentals"] += 1
            counts["quality_events"] += 1
            quality_summary["fundamentals"] = {"score": fund_quality.score, "flags": list(fund_quality.flags)}
        else:
            quality_summary["fundamentals"] = {"skipped": "refresh_interval_not_due"}

        vector = self._materialize_features(symbol)
        if vector is not None:
            warehouse.save_feature_vector(vector)
            counts["features"] += 1
            quality_summary["features"] = {"category": vector.category, "score": vector.score}

        return counts, quality_summary

    def _should_refresh(self, state: dict[str, float], symbol: str, setting_name: str) -> bool:
        interval = max(0.0, float(getattr(self._settings, setting_name, 0.0)))
        previous = float(state.get(symbol) or 0.0)
        if previous <= 0:
            return True
        return (datetime.now(timezone.utc).timestamp() - previous) >= interval

    def record_realtime_tick(self, symbol: str, price: float, event: dict[str, Any] | None = None) -> None:
        normalized_symbol = str(symbol or "").upper().strip()
        px = _safe_float(price)
        observed_at = str((event or {}).get("observed_at") or utc_iso())
        payload = dict(event or {})
        payload.update({"symbol": normalized_symbol, "price": px, "observed_at": observed_at})
        raw_id = warehouse.save_raw_event(
            provider="alpaca_stream",
            endpoint="websocket.trades",
            asset_class="equities",
            symbol=normalized_symbol,
            request={"channel": "trades", "feed": getattr(self._settings, "ALPACA_FEED", "iex")},
            payload=payload,
            provider_ts=observed_at,
            metadata={"transport": "websocket", "stream_first": True},
        )
        quality = validate_price(normalized_symbol, "alpaca_stream", px, observed_at)
        warehouse.save_quality(quality)
        warehouse.save_market_price(
            symbol=normalized_symbol,
            asset_class="equities",
            price=px,
            provider="alpaca_stream",
            source_mode="stream",
            observed_at=observed_at,
            raw_id=raw_id,
            quality=quality,
        )
        vector = FeatureVector(
            symbol=normalized_symbol,
            asset_class="equities",
            use_case="execution",
            as_of=observed_at,
            features={
                "last_trade_price": px,
                "trade_size": _safe_float(payload.get("size")),
                "exchange": payload.get("exchange"),
                "feed": payload.get("feed") or getattr(self._settings, "ALPACA_FEED", "iex"),
                "freshness_seconds": 0.0,
            },
            score=round(float(quality.score), 6),
            category="live_tick" if quality.score >= 0.95 else "degraded_tick",
            source_snapshot_id=raw_id,
            metadata={"feature_set": "execution_tick_v1", "quality_flags": list(quality.flags)},
        )
        warehouse.save_feature_vector(vector)
        warehouse.upsert_provider_health(
            provider="alpaca_stream",
            status="healthy" if quality.severity == "ok" else "degraded",
            success=quality.severity == "ok",
            stale="stale_observation" in quality.flags,
            event_at=observed_at,
            metadata={"event_type": "trade", "symbol": normalized_symbol},
        )
        self._stream_tick_count += 1
        self._last_stream_tick = {
            "symbol": normalized_symbol,
            "price": px,
            "observed_at": observed_at,
            "quality_score": quality.score,
            "flags": list(quality.flags),
        }

    def record_realtime_quote(self, symbol: str, event: dict[str, Any]) -> None:
        normalized_symbol = str(symbol or "").upper().strip()
        bid_price = _safe_float(event.get("bid_price"))
        ask_price = _safe_float(event.get("ask_price"))
        observed_at = str(event.get("observed_at") or utc_iso())
        raw_id = warehouse.save_raw_event(
            provider="alpaca_quote_stream",
            endpoint="websocket.quotes",
            asset_class="equities",
            symbol=normalized_symbol,
            request={"channel": "quotes", "feed": getattr(self._settings, "ALPACA_FEED", "iex")},
            payload=event,
            provider_ts=observed_at,
            metadata={"transport": "websocket", "stream_first": True},
        )
        quality = validate_quote(
            normalized_symbol,
            "alpaca_quote_stream",
            bid_price,
            ask_price,
            observed_at,
            max_spread_bps=float(getattr(self._settings, "DATA_PIPELINE_MAX_SPREAD_BPS", 100.0)),
        )
        warehouse.save_quality(quality)
        warehouse.save_market_quote(
            symbol=normalized_symbol,
            asset_class="equities",
            bid_price=bid_price,
            bid_size=event.get("bid_size"),
            ask_price=ask_price,
            ask_size=event.get("ask_size"),
            provider="alpaca_quote_stream",
            source_mode="stream",
            observed_at=observed_at,
            raw_id=raw_id,
            quality=quality,
        )
        mid = ((bid_price + ask_price) / 2.0) if bid_price > 0 and ask_price > 0 else 0.0
        spread = max(0.0, ask_price - bid_price)
        spread_bps = (spread / mid * 10_000.0) if mid > 0 else 0.0
        vector = FeatureVector(
            symbol=normalized_symbol,
            asset_class="equities",
            use_case="execution",
            as_of=observed_at,
            features={
                "bid_price": bid_price,
                "ask_price": ask_price,
                "mid_price": round(mid, 6),
                "spread": round(spread, 6),
                "spread_bps": round(spread_bps, 6),
                "bid_size": _safe_float(event.get("bid_size")),
                "ask_size": _safe_float(event.get("ask_size")),
                "feed": event.get("feed") or getattr(self._settings, "ALPACA_FEED", "iex"),
            },
            score=round(float(quality.score), 6),
            category="nbbo_live" if quality.score >= 0.95 else "nbbo_degraded",
            source_snapshot_id=raw_id,
            metadata={"feature_set": "execution_nbbo_v1", "quality_flags": list(quality.flags)},
        )
        warehouse.save_feature_vector(vector)
        snapshot_id = warehouse.save_snapshot(
            snapshot_type="nbbo",
            symbol=normalized_symbol,
            as_of=observed_at,
            source_ids=[raw_id],
            payload=vector.features,
            quality={"score": quality.score, "flags": list(quality.flags), "severity": quality.severity},
            metadata={"feature_id": stable_id(normalized_symbol, "execution", observed_at, raw_id)},
        )
        warehouse.upsert_provider_health(
            provider="alpaca_quote_stream",
            status="healthy" if quality.severity == "ok" else "degraded",
            success=quality.severity == "ok",
            stale="stale_observation" in quality.flags,
            event_at=observed_at,
            metadata={"event_type": "quote", "symbol": normalized_symbol, "snapshot_id": snapshot_id},
        )
        self._stream_quote_count += 1
        self._last_stream_quote = {
            "symbol": normalized_symbol,
            "bid_price": bid_price,
            "ask_price": ask_price,
            "observed_at": observed_at,
            "quality_score": quality.score,
            "flags": list(quality.flags),
            "snapshot_id": snapshot_id,
        }

    def record_realtime_news(self, item: Any) -> None:
        raw = item if isinstance(item, dict) else {
            "id": getattr(item, "id", None),
            "headline": getattr(item, "headline", None),
            "summary": getattr(item, "summary", None),
            "author": getattr(item, "author", None),
            "url": getattr(item, "url", None),
            "symbols": getattr(item, "symbols", None),
            "created_at": getattr(item, "created_at", None),
            "updated_at": getattr(item, "updated_at", None),
        }
        symbols = raw.get("symbols") or []
        if isinstance(symbols, str):
            symbols = [symbols]
        title = str(raw.get("headline") or raw.get("title") or "").strip()
        published_at = str(raw.get("created_at") or raw.get("updated_at") or utc_iso())
        primary_symbol = str(symbols[0]).upper().strip() if symbols else None
        raw_id = warehouse.save_raw_event(
            provider="alpaca_news_stream",
            endpoint="websocket.news",
            asset_class="equities",
            symbol=primary_symbol,
            request={"channel": "news", "symbols": list(symbols)},
            payload=raw,
            provider_ts=published_at,
            metadata={"transport": "websocket", "stream_first": True},
        )
        text_rows = []
        for symbol in (symbols or [primary_symbol]):
            normalized_symbol = str(symbol or "").upper().strip() or None
            quality = validate_text_event(
                normalized_symbol,
                "alpaca_news_stream",
                title,
                published_at,
                max_age_hours=float(getattr(self._settings, "DATA_PIPELINE_MAX_NEWS_AGE_HOURS", 72.0)),
            )
            warehouse.save_quality(quality)
            text_rows.append(
                {
                    "event_id": stable_id("alpaca_news_stream", normalized_symbol or "", raw.get("id") or raw_id),
                    "symbol": normalized_symbol,
                    "asset_class": "equities",
                    "source_type": "news",
                    "provider": "alpaca_news_stream",
                    "title": title,
                    "body": raw.get("summary"),
                    "url": raw.get("url"),
                    "published_at": published_at,
                    "raw_id": raw_id,
                    "quality_score": quality.score,
                    "quality_flags": list(quality.flags),
                    "metadata": {"stream_first": True, "author": raw.get("author")},
                }
            )
        warehouse.save_text_events(text_rows)
        warehouse.upsert_provider_health(
            provider="alpaca_news_stream",
            status="healthy",
            success=True,
            event_at=published_at,
            metadata={"event_type": "news", "symbol": primary_symbol, "rows": len(text_rows)},
        )
        self._news_stream_count += len(text_rows)
        self._last_news_stream_event = {
            "symbol": primary_symbol,
            "title": title,
            "published_at": published_at,
            "rows": len(text_rows),
        }

    def _ingest_price(self, symbol: str):
        from app.data.market_data import FEED

        observed_at = utc_iso()
        price = _safe_float(FEED.price(symbol))
        payload = {"symbol": symbol, "price": price, "observed_at": observed_at}
        raw_id = warehouse.save_raw_event(
            provider="market_feed",
            endpoint="FEED.price",
            asset_class="equities",
            symbol=symbol,
            request={"symbol": symbol},
            payload=payload,
            provider_ts=observed_at,
            metadata={"adapter": "AlpacaRealtimeFeed"},
        )
        quality = validate_price(symbol, "market_feed", price, observed_at)
        warehouse.save_quality(quality)
        warehouse.save_market_price(
            symbol=symbol,
            asset_class="equities",
            price=price,
            provider="market_feed",
            source_mode="provider_or_guarded_fallback",
            observed_at=observed_at,
            raw_id=raw_id,
            quality=quality,
        )
        return quality

    def _ingest_bars(self, symbol: str) -> tuple[Any, int]:
        from app.data.market_data import FEED

        bars = int(getattr(self._settings, "DATA_PIPELINE_HISTORY_BARS", 260))
        frame = FEED.history(symbol, bars=bars)
        rows: list[dict[str, Any]] = []
        if frame is not None and hasattr(frame, "to_dict"):
            for row in frame.to_dict(orient="records"):
                rows.append(
                    {
                        "ts": row.get("ts") or row.get("Date") or row.get("Datetime"),
                        "open": _safe_float(row.get("open") or row.get("Open")),
                        "high": _safe_float(row.get("high") or row.get("High")),
                        "low": _safe_float(row.get("low") or row.get("Low")),
                        "close": _safe_float(row.get("close") or row.get("Close")),
                        "volume": _safe_float(row.get("volume") or row.get("Volume")),
                    }
                )
        raw_id = warehouse.save_raw_event(
            provider="market_feed",
            endpoint="FEED.history",
            asset_class="equities",
            symbol=symbol,
            request={"symbol": symbol, "bars": bars, "timeframe": "1d"},
            payload=rows,
            provider_ts=(str(rows[-1].get("ts")) if rows else None),
            metadata={"adapter": "AlpacaRealtimeFeed"},
        )
        quality = validate_bars(
            symbol,
            "market_feed",
            rows,
            max_age_days=float(getattr(self._settings, "DATA_PIPELINE_MAX_BAR_AGE_DAYS", 5.0)),
        )
        warehouse.save_quality(quality)
        inserted = warehouse.save_market_bars(
            symbol=symbol,
            asset_class="equities",
            timeframe="1d",
            rows=rows,
            provider="market_feed",
            raw_id=raw_id,
            quality=quality,
            adjusted=False,
        )
        return quality, inserted

    def _ingest_news(self, symbol: str) -> tuple[int, list[float]]:
        from app.data.news import latest_news

        rows = latest_news(symbol, limit=int(getattr(self._settings, "DATA_PIPELINE_NEWS_LIMIT", 12)))
        raw_id = warehouse.save_raw_event(
            provider="news_aggregate",
            endpoint="latest_news",
            asset_class="equities",
            symbol=symbol,
            request={"symbol": symbol},
            payload=rows,
            provider_ts=(rows[0].get("published_at") if rows else None),
            metadata={"providers": ["finnhub", "cache_or_sample"]},
        )
        text_rows: list[dict[str, Any]] = []
        scores: list[float] = []
        for row in rows:
            title = str(row.get("headline") or "").strip()
            published_at = row.get("published_at")
            provider = str(row.get("source") or "news_aggregate").strip().lower()
            quality = validate_text_event(
                symbol,
                provider,
                title,
                published_at,
                max_age_hours=float(getattr(self._settings, "DATA_PIPELINE_MAX_NEWS_AGE_HOURS", 72.0)),
            )
            warehouse.save_quality(quality)
            scores.append(float(quality.score))
            event_id = stable_id("news", symbol, provider, row.get("url") or title, published_at or "")
            text_rows.append(
                {
                    "event_id": event_id,
                    "symbol": symbol,
                    "asset_class": "equities",
                    "source_type": "news",
                    "provider": provider,
                    "title": title,
                    "url": row.get("url"),
                    "published_at": published_at,
                    "raw_id": raw_id,
                    "quality_score": quality.score,
                    "quality_flags": list(quality.flags),
                    "metadata": {"pipeline": "quant_data_pipeline"},
                }
            )
        return warehouse.save_text_events(text_rows), scores

    def _ingest_fundamentals(self, symbol: str):
        from app.data.fundamentals import get_fundamentals

        metrics = dict(get_fundamentals(symbol) or {})
        metric_date = datetime.now(timezone.utc).date().isoformat()
        raw_id = warehouse.save_raw_event(
            provider="fmp_fundamentals",
            endpoint="get_fundamentals",
            asset_class="equities",
            symbol=symbol,
            request={"symbol": symbol},
            payload=metrics,
            provider_ts=metric_date,
        )
        quality = validate_fundamentals(symbol, "fmp_fundamentals", metrics)
        warehouse.save_quality(quality)
        warehouse.save_fundamentals(
            symbol=symbol,
            asset_class="equities",
            provider="fmp_fundamentals",
            metric_date=metric_date,
            period="ttm",
            metrics=metrics,
            raw_id=raw_id,
            quality=quality,
        )
        return quality

    def _materialize_features(self, symbol: str) -> FeatureVector | None:
        bars = warehouse.load_recent_bars(symbol, "1d", limit=260)
        if not bars:
            return None
        latest_bar_ts = self._parse_ts(bars[-1].get("ts"))
        max_age_days = float(getattr(self._settings, "DATA_PIPELINE_MAX_BAR_AGE_DAYS", 5.0))
        bar_age_days = (
            max(0.0, (datetime.now(timezone.utc) - latest_bar_ts.astimezone(timezone.utc)).total_seconds() / 86400.0)
            if latest_bar_ts is not None
            else None
        )
        closes = [_safe_float(row.get("close")) for row in bars if _safe_float(row.get("close")) > 0]
        volumes = [_safe_float(row.get("volume")) for row in bars]
        if not closes:
            return None
        last = closes[-1]
        ret_1d = (last / closes[-2] - 1.0) if len(closes) > 1 and closes[-2] > 0 else 0.0
        ret_20d = (last / closes[-21] - 1.0) if len(closes) > 21 and closes[-21] > 0 else 0.0
        avg_volume_20d = sum(volumes[-20:]) / max(len(volumes[-20:]), 1)
        realized_vol_20d = self._realized_vol(closes[-21:])
        liquidity_score = min(1.0, max(0.0, math.log10(max(avg_volume_20d, 1.0)) / 8.0))
        trend_score = max(-1.0, min(1.0, ret_20d * 5.0))
        risk_penalty = min(0.5, realized_vol_20d * 3.0)
        composite = max(0.0, min(1.0, 0.5 + trend_score * 0.25 + liquidity_score * 0.2 - risk_penalty))
        stale_bar = bar_age_days is None or bar_age_days > max_age_days
        if stale_bar:
            composite = min(composite, 0.25)
            category = "stale_blocked"
        else:
            category = "trade_candidate" if composite >= 0.68 else "watchlist" if composite >= 0.52 else "research_only"
        features = {
            "last_close": round(last, 6),
            "return_1d": round(ret_1d, 6),
            "return_20d": round(ret_20d, 6),
            "realized_vol_20d": round(realized_vol_20d, 6),
            "avg_volume_20d": round(avg_volume_20d, 2),
            "liquidity_score": round(liquidity_score, 6),
            "trend_score": round(trend_score, 6),
            "bar_age_days": round(bar_age_days, 4) if bar_age_days is not None else None,
        }
        return FeatureVector(
            symbol=symbol,
            asset_class="equities",
            use_case="alpha",
            as_of=str(bars[-1].get("ts") or utc_iso()),
            features=features,
            score=round(composite, 6),
            category=category,
            source_snapshot_id=stable_id(symbol, "1d", len(bars), bars[-1].get("ts")),
            metadata={
                "feature_set": "quant_core_v1",
                "bars_used": len(bars),
                "latest_bar_ts": str(bars[-1].get("ts")),
                "stale_bar_blocked": stale_bar,
            },
        )

    @staticmethod
    def _realized_vol(closes: list[float]) -> float:
        if len(closes) < 3:
            return 0.0
        returns = []
        for prev, curr in zip(closes[:-1], closes[1:]):
            if prev > 0:
                returns.append((curr / prev) - 1.0)
        if len(returns) < 2:
            return 0.0
        mean = sum(returns) / len(returns)
        variance = sum((value - mean) ** 2 for value in returns) / len(returns)
        return math.sqrt(variance)

    def status(self) -> dict[str, Any]:
        status = warehouse.status()
        status.update(
            {
                "enabled": bool(getattr(self._settings, "DATA_PIPELINE_ENABLED", True)),
                "running": bool(self._task and not self._task.done()),
                "configured_symbols": self.configured_symbols(),
                "last_run": self._last_run,
                "stream": {
                    "subscribed": self._stream_subscribed,
                    "tick_count": self._stream_tick_count,
                    "quote_count": self._stream_quote_count,
                    "last_tick": self._last_stream_tick,
                    "last_quote": self._last_stream_quote,
                    "alpaca_stream_enabled": bool(getattr(self._settings, "ALPACA_STREAM_ENABLED", False)),
                    "feed": getattr(self._settings, "ALPACA_FEED", "iex"),
                },
                "news_stream": {
                    "enabled": bool(getattr(self._settings, "DATA_PIPELINE_NEWS_STREAM_ENABLED", True)),
                    "started": self._news_stream_started,
                    "event_count": self._news_stream_count,
                    "last_event": self._last_news_stream_event,
                },
                "storage_guidance": self.storage_estimate(),
                "provider_health": warehouse.provider_health(),
            }
        )
        return status

    def latest_features(self, symbol: str) -> list[dict[str, Any]]:
        return warehouse.latest_features(symbol)

    def replay_snapshot(self, snapshot_id: str) -> dict[str, Any] | None:
        return warehouse.load_snapshot(snapshot_id)

    def latest_rows(self, table: str, limit: int = 50) -> list[dict[str, Any]]:
        return warehouse.latest_rows(table, limit=limit)

    def storage_estimate(self, symbols: int | None = None) -> dict[str, Any]:
        symbol_count = int(symbols or len(self.configured_symbols()) or 1)
        tick_per_symbol_per_day = int(getattr(self._settings, "DATA_PIPELINE_TICK_ESTIMATE_PER_SYMBOL_DAY", 390))
        news_per_symbol_per_day = int(getattr(self._settings, "DATA_PIPELINE_NEWS_LIMIT", 12))
        bytes_per_price = 240
        bytes_per_bar = 360
        bytes_per_news = 2_500
        bytes_per_feature = 1_200
        daily_bytes = symbol_count * (
            tick_per_symbol_per_day * bytes_per_price
            + bytes_per_bar
            + news_per_symbol_per_day * bytes_per_news
            + bytes_per_feature
        )
        monthly_gb = daily_bytes * 21 / (1024 ** 3)
        return {
            "symbols": symbol_count,
            "assumptions": {
                "price_points_per_symbol_day": tick_per_symbol_per_day,
                "news_events_per_symbol_day": news_per_symbol_per_day,
                "bars_per_symbol_day": 1,
                "features_per_symbol_day": 1,
            },
            "estimated_storage": {
                "daily_mb": round(daily_bytes / (1024 ** 2), 3),
                "trading_month_gb": round(monthly_gb, 3),
                "trading_year_gb": round(monthly_gb * 12, 3),
            },
            "recommendation": (
                "SQLite is acceptable for local development and small IEX tick universes. "
                "Use Postgres+TimescaleDB for institutional continuous ticks, multi-asset history, or >5GB/year. "
                "Keep text/JSON metadata in Postgres JSONB; add object storage later for large raw documents."
            ),
        }

    @staticmethod
    def _parse_ts(value: Any):
        if value is None:
            return None
        try:
            return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        except Exception:
            return None


data_pipeline = QuantDataPipeline()
