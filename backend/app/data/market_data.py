from __future__ import annotations
import threading
import time
from datetime import datetime, timedelta
from typing import Dict, Callable, List
import pandas as pd

from app.config import get_settings

settings = get_settings()

# Price cache: symbol -> (price, timestamp)
_price_cache: Dict[str, tuple[float, float]] = {}
_CACHE_TTL = 30.0  # seconds


class AlpacaRealtimeFeed:
    def __init__(self):
        self._prices: Dict[str, float] = {}
        self._subscribers: List[Callable] = []
        self._started = False

    def price(self, symbol: str) -> float:
        # 1. Use streaming price if available and fresh
        if symbol in self._prices and self._prices[symbol] > 0:
            return self._prices[symbol]

        # 2. Check cache
        now = time.time()
        if symbol in _price_cache:
            px, ts = _price_cache[symbol]
            if now - ts < _CACHE_TTL and px > 0:
                return px

        # 3. Try Alpaca latest quote/bar
        if settings.ALPACA_API_KEY:
            try:
                px = self._alpaca_latest_price(symbol)
                if px > 0:
                    self._prices[symbol] = px
                    _price_cache[symbol] = (px, now)
                    return px
            except Exception as e:
                print(f"⚠️ Alpaca price failed for {symbol}: {e}")

        # 4. Last known price from cache (stale but better than 0)
        if symbol in _price_cache and _price_cache[symbol][0] > 0:
            return _price_cache[symbol][0]

        return self._prices.get(symbol, 0.0)

    def history(self, symbol: str, bars: int = 200) -> pd.DataFrame:
        if settings.ALPACA_API_KEY:
            try:
                return self._alpaca_bars(symbol, bars)
            except Exception as e:
                print(f"⚠️ Alpaca bars failed for {symbol}: {e}")
        # yfinance only as last resort for history
        return self._yf_bars(symbol, bars)

    def subscribe(self, callback: Callable):
        self._subscribers.append(callback)

    def start_stream(self, symbols: List[str]):
        if self._started or not settings.ALPACA_API_KEY:
            if not settings.ALPACA_API_KEY:
                print("ℹ️  No ALPACA_API_KEY — using Alpaca REST polling")
            return
        self._started = True
        t = threading.Thread(
            target=self._run_stream,
            args=(symbols,),
            daemon=True,
            name="alpaca-ws-feed",
        )
        t.start()
        print(f"🚀 Alpaca real-time stream started for {symbols}")

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
                _price_cache[sym] = (px, time.time())
                for cb in self._subscribers:
                    try:
                        cb(sym, px)
                    except Exception:
                        pass

            stream.subscribe_trades(_on_trade, *symbols)
            stream.run()

        except Exception as e:
            print(f"⚠️ Alpaca stream error: {e} — falling back to REST polling")
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
        df = df.rename(columns={
            "timestamp": "ts", "open": "open", "high": "high",
            "low": "low", "close": "close", "volume": "volume",
        })
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
            df = df.rename(columns={
                "Date": "ts", "Open": "open", "High": "high",
                "Low": "low", "Close": "close", "Volume": "volume",
            })
            return df
        except Exception as e:
            print(f"⚠️ yfinance bars failed for {symbol}: {e}")
            return pd.DataFrame(columns=["ts", "open", "high", "low", "close", "volume"])


FEED = AlpacaRealtimeFeed()