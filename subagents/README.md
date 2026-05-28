# Subagents

This directory defines role-specific subagent responsibilities for the AI-native hedge fund buildout.

Primary runtime config is in `.codex/config.toml` with role TOML files under `.codex/agents/`.

Role groups:
- Core engineering: `explorer`, `reviewer`, `docs_researcher`
- Fund operations: `fund_manager`, `researcher`, `sentiment_researcher`, `trader`, `risk_auditor`, `openclaw_ops`

Usage pattern:
- Use `explorer` for read-only mapping before changes.
- Use `docs_researcher` for source verification.
- Use `fund_manager` to coordinate cross-role execution.
- Use `reviewer` before merging each milestone.

Token-efficiency policy:
- Treat subagents as context filters, not extra narration layers.
- Keep each subagent on a narrow file scope tied to the active feature.
- Run planner/explorer first, then hand only validated target files to executor.
- Avoid broad repo scans after bootstrap unless the active feature requires them.

Role specs:
- `fund-manager-subagent.md`
- `research-subagent.md`
- `trader-subagent.md`
- `risk-auditor-subagent.md`
