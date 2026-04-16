from decimal import Decimal

from app.fund.contracts import ExecutionIntent, ProvenanceRef, ResearchReport, Sleeve, make_immutable_id


def test_make_immutable_id_is_deterministic():
    first = make_immutable_id("decision", "run-1", "aapl", "buy", 10)
    second = make_immutable_id("decision", "run-1", "aapl", "buy", 10)
    assert first == second
    assert first.startswith("decision_")


def test_research_report_normalizes_assets_and_keeps_trace_fields():
    report = ResearchReport(
        run_id="run-1",
        agent_id="researcher-1",
        summary="AAPL thesis",
        findings=("AAPL margin expansion",),
        confidence=Decimal("0.72"),
        asset_universe=("aapl", "AAPL", "msft"),
        provenance=(
            ProvenanceRef(source_type="data", source_id="data-1"),
            ProvenanceRef(source_type="sentiment", source_id="sent-1"),
        ),
    )
    assert report.asset_universe == ("AAPL", "MSFT")
    assert report.provenance[0].source_id == "data-1"


def test_execution_intent_enforces_uppercase_symbol_and_positive_notional():
    intent = ExecutionIntent(
        decision_id="decision-1",
        sleeve=Sleeve.TACTICAL,
        symbol="aapl",
        side="buy",
        notional_usd=Decimal("5000"),
    )
    assert intent.symbol == "AAPL"
