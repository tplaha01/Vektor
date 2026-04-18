from app.fund.ingestion_adapters import MarketIntelligenceIngestion


def test_market_ingestion_builds_source_backed_research_and_sentiment():
    adapter = MarketIntelligenceIngestion()

    technical = adapter.build_technical_report("AAPL")
    assert technical.symbol == "AAPL"
    assert len(technical.findings) > 0

    fundamental = adapter.build_fundamental_report("AAPL")
    assert fundamental.symbol == "AAPL"
    assert len(fundamental.findings) > 0

    ml = adapter.build_ml_timeseries_report("AAPL")
    assert ml.symbol == "AAPL"
    assert len(ml.findings) > 0

    insight = adapter.build_insight_report("AAPL")
    assert insight.symbol == "AAPL"
    assert insight.summary
    assert len(insight.provenance) > 0

    sentiment = adapter.build_sentiment("AAPL")
    assert sentiment.symbol == "AAPL"
    assert -1 <= float(sentiment.sentiment_score) <= 1
    assert 0 <= float(sentiment.confidence) <= 1
