from app.fund.knowledge_graph import KnowledgeGraph


def test_knowledge_graph_ingests_and_queries_lineage():
    graph = KnowledgeGraph(enabled=True, persist=False, graphify_sync_enabled=False, max_events=100)
    first = graph.ingest(
        source="research_memory",
        event_type="research.report.stored",
        source_event_id="rep-1",
        run_id="run-1",
        agent_id="researcher-1",
        payload={
            "report_id": "rep-1",
            "asset_universe": ["AAPL", "MSFT"],
            "summary": "AAPL revision cycle improving.",
        },
    )
    second = graph.ingest(
        source="decision_ledger",
        event_type="decision_created",
        source_event_id="dec-evt-1",
        run_id="run-1",
        agent_id="trader-1",
        decision_id="decision-1",
        payload={"decision_id": "decision-1", "report_ids": ["rep-1"]},
    )
    assert first["event_id"] != second["event_id"]

    lineage = graph.lineage(run_id="run-1", report_id="rep-1", limit=50)
    event_types = {row["event_type"] for row in lineage}
    assert "research.report.stored" in event_types
    assert "decision_ledger.decision_created" in event_types


def test_knowledge_graph_deduplicates_source_event_ids():
    graph = KnowledgeGraph(enabled=True, persist=False, graphify_sync_enabled=False, max_events=100)
    first = graph.ingest(
        source="audit_log",
        event_type="execution.intent.processed",
        source_event_id="aevt-1",
        occurred_at="2026-01-01T00:00:00Z",
        run_id="run-1",
        decision_id="decision-1",
        payload={"status": "executed"},
    )
    second = graph.ingest(
        source="audit_log",
        event_type="execution.intent.processed",
        source_event_id="aevt-1",
        occurred_at="2026-01-01T00:00:00Z",
        run_id="run-1",
        decision_id="decision-1",
        payload={"status": "executed"},
    )
    assert first["event_id"] == second["event_id"]
    assert graph.stats()["event_count"] == 1


def test_knowledge_graph_namespace_policy_normalizes_event_types():
    graph = KnowledgeGraph(enabled=True, persist=False, graphify_sync_enabled=False, max_events=100)
    event = graph.ingest(
        source="task_bus",
        event_type="created",
        source_event_id="task-1",
        run_id="run-1",
        payload={"task_id": "task-1"},
    )
    assert event["event_type"] == "task_bus.created"
    rows = graph.list_events(limit=10, namespace="task_bus")
    assert len(rows) == 1


def test_knowledge_graph_reset_clears_events_and_storage(tmp_path):
    storage = tmp_path / "kb"
    graph = KnowledgeGraph(
        enabled=True,
        persist=True,
        storage_dir=str(storage),
        graphify_sync_enabled=False,
        max_events=100,
    )
    graph.ingest(
        source="development",
        event_type="development.seed",
        source_event_id="seed-1",
        run_id="run-seed-1",
        payload={"hello": "world"},
    )
    assert graph.stats()["event_count"] == 1
    assert (storage / "events.jsonl").exists()

    result = graph.reset(clear_storage=True)
    assert result["reset"] is True
    assert result["previous_event_count"] == 1
    assert graph.stats()["event_count"] == 0
    assert (storage / "events.jsonl").exists()
