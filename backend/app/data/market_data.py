from __future__ import annotations

import threading
import time
import os
from urllib.parse import urlencode
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Dict, List

import pandas as pd
import requests

from app.config import get_settings
from app.fund.runtime_guard import DataMode, data_integrity_guard

settings = get_settings()

_PROXY_ENV_KEYS = (
    "HTTP_PROXY",
    "HTTPS_PROXY",
    "ALL_PROXY",
    "http_proxy",
    "https_proxy",
    "all_proxy",
)


def _is_test_mode() -> bool:
    return bool(os.getenv("PYTEST_CURRENT_TEST")) or os.getenv("VEKTOR_TEST_MODE") == "1"

# Price cache: symbol -> (price, timestamp, source)
_price_cache: Dict[str, tuple[float, float, str]] = {}
_CACHE_TTL = 30.0  # seconds


def _empty_history() -> pd.DataFrame:
    return pd.DataFrame(columns=["ts", "open", "high", "low", "close", "volume"])


def _synthetic_price(symbol: str) -> float:
    base = 100.0 + (sum(ord(ch) for ch in symbol) % 25)
    return round(base, 2)


def _synthetic_history(symbol: str, bars: int) -> pd.DataFrame:
    total = max(2, int(bars))
    end = datetime.utcnow()
    step = 0.1 + ((sum(ord(ch) for ch in symbol) % 7) * 0.01)
    start_price = _synthetic_price(symbol) - (total * step * 0.5)
    rows: list[dict[str, float | datetime]] = []
    for idx in range(total):
        close = max(1.0, start_price + (idx * step))
        rows.append(
            {
                "ts": end - timedelta(days=(total - idx)),
                "open": round(close - 0.15, 4),
                "high": round(close + 0.2, 4),
                "low": round(close - 0.25, 4),
                "close": round(close, 4),
                "volume": float(1_000_000 + (idx * 1_000)),
            }
        )
    return pd.DataFrame(rows)


def _is_alpaca_connection_limit_error(exc: Exception) -> bool:
    message = str(exc or "").strip().lower()
    return (
        "connection limit exceeded" in message
        or "http 429" in message
        or "server rejected websocket connection: http 429" in message
    )


@contextmanager
def _without_proxy_env():
    """
    Temporarily disable inherited proxy environment variables for provider SDK calls.
    This prevents broken local proxy settings from forcing real-data requests through
    invalid endpoints (for example 127.0.0.1:9).
    """
    previous: dict[str, str] = {}
    removed: list[str] = []
    for key in _PROXY_ENV_KEYS:
        if key in os.environ:
            previous[key] = os.environ[key]
            removed.append(key)
            os.environ.pop(key, None)
    try:
        yield
    finally:
        for key in removed:
            if key in previous:
                os.environ[key] = previous[key]


