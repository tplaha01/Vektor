param(
    [string]$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path,
    [string]$Binary = "$env:LOCALAPPDATA\Programs\codebase-memory-mcp\codebase-memory-mcp.exe",
    [int]$TimeoutSeconds = 1200,
    [string]$Mode = "fast"
)

$ErrorActionPreference = "Stop"

if (-not (Test-Path -LiteralPath $Binary)) {
    throw "codebase-memory-mcp binary not found at $Binary"
}

if (-not (Get-Command node -ErrorAction SilentlyContinue)) {
    throw "Node.js is required for scripts/index-repo.ps1."
}

$tempJs = Join-Path $env:TEMP ("cbm-index-" + [guid]::NewGuid().ToString("N") + ".mjs")

$nodeScript = @'
import { spawn } from "node:child_process";
import { createInterface } from "node:readline";

const [repoRoot, binaryPath, timeoutSecondsRaw, indexMode] = process.argv.slice(2);
const timeoutMs = Math.max(30, Number(timeoutSecondsRaw || "1200")) * 1000;

const child = spawn(binaryPath, [], {
  stdio: ["pipe", "pipe", "pipe"],
});

const stdout = createInterface({ input: child.stdout });
const stderr = createInterface({ input: child.stderr });

let nextId = 0;
const pending = new Map();

const send = (message) => {
  child.stdin.write(JSON.stringify(message) + "\n");
};

const request = (method, params) => {
  const requestId = ++nextId;
  return new Promise((resolve, reject) => {
    const timer = setTimeout(() => {
      pending.delete(requestId);
      reject(new Error(`Timed out waiting for ${method}`));
    }, timeoutMs);

    pending.set(requestId, {
      resolve: (value) => {
        clearTimeout(timer);
        resolve(value);
      },
      reject: (error) => {
        clearTimeout(timer);
        reject(error);
      },
    });

    send({
      jsonrpc: "2.0",
      id: requestId,
      method,
      params,
    });
  });
};

stdout.on("line", (line) => {
  if (!line.trim()) {
    return;
  }

  let message;
  try {
    message = JSON.parse(line);
  } catch {
    return;
  }

  if (Object.prototype.hasOwnProperty.call(message, "id") && pending.has(message.id)) {
    const handler = pending.get(message.id);
    pending.delete(message.id);

    if (message.error) {
      handler.reject(new Error(JSON.stringify(message.error)));
    } else {
      handler.resolve(message.result);
    }
  }
});

stderr.on("line", (line) => {
  if (line.trim()) {
    process.stderr.write(`${line}\n`);
  }
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
'@

Set-Content -LiteralPath $tempJs -Value $nodeScript -Encoding UTF8

try {
    & node $tempJs $RepoRoot $Binary $TimeoutSeconds $Mode
    exit $LASTEXITCODE
} finally {
    if (Test-Path -LiteralPath $tempJs) {
        Remove-Item -LiteralPath $tempJs -Force -ErrorAction SilentlyContinue
    }
}
