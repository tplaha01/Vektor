# Vektor Graphify Knowledge Graph

## What this adds

Vektor now emits a live knowledge event stream from:

- research memory
- sentiment ingest
- task bus
- decision ledger
- audit log
- OpenClaw ingest
- orchestrator milestones

Each event is indexed with run/agent/decision/order IDs and persisted under `knowledge_graph` (repo root by default).

## Files generated

- `knowledge_graph/events.jsonl`: append-only event log
- `knowledge_graph/events/*.md`: event notes
- `knowledge_graph/entities/*/*.md`: entity nodes (run IDs, decision IDs, report IDs, symbols, etc.)

## API inspection

- `GET /fund/knowledge/events`
- `GET /fund/knowledge/lineage`
- `GET /fund/knowledge/stats`
- `POST /fund/knowledge/reset`
- `POST /fund/knowledge/development/log`

Namespace policy is enforced for all events. Example namespaces:
- `development.*`
- `task_bus.*`
- `orchestrator.*`
- `decision_ledger.*`
- `audit_log.*`
- `openclaw.*`

Development log graphification:
- Write uniform entry in `Dev_Logs.md`.
- Send matching payload to `POST /fund/knowledge/development/log`.
- Query with:
  - `GET /fund/knowledge/events?namespace=development&limit=200`

## Env settings

Set these in `backend/.env`:

```env
KNOWLEDGE_GRAPH_ENABLED=true
KNOWLEDGE_GRAPH_DIR=knowledge_graph
KNOWLEDGE_GRAPH_MAX_EVENTS=50000
KNOWLEDGE_GRAPH_PERSIST=true
GRAPHIFY_SYNC_ENABLED=false
GRAPHIFY_SYNC_MIN_INTERVAL_SECONDS=30
GRAPHIFY_UPDATE_COMMAND=py -3 -m graphify update .
```

## Enabling live Graphify refresh

1. Keep `GRAPHIFY_SYNC_ENABLED=false` first and verify the API endpoints work.
2. Turn on `GRAPHIFY_SYNC_ENABLED=true`.
3. Restart backend.
4. Validate sync status:
   - `GET /fund/knowledge/stats` and check:
     - `graphify_sync_enabled: true`
     - `last_graphify_sync_status: ok`

## Notes

- This does not grant trading authority to OpenClaw or Graphify.
- Trade execution remains paper-only and policy-gated.
- Knowledge events survive backend restarts by replaying `events.jsonl` on boot.
