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
- Work one feature at a time from `../feature_list.json` (`passes: false` highest priority first).
- Never edit feature descriptions/steps; only flip `passes` after end-to-end browser verification.
- Keep `Dev_Logs.md` and KB ingestion in sync per `../DevViktor.md`.
- Run relevant frontend build/lint/test checks before commit.

