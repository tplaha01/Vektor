# TradingBot Codex Operating Contract

This repo uses a split Codex workflow:

1. `planner` agent
   - Use for read-only repo mapping, task decomposition, and risk analysis.
   - Keep planning cheap and concise.

2. `executor` agent
   - Use for code changes, tests, and validated implementation.
   - Keep execution focused and traceable.

Run hygiene:
- Every session must log `START` and `END` in `Dev_Logs.md`.
- Every session must ingest the same run into `knowledge_graph/`.
- Every completed run must refresh the codebase-memory index with `scripts/index-repo.ps1`.
- Prefer the indexed graph before file-by-file searching when tracing the codebase.

Source of truth:
- `DevViktor.md`
- `docs/AI_NATIVE_HEDGE_FUND_AUDIT_AND_ROADMAP.md`
- `.codex/config.toml`
