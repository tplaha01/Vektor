# DevViktor: Engineering Execution Contract

This file is code-delivery governance only.
Product vision, business goals, and role architecture live in `Viktor.md`.

## 1) Boot Sequence (Mandatory)
0. Run mandatory session bearings bootstrap:
   - `powershell -ExecutionPolicy Bypass -File scripts/session-bootstrap.ps1 -CountRemaining`
   - If files are missing (`app_spec.txt`, `feature_list.json`, `codex-progress.txt`), stop feature work and restore initializer baseline first.
1. Read `Viktor.md`.
2. Read `docs/VEKTOR_PHASED_EXECUTION_PLAN.md`.
2. Read `Dev_Logs.md`.
3. Append `START` entry in `Dev_Logs.md`.
4. Capture baseline state:
   - `GET /fund/knowledge/stats`
   - `GET /fund/knowledge/events?limit=200&namespace=development`
   - `GET /fund/agents/workers/status`
5. Confirm repo KB location:
   - `knowledge_graph/` at repository root is the canonical development memory store.

## 2) Coding Rules
- Preserve paper-trading safety; no live trading activation.
- Keep API compatibility during migration unless explicitly versioned.
- Every non-trivial behavior change requires test updates.
- Keep decisions traceable (`run_id`, `agent_id`, `decision_id`, `order_id` where applicable).
- Do not bypass policy gates, sleeve budgets, or audit logging paths.
- Tests must not mutate repo runtime state: when exercising singleton services (for example `knowledge_graph`), monkeypatch ingest/persistence or use isolated storage.
- For long-running staged development, select the highest-priority pending feature from `feature_list.json` and complete one unit fully before moving to the next.

## 3) Branch and Commit Discipline
- Long-running Codex sessions must work on local `codex/main` only.
- `codex/main` is the canonical local handoff branch and must be kept aligned with `origin/main`.
- End every coding session with a commit on `codex/main`, then push that commit to `origin/main` using `scripts/session-handoff.ps1`.
- A session is incomplete if `git status --short` is non-empty or if local `codex/main` and `origin/main` differ.
- Log `git_branch`, `git_commit_start`, and `git_commit_end` in `Dev_Logs.md`.
- Keep commits migration-safe and reversible.

## 4) Dev Log Requirement (Mandatory)
Every session must append both `START` and `END` in `Dev_Logs.md` using the uniform schema defined there.

Minimum required fields per entry:
- `actor_platform`
- `actor_model`
- `actor_provider`
- `git_branch`
- `git_commit_start`
- `git_commit_end` (for END)
- `run_id`
- `scope`
- `active_phase`
- `files`
- `validation`
- `notes`

Hard requirement:
- Every session must explicitly state which execution phase it advances.
- If the work does not materially advance the active phase defined in `docs/VEKTOR_PHASED_EXECUTION_PLAN.md`, it should not be done in that session.

## 5) Graphify Requirement (Mandatory)
Every `START` and `END` dev-log entry must also be sent to the KB:
- `POST /fund/knowledge/development/log`

This writes namespaced `development.devlog.*` events so cross-model work becomes queryable memory.

Hard requirement:
- If a session is not written to repo KB, that session is non-compliant and incomplete.
- Every model must verify ingestion by querying:
  - `GET /fund/knowledge/events?namespace=development&limit=50`
  and confirming its `entry_id` appears.

Offline fallback (if backend API is unavailable):
- Write a direct development event to repo KB using local Python and `KnowledgeGraph(storage_dir=\"../knowledge_graph\")` from `backend/`.
- Then, once backend is available, replay the same entry via `/fund/knowledge/development/log` to keep API-visible lineage consistent.

## 6) Codex Agent Split (Mandatory)
- Use the low-cost `planner` agent for read-only repo mapping, task decomposition, and risk review.
- Use the higher-cost `executor` agent for actual file edits, tests, and implementation.
- Do not ask the executor to do planning-only work when the planner can answer it cheaply.
- Prefer a small, explicit plan before any non-trivial implementation.

## 7) Validation and Exit
Before ending a session:
1. Run backend tests or focused tests for changed modules.
2. Run frontend/build checks if UI code changed.
3. Append `END` entry in `Dev_Logs.md`.
4. Ingest `END` entry to KB via `/fund/knowledge/development/log`.
5. Verify `END` entry exists in repo KB query results.
6. Refresh the codebase-memory graph with `scripts/index-repo.ps1`.
7. Verify the repo appears in the graph registry after indexing.
8. Run `scripts/session-handoff.ps1 -CommitMessage "<summary>"` from `codex/main`.
