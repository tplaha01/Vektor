# Automatic Dev Log Tracking and Repo Knowledge Base Integration

The backend now logs sessions to repository memory in alignment with `DevViktor.md`.

## What Is Implemented

1. Automatic session logging
- Backend startup writes a `START` entry to `Dev_Logs.md`.
- Backend shutdown writes an `END` entry to `Dev_Logs.md`.
- Entries follow the structured template from `DevViktor.md`.
- Each session gets a unique `run_id`.

2. Repo knowledge-base integration
- Log entries are written to `knowledge_graph/events.jsonl`.
- Namespace: `development`.
- Captured fields include actor identity, platform, model, branch, commits, scope, files, validation, and notes.

3. Git tracking
- Captures current git branch.
- Records `git_commit_start` at startup.
- Records `git_commit_end` at shutdown.

4. Backend ingestion endpoint
- `POST /fund/knowledge/development/log`

5. Monitoring integration
- Startup output includes devlog initialization details.

## Entry Format

```text
[2026-04-17T12:30:45.123456Z] [START]
entry_id: devlog-20260417-a1b2c3d4
actor_name: codex
actor_platform: codex
actor_model: gpt-5
actor_provider: openai
run_id: run-a1b2c3d4e5f6g7h8
git_branch: main
git_commit_start: 5a6b7c8d9e0f1a2b3c4d5e6f
git_commit_end:
scope: Backend server runtime operations
files:
- backend/app/main.py
- backend/app/monitoring.py
- backend/app/devlog.py
validation: in_progress
notes: Automated session start on server boot
```

## Architecture Flow

```text
Backend Startup
  -> create_dev_session()
  -> append START to Dev_Logs.md
  -> append START event to knowledge_graph/events.jsonl

Backend Shutdown
  -> complete_dev_session()
  -> append END to Dev_Logs.md
  -> append END event to knowledge_graph/events.jsonl
```

## Querying Sessions

1. Local file inspection
- `Get-Content Dev_Logs.md -Tail 100`

2. Repo KB inspection
- `Get-Content knowledge_graph/events.jsonl -Tail 20`

3. Backend API (when running)
- `GET /fund/knowledge/stats`
- `GET /fund/knowledge/events?namespace=development&limit=50`

## Captured Metadata

| Field | Captured | Example |
|---|---|---|
| `entry_id` | Auto-generated | `devlog-20260417-a1b2c3d4` |
| `run_id` | Auto-generated | `run-a1b2c3d4e5f6g7h8` |
| `timestamp` | Auto-generated | `2026-04-17T12:30:45Z` |
| `git_branch` | Auto-captured | `main` |
| `git_commit_start` | Auto-captured | SHA |
| `git_commit_end` | Auto-captured on END | SHA |
| `actor_name` | Configured | `codex` |
| `actor_platform` | Configured | `codex` |
| `actor_model` | Configured | `gpt-5` |
| `actor_provider` | Configured | `openai` |
| `scope` | Set by caller | Runtime scope text |
| `files` | Set by caller | Changed file list |
| `validation` | Set by caller | `in_progress` / `passed` |
| `notes` | Set by caller | Session notes |

## Integration Checklist

- START/END entries are append-only.
- START/END entries are mirrored into `knowledge_graph/events.jsonl`.
- Entries are queryable by namespace and lineage fields.
- Offline fallback works through direct file writes even when backend API is unavailable.
