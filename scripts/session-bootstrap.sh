#!/usr/bin/env bash
set -euo pipefail

WORK_DIR="."
STRICT=0
COUNT_REMAINING=0
CANONICAL_BRANCH="codex/main"
CANONICAL_REMOTE="origin/codex/main"
HEAD_LINES=80
LS_LINES=40

while [[ $# -gt 0 ]]; do
  case "$1" in
    -w|--work-dir) WORK_DIR="${2:?missing value}"; shift 2 ;;
    --strict) STRICT=1; shift ;;
    --count-remaining) COUNT_REMAINING=1; shift ;;
    --canonical-branch) CANONICAL_BRANCH="${2:?missing value}"; shift 2 ;;
    --canonical-remote) CANONICAL_REMOTE="${2:?missing value}"; shift 2 ;;
    --head-lines) HEAD_LINES="${2:?missing value}"; shift 2 ;;
    --ls-lines) LS_LINES="${2:?missing value}"; shift 2 ;;
    *) echo "Unknown argument: $1" >&2; exit 1 ;;
  esac
done

cd "$WORK_DIR"

echo "=== SESSION BOOTSTRAP ==="
echo "[1/8] pwd"
pwd

echo "[2/8] ls -la"
ls -la | sed -n "1,${LS_LINES}p"

print_file_head() {
  local file="$1"
  local label="$2"
  echo "$label"
  if [[ -f "$file" ]]; then
    sed -n "1,${HEAD_LINES}p" "$file"
  else
    echo "WARN: $file missing"
    if [[ $STRICT -eq 1 ]]; then
      return 1
    fi
  fi
}

print_file_head "app_spec.txt" "[3/8] app_spec.txt (head)"
print_file_head "feature_list.json" "[4/8] feature_list.json (head)"
print_file_head "codex-progress.txt" "[5/8] codex-progress.txt (head)"

echo "[6/8] git log --oneline -20"
git log --oneline -20

echo "[7/8] branch and handoff status"
current_branch="$(git branch --show-current | tr -d '\n')"
current_head="$(git rev-parse --short HEAD | tr -d '\n')"
status_output="$(git status --short)"

echo "current_branch=${current_branch}"
echo "current_head=${current_head}"
echo "canonical_local_branch=${CANONICAL_BRANCH}"
echo "canonical_remote_branch=${CANONICAL_REMOTE}"

if [[ -n "$status_output" ]]; then
  echo "worktree_dirty=true"
  echo "WARN: Dirty worktree detected. Previous session handoff is incomplete until the tree is clean again."
  echo "$status_output" | sed -n '1,20p'
  if [[ $STRICT -eq 1 ]]; then
    exit 7
  fi
else
  echo "worktree_dirty=false"
fi

if git show-ref --verify --quiet "refs/remotes/${CANONICAL_REMOTE}"; then
  remote_head="$(git rev-parse --short "${CANONICAL_REMOTE}" | tr -d '\n')"
  ahead="$(git rev-list --count "${CANONICAL_REMOTE}..HEAD" | tr -d '\n')"
  behind="$(git rev-list --count "HEAD..${CANONICAL_REMOTE}" | tr -d '\n')"
  echo "remote_head=${remote_head}"
  echo "ahead_of_${CANONICAL_REMOTE//\//_}=${ahead}"
  echo "behind_${CANONICAL_REMOTE//\//_}=${behind}"
  if [[ "${behind}" != "0" ]]; then
    echo "WARN: ${CANONICAL_BRANCH} is behind ${CANONICAL_REMOTE}. Sync before starting the next coding session."
    if [[ $STRICT -eq 1 ]]; then
      exit 8
    fi
  fi
else
  echo "WARN: ${CANONICAL_REMOTE} is not available in local refs yet."
fi

if [[ "${current_branch}" != "${CANONICAL_BRANCH}" ]]; then
  echo "WARN: Long-running sessions must end on ${CANONICAL_BRANCH}. Current branch is ${current_branch}."
  if [[ $STRICT -eq 1 ]]; then
    exit 6
  fi
fi

echo "handoff_script=scripts/session-handoff.sh"

echo "[8/8] remaining tests"
if [[ -f feature_list.json ]]; then
  if [[ $COUNT_REMAINING -eq 1 ]]; then
    node -e 'const fs=require("fs");const d=JSON.parse(fs.readFileSync("feature_list.json","utf8"));const pending=d.filter(x=>x&&x.passes===false);const next=pending[0]||null;console.log(`remaining_false=${pending.length}`);if(next){console.log(`next_category=${next.category||""}`);console.log(`next_description=${(next.description||"").slice(0,160)}`);console.log(`next_step_count=${Array.isArray(next.steps)?next.steps.length:0}`);}' || echo "WARN: could not parse feature_list.json for remaining tests"
  else
    approx="$(rg -o '"passes"\s*:\s*false' feature_list.json | wc -l | tr -d ' ')"
    echo "remaining_false_approx=${approx}"
  fi
else
  echo "WARN: feature_list.json missing"
  if [[ $STRICT -eq 1 ]]; then
    exit 5
  fi
fi

echo "=== BOOTSTRAP COMPLETE ==="
if [[ -f app_spec.txt && -f feature_list.json && -f codex-progress.txt ]]; then
  echo "MISSING_REQUIRED_FILES=false"
else
  echo "MISSING_REQUIRED_FILES=true"
fi
