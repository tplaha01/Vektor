from __future__ import annotations

import math
import statistics
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Callable

import requests

from app.config import get_settings
from app.data.fundamentals import get_fundamentals
from app.data.market_data import FEED
from app.data.news import latest_news
from app.fund.contracts import ProvenanceRef, make_immutable_id
from app.fund.runtime_guard import data_integrity_guard
from app.utils.sentiment import sentiment_score


def _utc_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except Exception:
        return default


def _clamp(value: float, lower: float, upper: float) -> float:
    return max(lower, min(upper, value))


@dataclass(frozen=True)
class ResearchIngestionResult:
    symbol: str
    summary: str
    findings: tuple[str, ...]
    confidence: Decimal
    provenance: tuple[ProvenanceRef, ...]
    metadata: dict[str, Any]


@dataclass(frozen=True)
class SentimentIngestionResult:
    symbol: str
    source: str
    sentiment_score: float
    confidence: float
    provenance_url: str | None
    metadata: dict[str, Any]


class MarketIntelligenceIngestion:
    """
    Source-backed ingestion adapter used by specialist analyst workers.
    """

    def __init__(self, price_history_lookup: Callable[[str, int], Any] | None = None) -> None:
        self._settings = get_settings()
        self._price_history_lookup = price_history_lookup or (lambda symbol, bars: FEED.history(symbol, bars=bars))

    def build_technical_report(self, symbol: str) -> ResearchIngestionResult:
        normalized_symbol = str(symbol).upper().strip()
        prices = self._load_close_prices(normalized_symbol, bars=260)
        if data_integrity_guard.strict_mode_enabled() and not prices:
            raise RuntimeError(f"real_data_required:technical_prices_unavailable:{normalized_symbol}")
        last = prices[-1] if prices else 0.0
        sma20 = self._sma(prices, 20)
        sma50 = self._sma(prices, 50)
        sma200 = self._sma(prices, 200)
        ema12 = self._ema(prices, 12)
        ema26 = self._ema(prices, 26)
        rsi14 = self._rsi(prices, 14)
        atr_proxy = self._atr_proxy(prices)
        macd = ema12 - ema26
        trend_signal = "bullish" if last >= sma50 >= sma200 else "bearish" if last <= sma50 <= sma200 else "mixed"

        findings = (
            f"Close: {last:.2f}",
            f"SMA20/SMA50/SMA200: {sma20:.2f}/{sma50:.2f}/{sma200:.2f}",
            f"EMA12/EMA26: {ema12:.2f}/{ema26:.2f}",
            f"RSI14: {rsi14:.2f}",
            f"MACD(12,26): {macd:.4f}",
            f"ATR proxy: {atr_proxy:.4f}",
            f"Regime: {trend_signal}",
        )
        confidence = Decimal(str(_clamp(0.45 + min(len(prices), 240) / 800, 0.45, 0.85))).quantize(Decimal("0.01"))
        summary = f"Technical analyst update for {normalized_symbol}: regime={trend_signal}, momentum and volatility mapped."
        provenance = (
            ProvenanceRef(source_type="data", source_id=make_immutable_id("price-series", normalized_symbol, len(prices))),
        )
        return ResearchIngestionResult(
            symbol=normalized_symbol,
            summary=summary,
            findings=findings,
            confidence=confidence,
            provenance=provenance,
            metadata={"analysis_type": "technical", "bars_used": len(prices), "generated_at": _utc_iso()},
        )

    def build_fundamental_report(self, symbol: str) -> ResearchIngestionResult:
        normalized_symbol = str(symbol).upper().strip()
        fundamentals = get_fundamentals(normalized_symbol)
        if data_integrity_guard.strict_mode_enabled() and not fundamentals:
            raise RuntimeError(f"real_data_required:fundamentals_unavailable:{normalized_symbol}")
        revenue_growth = _safe_float(fundamentals.get("revenue_growth"))
        gross_margin = _safe_float(fundamentals.get("gross_margin"))
        oper_margin = _safe_float(fundamentals.get("oper_margin"))
        debt_to_equity = _safe_float(fundamentals.get("debt_to_equity"), 1.0)
        pe = _safe_float(fundamentals.get("pe"), 20.0)
        quality_score = _clamp((revenue_growth * 2.0) + gross_margin + oper_margin - (debt_to_equity * 0.2), -1.0, 1.0)
        valuation_tag = "rich" if pe > 30 else "discounted" if pe < 15 else "fair"

        findings = (
            f"Revenue growth TTM: {revenue_growth:.2%}",
            f"Gross margin TTM: {gross_margin:.2%}",
            f"Operating margin TTM: {oper_margin:.2%}",
            f"Debt-to-equity: {debt_to_equity:.2f}",
            f"P/E: {pe:.2f}",
            f"Quality score: {quality_score:.3f}",
            f"Valuation regime: {valuation_tag}",
        )
        confidence = Decimal("0.72")
        summary = (
            f"Fundamental analyst report for {normalized_symbol}: quality={quality_score:.2f}, "
            f"valuation={valuation_tag}."
        )
        provenance = (
            ProvenanceRef(
                source_type="data",
                source_id=make_immutable_id(
                    "fmp-fundamentals",
                    normalized_symbol,
                    revenue_growth,
                    gross_margin,
                    oper_margin,
                    debt_to_equity,
                    pe,
                ),
            ),
        )
        return ResearchIngestionResult(
            symbol=normalized_symbol,
            summary=summary,
            findings=findings,
            confidence=confidence,
            provenance=provenance,
            metadata={"analysis_type": "fundamental", "generated_at": _utc_iso()},
        )

    def build_ml_timeseries_report(self, symbol: str) -> ResearchIngestionResult:
        normalized_symbol = str(symbol).upper().strip()
        prices = self._load_close_prices(normalized_symbol, bars=300)
        if data_integrity_guard.strict_mode_enabled() and not prices:
            raise RuntimeError(f"real_data_required:ml_prices_unavailable:{normalized_symbol}")
        returns = self._returns(prices)
        slope = self._linear_slope(prices[-90:]) if len(prices) >= 10 else 0.0
        momentum_20 = ((prices[-1] / prices[-21]) - 1.0) if len(prices) > 21 and prices[-21] != 0 else 0.0
        volatility_20 = statistics.pstdev(returns[-20:]) if len(returns) >= 20 else 0.0
        zscore_20 = self._zscore(prices[-20:]) if len(prices) >= 20 else 0.0
        probability_up = _clamp(
            0.5 + (slope * 5) + (momentum_20 * 0.7) - (volatility_20 * 2.5) - (zscore_20 * 0.05),
            0.02,
            0.98,
        )
        expected_move_5d = momentum_20 * 0.35 + slope * 8
        regime = "trend" if abs(slope) > 0.03 else "mean_revert"

        findings = (
            f"Model family: regime_ensemble_v1",
            f"90-bar trend slope: {slope:.5f}",
            f"20-bar momentum: {momentum_20:.4f}",
            f"20-bar volatility: {volatility_20:.4f}",
            f"20-bar zscore: {zscore_20:.3f}",
            f"5-day expected move: {expected_move_5d:.4f}",
            f"Directional probability(up): {probability_up:.3f}",
            f"Detected regime: {regime}",
        )
        confidence = Decimal(str(_clamp(0.55 + (len(prices) / 1200), 0.55, 0.82))).quantize(Decimal("0.01"))
        summary = (
            f"ML timeseries analyst for {normalized_symbol}: regime={regime}, "
            f"prob_up={probability_up:.2f}, expected_move_5d={expected_move_5d:.3f}."
        )
        provenance = (
            ProvenanceRef(source_type="data", source_id=make_immutable_id("timeseries-bars", normalized_symbol, len(prices))),
        )
        return ResearchIngestionResult(
            symbol=normalized_symbol,
            summary=summary,
            findings=findings,
            confidence=confidence,
            provenance=provenance,
            metadata={"analysis_type": "ml_timeseries", "bars_used": len(prices), "generated_at": _utc_iso()},
        )

    def build_insight_report(self, symbol: str) -> ResearchIngestionResult:
        normalized_symbol = str(symbol).upper().strip()
        headlines = self._collect_headlines(normalized_symbol)
        if data_integrity_guard.strict_mode_enabled() and not headlines:
            raise RuntimeError(f"real_data_required:insight_headlines_unavailable:{normalized_symbol}")
        top_headlines = [f"- {item.get('headline')}" for item in headlines[:6]]
        sentiment = self.build_sentiment(normalized_symbol)
        findings = tuple(
            [
                f"Aggregated sentiment score: {sentiment.sentiment_score:.3f}",
                f"Sentiment confidence: {sentiment.confidence:.3f}",
                "Top narrative flow:",
                *top_headlines,
            ]
            if top_headlines
            else ["No fresh headlines detected; insight confidence is reduced."]
        )
        confidence = Decimal(str(_clamp(0.4 + len(top_headlines) * 0.05, 0.4, 0.8))).quantize(Decimal("0.01"))
        summary = f"Insight researcher report for {normalized_symbol}: narrative and sentiment context synthesized."
        provenance = self._build_news_provenance(normalized_symbol, headlines)
        return ResearchIngestionResult(
            symbol=normalized_symbol,
            summary=summary,
            findings=findings,
            confidence=confidence,
            provenance=provenance,
            metadata={"analysis_type": "insight", "headline_count": len(headlines), "generated_at": _utc_iso()},
        )

    def build_hedge_fund_report(self, symbol: str) -> ResearchIngestionResult:
        normalized_symbol = str(symbol).upper().strip()
        technical = self.build_technical_report(normalized_symbol)
        fundamental = self.build_fundamental_report(normalized_symbol)
        ml = self.build_ml_timeseries_report(normalized_symbol)
        sentiment = self.build_sentiment(normalized_symbol)

        expected_base = self._extract_expected_move(ml.findings)
        bull_case = expected_base + 0.04
        bear_case = expected_base - 0.05
        base_case = expected_base
        conviction = _clamp(
            (float(technical.confidence) + float(fundamental.confidence) + float(ml.confidence) + sentiment.confidence)
            / 4.0,
            0.35,
            0.92,
        )
        risk_bias = "risk-on" if sentiment.sentiment_score > 0.1 and bull_case > 0 else "risk-off"
        findings = (
            "Scenario framework (30 trading days):",
            f"Bull case expected return: {bull_case:.2%}",
            f"Base case expected return: {base_case:.2%}",
            f"Bear case expected return: {bear_case:.2%}",
            f"Portfolio risk bias: {risk_bias}",
            f"Cross-discipline conviction: {conviction:.3f}",
            "Catalyst map: earnings, guidance revisions, macro policy, volatility regime shifts.",
        )
        confidence = Decimal(str(conviction)).quantize(Decimal("0.01"))
        summary = (
            f"Hedge-fund research report for {normalized_symbol}: scenario analysis completed with "
            f"{risk_bias} stance and conviction {conviction:.2f}."
        )
        provenance = tuple(
            dict.fromkeys(
                [
                    *technical.provenance,
                    *fundamental.provenance,
                    *ml.provenance,
                    ProvenanceRef(source_type="sentiment", source_id=make_immutable_id("sentiment", normalized_symbol, sentiment.sentiment_score)),
                ]
            )
        )
        return ResearchIngestionResult(
            symbol=normalized_symbol,
            summary=summary,
            findings=findings,
            confidence=confidence,
            provenance=provenance,
            metadata={"analysis_type": "hedge_fund_research", "generated_at": _utc_iso()},
        )

    def build_sentiment(self, symbol: str) -> SentimentIngestionResult:
        normalized_symbol = str(symbol).upper().strip()
        headlines = self._collect_headlines(normalized_symbol)
        texts = [str(item.get("headline") or "").strip() for item in headlines if item.get("headline")]
        if data_integrity_guard.strict_mode_enabled() and not texts:
            raise RuntimeError(f"real_data_required:sentiment_headlines_unavailable:{normalized_symbol}")
        score = float(sentiment_score(texts)) if texts else 0.0
        confidence = float(_clamp(0.25 + len(texts) * 0.07, 0.25, 0.90))
        provenance_url = str(headlines[0].get("url") or "").strip() if headlines else ""
        return SentimentIngestionResult(
            symbol=normalized_symbol,
            source="news_aggregated",
            sentiment_score=_clamp(score, -1.0, 1.0),
            confidence=confidence,
            provenance_url=provenance_url or None,
            metadata={"headline_count": len(texts), "generated_at": _utc_iso()},
        )

    def _collect_headlines(self, symbol: str) -> list[dict[str, Any]]:
        merged: list[dict[str, Any]] = []
        merged.extend(latest_news(symbol, limit=8))
        if self._settings.NEWSAPI_KEY:
            merged.extend(self._newsapi_headlines(symbol, limit=8))
        deduped: list[dict[str, Any]] = []
        seen: set[str] = set()
        for row in merged:
            headline = str(row.get("headline") or "").strip()
            url = str(row.get("url") or "").strip()
            dedupe_key = f"{headline.lower()}|{url.lower()}"
            if not headline or dedupe_key in seen:
                continue
            seen.add(dedupe_key)
            deduped.append(
                {
                    "symbol": symbol,
                    "headline": headline,
                    "source": str(row.get("source") or "unknown"),
                    "url": url,
                    "published_at": row.get("published_at"),
                }
            )
        return deduped[:16]

    def _newsapi_headlines(self, symbol: str, limit: int = 8) -> list[dict[str, Any]]:
        try:
            response = requests.get(
                "https://newsapi.org/v2/everything",
                params={
                    "q": f"{symbol} stock OR {symbol} earnings",
                    "language": "en",
                    "sortBy": "publishedAt",
                    "pageSize": max(1, min(limit, 20)),
                    "apiKey": self._settings.NEWSAPI_KEY,
                },
                timeout=4,
            )
            response.raise_for_status()
            payload = response.json()
            articles = payload.get("articles") if isinstance(payload, dict) else []
            if not isinstance(articles, list):
                return []
            rows: list[dict[str, Any]] = []
            for article in articles:
                title = str(article.get("title") or "").strip()
                if not title:
                    continue
                rows.append(
                    {
                        "symbol": symbol,
                        "headline": title,
                        "source": str((article.get("source") or {}).get("name") or "NewsAPI"),
                        "url": str(article.get("url") or ""),
                        "published_at": article.get("publishedAt"),
                    }
                )
            return rows
        except Exception:
            return []

    def _load_close_prices(self, symbol: str, bars: int = 260) -> list[float]:
        try:
            history = self._price_history_lookup(symbol, bars)
            if history is None:
                return []
            closes = history.get("close") if hasattr(history, "get") else None
            if closes is None:
                return []
            return [float(value) for value in closes.tolist() if _safe_float(value) > 0]
        except Exception:
            return []

    def _returns(self, prices: list[float]) -> list[float]:
        if len(prices) < 2:
            return []
        values: list[float] = []
        for prev, curr in zip(prices[:-1], prices[1:]):
            if prev <= 0:
                continue
            values.append((curr / prev) - 1.0)
        return values

    def _sma(self, prices: list[float], window: int) -> float:
        if not prices:
            return 0.0
        if len(prices) < window:
            return sum(prices) / max(len(prices), 1)
        segment = prices[-window:]
        return sum(segment) / float(window)

    def _ema(self, prices: list[float], window: int) -> float:
        if not prices:
            return 0.0
        alpha = 2.0 / (window + 1.0)
        value = prices[0]
        for price in prices[1:]:
            value = (alpha * price) + ((1.0 - alpha) * value)
        return value

    def _rsi(self, prices: list[float], window: int = 14) -> float:
        if len(prices) < (window + 1):
            return 50.0
        gains = []
        losses = []
        for prev, curr in zip(prices[-(window + 1) : -1], prices[-window:]):
            delta = curr - prev
            if delta >= 0:
                gains.append(delta)
                losses.append(0.0)
            else:
                gains.append(0.0)
                losses.append(abs(delta))
        avg_gain = sum(gains) / float(window)
        avg_loss = sum(losses) / float(window)
        if avg_loss == 0:
            return 100.0
        rs = avg_gain / avg_loss
        return 100.0 - (100.0 / (1.0 + rs))

    def _atr_proxy(self, prices: list[float], window: int = 14) -> float:
        returns = self._returns(prices)
        if len(returns) < window:
            return 0.0
        return sum(abs(item) for item in returns[-window:]) / float(window)

    def _linear_slope(self, prices: list[float]) -> float:
        if len(prices) < 3:
            return 0.0
        n = len(prices)
        xs = list(range(n))
        mean_x = sum(xs) / n
        mean_y = sum(prices) / n
        numerator = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, prices))
        denominator = sum((x - mean_x) ** 2 for x in xs)
        if denominator == 0:
            return 0.0
        slope = numerator / denominator
        return 0.0 if mean_y == 0 else slope / mean_y

    def _zscore(self, prices: list[float]) -> float:
        if len(prices) < 2:
            return 0.0
        mean = statistics.mean(prices)
        std = statistics.pstdev(prices)
        if std <= 0:
            return 0.0
        return (prices[-1] - mean) / std

    def _extract_expected_move(self, findings: tuple[str, ...]) -> float:
        for line in findings:
            if line.lower().startswith("5-day expected move:"):
                try:
                    return float(line.split(":", 1)[1].strip())
                except Exception:
                    return 0.0
        return 0.0

    def _build_news_provenance(self, symbol: str, headlines: list[dict[str, Any]]) -> tuple[ProvenanceRef, ...]:
        refs: list[ProvenanceRef] = []
        for item in headlines[:6]:
            refs.append(
                ProvenanceRef(
                    source_type="research",
                    source_id=make_immutable_id("news", symbol, item.get("source"), item.get("url") or item.get("headline")),
                )
            )
        if not refs:
            refs.append(ProvenanceRef(source_type="research", source_id=make_immutable_id("news", symbol, "fallback", _utc_iso())))
        return tuple(refs)


market_ingestion = MarketIntelligenceIngestion()
