from __future__ import annotations
import threading
from datetime import datetime, timedelta
from typing import Dict, Callable, List
import pandas as pd
import yfinance as yf

from app.config import get_settings

settings = get_settings()


class AlpacaRealtimeFeed:
    def __init__(self):
        self._prices: Dict[str, float] = {}
        self._subscribers: List[Callable] = []
        self._started = False

    def price(self, symbol: str) -> float:
        if symbol in self._prices and self._prices[symbol] > 0:
            return self._prices[symbol]
        return self._yf_price(symbol)

    def history(self, symbol: str, bars: int = 200) -> pd.DataFrame:
        if settings.ALPACA_API_KEY:
            try:
                return self._alpaca_bars(symbol, bars)
            except Exception as e:
                print(f"⚠️ Alpaca bars failed for {symbol}: {e} — falling back to yfinance")
        return self._yf_bars(symbol, bars)

    def subscribe(self, callback: Callable):
        self._subscribers.append(callback)

    def start_stream(self, symbols: List[str]):
        if self._started or not settings.ALPACA_API_KEY:
            if not settings.ALPACA_API_KEY:
                print("ℹ️  No ALPACA_API_KEY — using yfinance polling fallback")
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

            # alpaca-py requires DataFeed enum, not a raw string
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
                for cb in self._subscribers:
                    try:
                        cb(sym, px)
                    except Exception:
                        pass

            stream.subscribe_trades(_on_trade, *symbols)
            stream.run()

        except Exception as e:
            print(f"⚠️ Alpaca stream error: {e} — using yfinance polling")
            self._started = False

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

    def _yf_price(self, symbol: str) -> float:
        try:
            ticker = yf.Ticker(symbol)
            px = ticker.fast_info.get("last_price") or ticker.fast_info.get("previousClose")
            if px:
                self._prices[symbol] = float(px)
                return float(px)
            # last resort — latest close from history
            hist = ticker.history(period="5d")
            if not hist.empty:
                px = float(hist["Close"].iloc[-1])
                self._prices[symbol] = px
                return px
        except Exception as e:
            print(f"⚠️ yfinance price failed for {symbol}: {e}")
        return self._prices.get(symbol, 0.0)


FEED = AlpacaRealtimeFeed()
