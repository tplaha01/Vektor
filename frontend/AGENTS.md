# Frontend Session Contract

Before coding in `frontend/`, run:

```powershell
..\scripts\session-bootstrap.ps1 -WorkDir .. -CountRemaining
```

Then initialize frontend environment:

```bash
./init.sh
```

Rules:
- Work from local `codex/main`; do not leave frontend sessions on feature branches.
- Every frontend session must hand off through remote `origin/main` so the next agent resumes from the same published state.
- Work one feature at a time from `../feature_list.json` (`passes: false` highest priority first).
- Never edit feature descriptions/steps; only flip `passes` after end-to-end browser verification.
- Keep `Dev_Logs.md` and KB ingestion in sync per `../DevViktor.md`.
- Run relevant frontend build/lint/test checks before commit.
- End the session with `..\scripts\session-handoff.ps1 -WorkDir .. -CommitMessage "<summary>"`.