class AlpacaRealtimeFeed:
    def __init__(self):
        self._prices: Dict[str, float] = {}
        self._subscribers: List[Callable] = []
        self._started = False

    def price(self, symbol: str) -> float:
        strict_mode = data_integrity_guard.strict_mode_enabled()
        normalized_symbol = str(symbol).upper().strip()

        if _is_test_mode():
            px = self._prices.get(normalized_symbol, _synthetic_price(normalized_symbol))
            self._prices[normalized_symbol] = px
            _price_cache[normalized_symbol] = (px, time.time(), "test_stub")
            data_integrity_guard.record_provider_event(
                provider="test_market_data",
                mode="fallback",
                symbol=normalized_symbol,
                detail="test_stub_price",
            )
            return px

        # 1. Use streaming price if available and fresh.
        if normalized_symbol in self._prices and self._prices[normalized_symbol] > 0:
            data_integrity_guard.record_provider_event(
                provider="alpaca_stream",
                mode="provider",
                symbol=normalized_symbol,
                detail="stream_tick",
            )
            return self._prices[normalized_symbol]

        # 2. Check cache.
        now = time.time()
        if normalized_symbol in _price_cache:
            px, ts, source = _price_cache[normalized_symbol]
            if now - ts < _CACHE_TTL and px > 0:
                cache_mode: DataMode = "provider" if source.startswith("alpaca") else "fallback"
                data_integrity_guard.record_provider_event(
                    provider="market_cache",
                    mode=cache_mode,
                    symbol=normalized_symbol,
                    detail=f"cache_source:{source}",
                )
                if strict_mode and cache_mode != "provider":
                    return 0.0
                return px

        # 3. Try Alpaca latest quote/bar.
        if settings.ALPACA_API_KEY:
            try:
                px = self._alpaca_latest_price(normalized_symbol)
                if px > 0:
                    self._prices[normalized_symbol] = px
                    _price_cache[normalized_symbol] = (px, now, "alpaca_rest")
                    data_integrity_guard.record_provider_event(
                        provider="alpaca_market_data",
                        mode="provider",
                        symbol=normalized_symbol,
                        detail="latest_trade",
                    )
                    return px
            except Exception as exc:
                print(f"Alpaca price failed for {normalized_symbol}: {exc}")
                data_integrity_guard.record_provider_event(
                    provider="alpaca_market_data",
                    mode="failed",
                    symbol=normalized_symbol,
                    detail=f"price_error:{exc}",
                )
        else:
            data_integrity_guard.record_provider_event(
                provider="alpaca_market_data",
                mode="fallback",
                symbol=normalized_symbol,
                detail="missing_alpaca_api_key",
            )
            if strict_mode:
                return 0.0

        # 4. Last known price from cache (stale but better than 0).
        if normalized_symbol in _price_cache and _price_cache[normalized_symbol][0] > 0:
            data_integrity_guard.record_provider_event(
                provider="market_cache",
                mode="fallback",
                symbol=normalized_symbol,
                detail="stale_cache_price",
            )
            if strict_mode:
                return 0.0
            return _price_cache[normalized_symbol][0]

        if strict_mode:
            return 0.0
        return self._prices.get(normalized_symbol, 0.0)

    def history(self, symbol: str, bars: int = 200) -> pd.DataFrame:
        strict_mode = data_integrity_guard.strict_mode_enabled()
        normalized_symbol = str(symbol).upper().strip()

        if _is_test_mode():
            data_integrity_guard.record_provider_event(
                provider="test_market_data",
                mode="fallback",
                symbol=normalized_symbol,
                detail=f"test_stub_bars:{bars}",
            )
            return _synthetic_history(normalized_symbol, bars)

        if settings.ALPACA_API_KEY:
            try:
                frame = self._alpaca_bars(normalized_symbol, bars)
                data_integrity_guard.record_provider_event(
                    provider="alpaca_market_data",
                    mode="provider",
                    symbol=normalized_symbol,
                    detail=f"bars:{len(frame)}",
                )
                return frame
            except Exception as exc:
                print(f"Alpaca bars failed for {normalized_symbol}: {exc}")
                data_integrity_guard.record_provider_event(
                    provider="alpaca_market_data",
                    mode="failed",
                    symbol=normalized_symbol,
                    detail=f"bars_error:{exc}",
                )
        else:
            data_integrity_guard.record_provider_event(
                provider="alpaca_market_data",
                mode="fallback",
                symbol=normalized_symbol,
                detail="missing_alpaca_api_key",
            )
            if strict_mode:
                return _empty_history()

        if strict_mode:
            return _empty_history()

        data_integrity_guard.record_provider_event(
            provider="yfinance_history",
            mode="fallback",
            symbol=normalized_symbol,
            detail="history_fallback_yfinance",
        )
        return self._yf_bars(normalized_symbol, bars)

    def subscribe(self, callback: Callable):
        self._subscribers.append(callback)

    def start_stream(self, symbols: List[str]):
        if _is_test_mode():
            data_integrity_guard.record_provider_event(
                provider="test_market_data",
                mode="fallback",
                detail="test_stub_stream",
            )
            return
        if not settings.ALPACA_STREAM_ENABLED:
            data_integrity_guard.record_provider_event(
                provider="alpaca_stream",
                mode="fallback",
                detail="stream_disabled_by_config",
            )
            return
        if self._started or not settings.ALPACA_API_KEY:
            if not settings.ALPACA_API_KEY:
                print("No ALPACA_API_KEY - using Alpaca REST polling")
                data_integrity_guard.record_provider_event(
                    provider="alpaca_stream",
                    mode="fallback",
                    detail="missing_alpaca_api_key",
                )
            return
        self._started = True
        t = threading.Thread(
            target=self._run_stream,
            args=(symbols,),
            daemon=True,
            name="alpaca-ws-feed",
        )
        t.start()
        print(f"Alpaca real-time stream started for {symbols}")

    def _run_stream(self, symbols: List[str]):
        try:
            from alpaca.data.live import StockDataStream
            from alpaca.data.enums import DataFeed

            feed_map = {"iex": DataFeed.IEX, "sip": DataFeed.SIP}
            feed = feed_map.get(settings.ALPACA_FEED.lower(), DataFeed.IEX)

            stream = StockDataStream(
                settings.ALPACA_API_KEY,
                settings.ALPACA_SECRET_KEY,
                feed=feed,
            )
            connection_limit_seen = {"value": False}
            original_connect = stream._connect
            original_auth = stream._auth

            async def _connect_with_limit_guard():
                try:
                    await original_connect()
                except Exception as exc:
                    if _is_alpaca_connection_limit_error(exc):
                        connection_limit_seen["value"] = True
                        raise ValueError("insufficient subscription: connection limit exceeded")
                    raise

            async def _auth_with_limit_guard():
                try:
                    await original_auth()
                except Exception as exc:
                    if _is_alpaca_connection_limit_error(exc):
                        connection_limit_seen["value"] = True
                        raise ValueError("insufficient subscription: connection limit exceeded")
                    raise

            stream._connect = _connect_with_limit_guard
            stream._auth = _auth_with_limit_guard

            async def _on_trade(trade):
                sym = str(getattr(trade, "symbol", "")).upper().strip()
                px = float(getattr(trade, "price", 0.0) or 0.0)
                trade_ts = getattr(trade, "timestamp", None)
                observed_at = (
                    trade_ts.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
                    if hasattr(trade_ts, "astimezone")
                    else datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
                )
                event: dict[str, Any] = {
                    "event_type": "trade",
                    "symbol": sym,
                    "price": px,
                    "observed_at": observed_at,
                    "size": getattr(trade, "size", None),
                    "exchange": getattr(trade, "exchange", None),
                    "trade_id": getattr(trade, "id", None),
                    "tape": getattr(trade, "tape", None),
                    "conditions": list(getattr(trade, "conditions", []) or []),
                    "feed": settings.ALPACA_FEED,
                }
                self._prices[sym] = px
                _price_cache[sym] = (px, time.time(), "alpaca_stream")
                data_integrity_guard.record_provider_event(
                    provider="alpaca_stream",
                    mode="provider",
                    symbol=sym,
                    detail="stream_tick",
                )
                for cb in self._subscribers:
                    try:
                        cb(sym, px, event)
                    except TypeError:
                        try:
                            cb(sym, px)
                        except Exception:
                            pass
                    except Exception:
                        pass

            async def _on_quote(quote):
                sym = str(getattr(quote, "symbol", "")).upper().strip()
                bid_price = float(getattr(quote, "bid_price", 0.0) or 0.0)
                ask_price = float(getattr(quote, "ask_price", 0.0) or 0.0)
                mid = ((bid_price + ask_price) / 2.0) if bid_price > 0 and ask_price > 0 else 0.0
                quote_ts = getattr(quote, "timestamp", None)
                observed_at = (
                    quote_ts.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
                    if hasattr(quote_ts, "astimezone")
                    else datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
                )
                event: dict[str, Any] = {
                    "event_type": "quote",
                    "symbol": sym,
                    "bid_price": bid_price,
                    "bid_size": getattr(quote, "bid_size", None),
                    "ask_price": ask_price,
                    "ask_size": getattr(quote, "ask_size", None),
                    "mid_price": mid,
                    "observed_at": observed_at,
                    "bid_exchange": getattr(quote, "bid_exchange", None),
                    "ask_exchange": getattr(quote, "ask_exchange", None),
                    "conditions": list(getattr(quote, "conditions", []) or []),
                    "tape": getattr(quote, "tape", None),
                    "feed": settings.ALPACA_FEED,
                }
                if mid > 0:
                    self._prices[sym] = mid
                    _price_cache[sym] = (mid, time.time(), "alpaca_quote_stream")
                data_integrity_guard.record_provider_event(
                    provider="alpaca_quote_stream",
                    mode="provider",
                    symbol=sym,
                    detail="quote_tick",
                )
                for cb in self._subscribers:
                    try:
                        cb(sym, mid, event)
                    except TypeError:
                        try:
                            cb(sym, mid)
                        except Exception:
                            pass
                    except Exception:
                        pass

            stream.subscribe_trades(_on_trade, *symbols)
            stream.subscribe_quotes(_on_quote, *symbols)
            stream.run()
            if connection_limit_seen["value"]:
                print("Alpaca stream connection limit exceeded - falling back to REST polling")
                data_integrity_guard.record_provider_event(
                    provider="alpaca_stream",
                    mode="fallback",
                    detail="stream_connection_limit_exceeded",
                )
            self._started = False

        except Exception as exc:
            print(f"Alpaca stream error: {exc} - falling back to REST polling")
            data_integrity_guard.record_provider_event(
                provider="alpaca_stream",
                mode="failed",
                detail=f"stream_error:{exc}",
            )
            self._started = False

    def _alpaca_latest_price(self, symbol: str) -> float:
        payload = self._alpaca_rest_json(
            "/v2/stocks/trades/latest",
            {"symbols": symbol},
        )
        trade = ((payload or {}).get("trades") or {}).get(symbol) or {}
        price = trade.get("p")
        if price is not None:
            return float(price)
        return 0.0

    def _alpaca_bars(self, symbol: str, bars: int) -> pd.DataFrame:
        start = (datetime.utcnow() - timedelta(days=bars * 2)).replace(microsecond=0).isoformat() + "Z"
        payload = self._alpaca_rest_json(
            "/v2/stocks/bars",
            {
                "symbols": symbol,
                "timeframe": "1Day",
                "start": start,
                "limit": max(1, int(bars)),
                "feed": settings.ALPACA_FEED,
                "sort": "desc",
            },
        )
        rows = ((payload or {}).get("bars") or {}).get(symbol) or []
        if not rows:
            return _empty_history()
        frame = pd.DataFrame(rows)
        frame = frame.rename(
            columns={
                "t": "ts",
                "o": "open",
                "h": "high",
                "l": "low",
                "c": "close",
                "v": "volume",
            }
        )
        frame = frame[[col for col in ("ts", "open", "high", "low", "close", "volume") if col in frame.columns]]
        if "ts" in frame.columns:
            frame["ts"] = pd.to_datetime(frame["ts"], utc=True, errors="coerce")
            frame = frame.sort_values("ts", ascending=True)
        return frame.tail(bars).reset_index(drop=True)

    def _alpaca_rest_json(self, path: str, params: dict[str, object] | None = None) -> dict:
        params = dict(params or {})
        if settings.ALPACA_FEED and "feed" not in params and path.startswith("/v2/stocks/"):
            params["feed"] = settings.ALPACA_FEED
        query = urlencode({k: v for k, v in params.items() if v is not None}, doseq=True)
        url = f"https://data.alpaca.markets{path}"
        if query:
            url = f"{url}?{query}"
        headers = {
            "APCA-API-KEY-ID": str(settings.ALPACA_API_KEY or ""),
            "APCA-API-SECRET-KEY": str(settings.ALPACA_SECRET_KEY or ""),
            "Accept": "application/json",
        }
        last_exc: Exception | None = None
        attempts = max(1, int(settings.ALPACA_HTTP_RETRIES))
        timeout = float(settings.ALPACA_HTTP_TIMEOUT_SECONDS)
        backoff = max(0.0, float(settings.ALPACA_HTTP_RETRY_BACKOFF_SECONDS))
        for attempt in range(1, attempts + 1):
            try:
                with _without_proxy_env():
                    response = requests.get(
                        url,
                        headers=headers,
                        timeout=timeout,
                    )
                response.raise_for_status()
                return response.json()
            except requests.RequestException as exc:
                last_exc = exc
                if attempt >= attempts:
                    break
                if backoff > 0:
                    time.sleep(backoff * attempt)
        if last_exc is not None:
            raise last_exc
        raise RuntimeError(f"alpaca_request_failed:{path}")

    def _yf_bars(self, symbol: str, bars: int) -> pd.DataFrame:
        try:
            import yfinance as yf

            ticker = yf.Ticker(symbol)
            df = ticker.history(period="1y", interval="1d")
            if df.empty:
                df = ticker.history(period="6mo", interval="1d")
            df = df.tail(bars).reset_index()
            df.columns = [c[0] if isinstance(c, tuple) else c for c in df.columns]
            df = df.rename(
                columns={
                    "Date": "ts",
                    "Open": "open",
                    "High": "high",
                    "Low": "low",
                    "Close": "close",
                    "Volume": "volume",
                }
            )
            return df
        except Exception as exc:
            print(f"yfinance bars failed for {symbol}: {exc}")
            return _empty_history()


FEED = AlpacaRealtimeFeed()
