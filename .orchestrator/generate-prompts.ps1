param(
    [string]$OrchestratorRoot = $PSScriptRoot,
    [switch]$Force
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$queuePath = Join-Path $OrchestratorRoot "queue.json"
$statePath = Join-Path $OrchestratorRoot "state.json"
$promptsDir = Join-Path $OrchestratorRoot "prompts"

New-Item -ItemType Directory -Force -Path $promptsDir | Out-Null
New-Item -ItemType Directory -Force -Path (Join-Path $OrchestratorRoot "handoffs") | Out-Null
New-Item -ItemType Directory -Force -Path (Join-Path $OrchestratorRoot "logs") | Out-Null
New-Item -ItemType Directory -Force -Path (Join-Path $OrchestratorRoot "sessions") | Out-Null

$orderedIds = @(
    "R0A", "R0B", "R1A", "R1B", "R2A", "R2B", "R3A", "R3B",
    "P0A", "P0B", "P1A", "P1B", "P2A", "P2B",
    "A0A", "A0B", "A1A", "A1B", "A2A", "A2B", "A3A", "A3B", "A4A", "A4B",
    "A5A", "A5B", "A6A", "A6B", "A7A", "A7B", "A8A", "A8B", "A9A", "A9B"
)

$sessionPlans = @{
    R0 = "Research app foundation and repository alignment"
    R1 = "Research index and publication navigation"
    R2 = "Paper detail viewer and research reading workflow"
    R3 = "Research evidence, provenance, and editorial polish"
    P0 = "Platform runtime reliability and health gates"
    P1 = "Portfolio, policy, and risk operating surfaces"
    P2 = "Production deployment, monitoring, and operator controls"
    A0 = "Autonomous fund-manager orchestration baseline"
    A1 = "Agent role isolation and investment committee workflow"
    A2 = "Research memory, thesis lineage, and provenance loop"
    A3 = "Cross-asset data ingestion and deterministic signal contracts"
    A4 = "Sleeve allocation, mandate enforcement, and policy gates"
    A5 = "Execution intent routing and paper-broker audit trail"
    A6 = "Observability, incident handling, and kill-switch operations"
    A7 = "Reward, drift, and model-quality feedback loops"
    A8 = "Admin control center completion and operator ergonomics"
    A9 = "Final production hardening and full queue closure"
}

$sessions = for ($i = 0; $i -lt $orderedIds.Count; $i++) {
    $id = $orderedIds[$i]
    $prefix = $id.Substring(0, $id.Length - 1)
    $phase = $id.Substring($id.Length - 1)
    [ordered]@{
        id = $id
        phase = $prefix
        type = if ($phase -eq "A") { "implementation" } else { "validation" }
        title = $sessionPlans[$prefix]
        prompt = "prompts/$id.txt"
        next_session = if ($i + 1 -lt $orderedIds.Count) { $orderedIds[$i + 1] } else { "" }
    }
}

$queue = [ordered]@{
    name = "Vektor Autonomous Session Orchestrator Queue"
    version = 1
    sessions = $sessions
}

$queue | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $queuePath -Encoding UTF8

if ($Force -or -not (Test-Path -LiteralPath $statePath)) {
    [ordered]@{
        current_session = ""
        last_completed = ""
        status = ""
        started_at = ""
        updated_at = ""
        retry_count = 0
    } | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath $statePath -Encoding UTF8
}

for ($i = 0; $i -lt $orderedIds.Count; $i++) {
    $id = $orderedIds[$i]
    $prefix = $id.Substring(0, $id.Length - 1)
    $phase = $id.Substring($id.Length - 1)
    $next = if ($i + 1 -lt $orderedIds.Count) { $orderedIds[$i + 1] } else { "END" }
    $title = $sessionPlans[$prefix]
    $promptPath = Join-Path $promptsDir "$id.txt"

    if ((Test-Path -LiteralPath $promptPath) -and -not $Force) {
        continue
    }

    if ($phase -eq "A") {
        $content = @"
You are Codex running Vektor autonomous build session $id.

Session: $id
Phase: IMPLEMENTATION
Build Slice: $title
Next Session: $next

Operate with no operator intervention. The orchestrator launched you with approval_policy=never and sandbox_mode=danger-full-access.

Mandatory repo contract:
1. Run scripts/session-bootstrap.ps1 -CountRemaining from the repository root.
2. Read DevViktor.md, docs/AI_NATIVE_HEDGE_FUND_AUDIT_AND_ROADMAP.md, and .codex/config.toml for current constraints.
3. Append a START entry to Dev_Logs.md for session $id.
4. Use the codebase-memory MCP graph first for code discovery; fall back to rg only for literals/config/non-code files.
5. Implement the highest-value, tightly scoped work for this build slice: $title.
6. Keep changes on codex/main only. Do not touch production main.
7. Update codex-progress.txt and any directly relevant docs when the implementation changes behavior.
8. Ingest the run into knowledge_graph/ using the repository's existing development-log pattern or offline fallback.
9. End by emitting the HANDOFF PACKAGE exactly as specified below.

Implementation expectations:
- Prefer existing architecture and helpers over new abstractions.
- Keep paper-trading safety intact; do not enable live trading.
- Add or update focused tests for changed behavior.
- Do not leave unrelated refactors or uncommitted generated noise.

Required final output format:

HANDOFF PACKAGE

Session:
$id

Status:
PASS or FAIL

Next Session:
$next

Validation Status:
Briefly state tests run, evidence captured, or why validation remains blocked.

Commit Hash:
The local commit hash if a commit was created, otherwise pending.
"@
    } else {
        $content = @"
You are Codex running Vektor autonomous validation session $id.

Session: $id
Phase: VALIDATION
Build Slice: $title
Next Session: $next

Operate with no operator intervention. The orchestrator launched you with approval_policy=never and sandbox_mode=danger-full-access.

Mandatory validation checklist:
1. Run scripts/session-bootstrap.ps1 -CountRemaining from the repository root.
2. Append a START entry to Dev_Logs.md for validation session $id.
3. Run npm run build in the relevant frontend workspace. If multiple frontend workspaces are relevant, validate the one touched by the prior implementation session and explain the choice.
4. Run npm run lint in the same workspace when the script exists.
5. Run npm run dev as a background process or reuse an existing dev server; record the URL and process handling.
6. Capture at least one Playwright screenshot of the relevant UI or a reachable health/status page.
7. Run focused backend/frontend tests if the implementation touched backend or shared contracts.
8. Update Dev_Logs.md with END status, validation commands, screenshot path, and any failure details.
9. Update knowledge_graph/ with the same run evidence.
10. Run scripts/index-repo.ps1 from the repo root and capture the result.
11. Commit all intended changes on codex/main.
12. Push to origin/codex/main.
13. Verify git status --short is clean except for orchestrator runtime files ignored by .orchestrator/.gitignore.

If a required command is unavailable or inapplicable, record the reason and use the closest valid repository-specific equivalent. Do not mark PASS if the validation target is missing or the main workflow is broken.

Required final output format:

HANDOFF PACKAGE

Session:
$id

Status:
PASS or FAIL

Next Session:
$next

Validation Status:
Include npm run build, npm run lint, npm run dev, Playwright screenshot, Dev_Logs update, knowledge_graph update, scripts/index-repo.ps1, commit, and push results.

Commit Hash:
The pushed commit hash if successful, otherwise pending.
"@
    }

    $content | Set-Content -LiteralPath $promptPath -Encoding UTF8
}

Write-Output "Generated queue and prompts under $OrchestratorRoot"
