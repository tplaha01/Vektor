# Long-Running Agent Workflow

This workflow is mandatory for all coding sessions in this repository and its sub-repos (`backend`, `frontend`).

## Session Bootstrap (every turn)

Before doing feature work, run:

```bash
bash ./scripts/session-bootstrap.sh --count-remaining
```

This enforces:
1. `pwd`
2. concise file listing (head-limited)
3. spec read head (`app_spec.txt`)
4. features head read (`feature_list.json`)
5. progress head read (`codex-progress.txt`)
6. recent git log
7. branch + handoff status (`codex/main` vs `origin/codex/main`, dirty tree, ahead/behind)
8. remaining test count

The bootstrap defaults are intentionally head-limited to reduce token usage per turn while preserving bearings needed for safe execution.

## Feature Selection Rule

Choose the highest-priority feature with `passes: false` and complete one feature fully before moving on.

Helper:

```bash
bash ./scripts/select-next-feature.sh
```

## Prompt Assets

- Initializer prompt: `.codex/prompts/initializer_prompt.md`
- Coding prompt: `.codex/prompts/coding_agent_prompt.md`

## Multi-Agent / RAG Pipeline

- Use `planner` for read-only decomposition.
- Use `executor` for implementation and tests.
- Use subagent boundaries to keep retrieval scoped to only the files relevant to the active feature.
- Keep `knowledge_graph/` and `Dev_Logs.md` in sync per `DevViktor.md`.
- Refresh index after completion:

```bash
bash ./scripts/index-repo.sh
```

## Branching and Push Discipline

- The only long-running local Codex branch is `codex/main`.
- The only long-running remote handoff target is `origin/codex/main`.
- `main` is production and must not receive Codex handoff pushes.
- Do not leave work on feature branches between agents. If a session starts elsewhere, move the final state onto `codex/main` before ending the session.
- Every coding session must end by running:

```bash
bash ./scripts/session-handoff.sh --commit-message "<summary>"
```

- A handoff is complete only when all of the following are true:
  - the new commit exists on local `codex/main`
  - `origin/codex/main` matches local `HEAD`
  - `git status --short` is empty
  - `codex-progress.txt`, `Dev_Logs.md`, KB ingestion, and validation evidence are current
- The next agent always resumes from `codex/main`.

## Sub-repo Environment Setup

Each coding surface has a local init script:

- root: `./init.sh`
- backend: `./backend/init.sh`
- frontend: `./frontend/init.sh`

Use the local script inside that directory before feature work.
