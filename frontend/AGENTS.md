# Frontend Session Contract

Before coding in `frontend/`, run:

```bash
bash ../scripts/session-bootstrap.sh --work-dir .. --count-remaining
```

Then initialize frontend environment:

```bash
./init.sh
```

Rules:
- Work from local `codex/main`; do not leave frontend sessions on feature branches.
- Every frontend session must hand off through remote `origin/codex/main` so the next agent resumes from the same published dev state. Production `main` is not a Codex handoff target.
- Work one feature at a time from `../feature_list.json` (`passes: false` highest priority first).
- Never edit feature descriptions/steps; only flip `passes` after end-to-end browser verification.
- Keep `Dev_Logs.md` and KB ingestion in sync per `../DevViktor.md`.
- Run relevant frontend build/lint/test checks before commit.
- End the session with `bash ../scripts/session-handoff.sh --work-dir .. --commit-message "<summary>"`.
