#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TIMEOUT_SECONDS="${TIMEOUT_SECONDS:-1200}"
INDEX_MODE="${INDEX_MODE:-fast}"

if [[ $# -gt 0 ]]; then
  REPO_ROOT="$1"
fi

if ! command -v node >/dev/null 2>&1; then
  echo "Node.js is required for scripts/index-repo.sh." >&2
  exit 1
fi

resolve_binary() {
  if [[ -n "${CODEBASE_MEMORY_MCP_BINARY:-}" && -x "${CODEBASE_MEMORY_MCP_BINARY}" ]]; then
    echo "${CODEBASE_MEMORY_MCP_BINARY}"
    return 0
  fi
  if command -v codebase-memory-mcp >/dev/null 2>&1; then
    command -v codebase-memory-mcp
    return 0
  fi
  if [[ -n "${LOCALAPPDATA:-}" ]]; then
    local win_path="${LOCALAPPDATA}/Programs/codebase-memory-mcp/codebase-memory-mcp.exe"
    if [[ -x "$win_path" ]]; then
      echo "$win_path"
      return 0
    fi
  fi
  return 1
}

BINARY="$(resolve_binary || true)"
if [[ -z "$BINARY" ]]; then
  echo "codebase-memory-mcp binary not found. Set CODEBASE_MEMORY_MCP_BINARY or install codebase-memory-mcp on PATH." >&2
  exit 1
fi

TMP_JS="$(mktemp "${TMPDIR:-/tmp}/cbm-index-XXXXXX.mjs")"
trap 'rm -f "$TMP_JS"' EXIT

cat >"$TMP_JS" <<'EOF'
import { spawn } from "node:child_process";
import { createInterface } from "node:readline";

const [repoRoot, binaryPath, timeoutSecondsRaw, indexMode] = process.argv.slice(2);
const timeoutMs = Math.max(30, Number(timeoutSecondsRaw || "1200")) * 1000;

const child = spawn(binaryPath, [], { stdio: ["pipe", "pipe", "pipe"] });
const stdout = createInterface({ input: child.stdout });
const stderr = createInterface({ input: child.stderr });
let nextId = 0;
const pending = new Map();

const send = (message) => child.stdin.write(JSON.stringify(message) + "\n");
const request = (method, params) => {
  const requestId = ++nextId;
  return new Promise((resolve, reject) => {
    const timer = setTimeout(() => {
      pending.delete(requestId);
      reject(new Error(`Timed out waiting for ${method}`));
    }, timeoutMs);
    pending.set(requestId, {
      resolve: (value) => { clearTimeout(timer); resolve(value); },
      reject: (error) => { clearTimeout(timer); reject(error); },
    });
    send({ jsonrpc: "2.0", id: requestId, method, params });
  });
};

stdout.on("line", (line) => {
  if (!line.trim()) return;
  let message;
  try { message = JSON.parse(line); } catch { return; }
  if (Object.prototype.hasOwnProperty.call(message, "id") && pending.has(message.id)) {
    const handler = pending.get(message.id);
    pending.delete(message.id);
    if (message.error) handler.reject(new Error(JSON.stringify(message.error)));
    else handler.resolve(message.result);
  }
});

stderr.on("line", (line) => {
  if (line.trim()) process.stderr.write(`${line}\n`);
});

const closePromise = new Promise((resolve, reject) => {
  child.on("error", reject);
  child.on("close", (code) => resolve(code));
});

await request("initialize", {
  protocolVersion: "2024-11-05",
  clientInfo: { name: "tradingbot-indexer", version: "1.0.0" },
  capabilities: {},
});
send({ jsonrpc: "2.0", method: "notifications/initialized", params: {} });
const tools = await request("tools/list", {});
if (!tools.tools?.some((tool) => tool.name === "index_repository")) {
  throw new Error("index_repository tool not found");
}
const result = await request("tools/call", {
  name: "index_repository",
  arguments: { repo_path: repoRoot, mode: indexMode || "fast" },
});
process.stdout.write(`${JSON.stringify(result, null, 2)}\n`);
child.stdin.end();
await closePromise;
EOF

node "$TMP_JS" "$REPO_ROOT" "$BINARY" "$TIMEOUT_SECONDS" "$INDEX_MODE"
