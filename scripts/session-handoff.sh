#!/usr/bin/env bash
set -euo pipefail

COMMIT_MESSAGE=""
WORK_DIR="."
CANONICAL_BRANCH="codex/main"
REMOTE_NAME="origin"
REMOTE_BRANCH="codex/main"
ALLOW_EMPTY_COMMIT=0
SKIP_PUSH=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    -m|--commit-message) COMMIT_MESSAGE="${2:?missing value}"; shift 2 ;;
    -w|--work-dir) WORK_DIR="${2:?missing value}"; shift 2 ;;
    --canonical-branch) CANONICAL_BRANCH="${2:?missing value}"; shift 2 ;;
    --remote-name) REMOTE_NAME="${2:?missing value}"; shift 2 ;;
    --remote-branch) REMOTE_BRANCH="${2:?missing value}"; shift 2 ;;
    --allow-empty-commit) ALLOW_EMPTY_COMMIT=1; shift ;;
    --skip-push) SKIP_PUSH=1; shift ;;
    *) echo "Unknown argument: $1" >&2; exit 1 ;;
  esac
done

if [[ -z "$COMMIT_MESSAGE" ]]; then
  echo "Commit message is required. Use --commit-message \"<summary>\"." >&2
  exit 1
fi

cd "$WORK_DIR"

repo_root="$(git rev-parse --show-toplevel 2>/dev/null || true)"
if [[ -z "$repo_root" ]]; then
  echo "session-handoff.sh must run inside a git repository." >&2
  exit 1
fi

current_branch="$(git branch --show-current | tr -d '\n')"
if [[ "$current_branch" != "$CANONICAL_BRANCH" ]]; then
  echo "Handoff must run from $CANONICAL_BRANCH. Current branch is $current_branch." >&2
  exit 1
fi

echo "=== SESSION HANDOFF ==="
echo "repo_root=$repo_root"
echo "current_branch=$current_branch"

git add -A

if git diff --cached --quiet && [[ $ALLOW_EMPTY_COMMIT -eq 0 ]]; then
  echo "No staged changes found. Either make repo changes before handoff or rerun with --allow-empty-commit." >&2
  exit 1
fi

if [[ $ALLOW_EMPTY_COMMIT -eq 1 ]]; then
  git commit --allow-empty -m "$COMMIT_MESSAGE"
else
  git commit -m "$COMMIT_MESSAGE"
fi

local_head="$(git rev-parse HEAD | tr -d '\n')"
short_head="$(git rev-parse --short HEAD | tr -d '\n')"
echo "local_head=$local_head"
echo "local_head_short=$short_head"

if [[ $SKIP_PUSH -eq 0 ]]; then
  git push "$REMOTE_NAME" "HEAD:$REMOTE_BRANCH"
  git branch --set-upstream-to "$REMOTE_NAME/$REMOTE_BRANCH" "$CANONICAL_BRANCH" >/dev/null 2>&1 || true

  remote_line="$(git ls-remote "$REMOTE_NAME" "refs/heads/$REMOTE_BRANCH" | head -n 1)"
  if [[ -z "$remote_line" ]]; then
    echo "Could not read remote head for $REMOTE_NAME/$REMOTE_BRANCH." >&2
    exit 1
  fi
  remote_head="$(echo "$remote_line" | awk '{print $1}')"
  echo "remote_head=$remote_head"
  if [[ "$remote_head" != "$local_head" ]]; then
    echo "Remote head mismatch. local=$local_head remote=$remote_head" >&2
    exit 1
  fi
fi

remaining_status="$(git status --short)"
if [[ -n "$remaining_status" ]]; then
  echo "$remaining_status"
  echo "Handoff incomplete: worktree is still dirty after commit/push." >&2
  exit 1
fi

echo "HANDOFF_READY=true"
echo "NEXT_AGENT_REF=$CANONICAL_BRANCH@$short_head"
echo "REMOTE_REF=$REMOTE_NAME/$REMOTE_BRANCH"
