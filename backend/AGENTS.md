# Backend Session Contract

Before coding in `backend/`, run:

```bash
bash ../scripts/session-bootstrap.sh --work-dir .. --count-remaining
```

Then initialize backend environment:

```bash
./init.sh
```

Rules:
- Work from local `codex/main`; do not leave backend sessions on feature branches.
- Work one feature at a time from `../feature_list.json` (`passes: false` highest priority first).
- Never edit feature descriptions/steps; only flip `passes` after end-to-end verification.
- Keep `Dev_Logs.md` and KB ingestion in sync per `../DevViktor.md`.
- Run focused tests for changed backend behavior before commit.
- End the session with `bash ../scripts/session-handoff.sh --work-dir .. --commit-message "<summary>"`; this publishes to `origin/codex/main`, not production `main`.
