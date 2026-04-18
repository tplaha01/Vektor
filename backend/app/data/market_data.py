from __future__ import annotations

import threading
import time
import os
from datetime import datetime, timedelta
from typing import Callable, Dict, List

import pandas as pd

from app.config import get_settings
from app.fund.runtime_guard import DataMode, data_integrity_guard

settings = get_settings()


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

            async def _on_trade(trade):
                sym = trade.symbol
                px = float(trade.price)
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
                        cb(sym, px)
                    except Exception:
                        pass

            stream.subscribe_trades(_on_trade, *symbols)
            stream.run()

        except Exception as exc:
            print(f"Alpaca stream error: {exc} - falling back to REST polling")
            data_integrity_guard.record_provider_event(
                provider="alpaca_stream",
                mode="failed",
                detail=f"stream_error:{exc}",
            )
            self._started = False

    def _alpaca_latest_price(self, symbol: str) -> float:
        from alpaca.data.historical import StockHistoricalDataClient
        from alpaca.data.requests import StockLatestTradeRequest

        client = StockHistoricalDataClient(
            settings.ALPACA_API_KEY,
            settings.ALPACA_SECRET_KEY,
        )
        req = StockLatestTradeRequest(symbol_or_symbols=symbol)
        resp = client.get_stock_latest_trade(req)
        if symbol in resp:
            return float(resp[symbol].price)
        return 0.0

    def _alpaca_bars(self, symbol: str, bars: int) -> pd.DataFrame:
        from alpaca.data.historical import StockHistoricalDataClient
        from alpaca.data.requests import StockBarsRequest
        from alpaca.data.timeframe import TimeFrame

        client = StockHistoricalDataClient(
            settings.ALPACA_API_KEY,
            settings.ALPACA_SECRET_KEY,
        )
        req = StockBarsRequest(
            symbol_or_symbols=symbol,
            timeframe=TimeFrame.Day,
            start=datetime.utcnow() - timedelta(days=bars * 2),
        )
        df = client.get_stock_bars(req).df
        if isinstance(df.index, pd.MultiIndex):
            df = df.xs(symbol, level="symbol")
        df = df.reset_index()
        df.columns = [c[0] if isinstance(c, tuple) else c for c in df.columns]
        df = df.rename(
            columns={
                "timestamp": "ts",
                "open": "open",
                "high": "high",
                "low": "low",
                "close": "close",
                "volume": "volume",
            }
        )
        return df.tail(bars).reset_index(drop=True)

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
