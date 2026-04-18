"""
Dev Log Entry Management - Adheres to DevViktor.md specification
Automatically logs all runs to Dev_Logs.md and sends to repo knowledge base
"""
import os
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional
from uuid import uuid4
import logging

logger = logging.getLogger("devlog")


class DevLogEntry:
    """Single dev log entry following DevViktor structured template"""
    
    def __init__(
        self,
        actor_name: str = "github_copilot",
        actor_platform: str = "github_copilot",
        actor_model: str = "claude_haiku_4.5",
        actor_provider: str = "anthropic",
        scope: str = "Backend monitoring and live metrics implementation",
        files: list[str] = None,
        validation: str = "pending",
        notes: str = "",
        run_id: Optional[str] = None,
        git_branch: str = "main",
        git_commit_start: str = "",
        git_commit_end: str = "",
    ):
        self.entry_id = f"devlog-{datetime.now(timezone.utc).strftime('%Y%m%d')}-{uuid4().hex[:8]}"
        self.timestamp = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        self.stage = "START"  # Will be set to END on completion
        
        self.actor_name = actor_name
        self.actor_platform = actor_platform
        self.actor_model = actor_model
        self.actor_provider = actor_provider
        self.run_id = run_id or f"run-{uuid4().hex[:12]}"
        self.git_branch = git_branch
        self.git_commit_start = git_commit_start
        self.git_commit_end = git_commit_end
        self.scope = scope
        self.files = files or []
        self.validation = validation
        self.notes = notes

    def to_markdown(self) -> str:
        """Format entry as markdown for Dev_Logs.md"""
        files_md = "\n".join(f"- {f}" for f in self.files) if self.files else "(none)"
        
        return f"""[{self.timestamp}] [{self.stage}]
entry_id: {self.entry_id}
actor_name: {self.actor_name}
actor_platform: {self.actor_platform}
actor_model: {self.actor_model}
actor_provider: {self.actor_provider}
run_id: {self.run_id}
git_branch: {self.git_branch}
git_commit_start: {self.git_commit_start}
git_commit_end: {self.git_commit_end}
scope: {self.scope}
files:
{files_md}
validation: {self.validation}
notes: {self.notes}
"""

    def to_knowledge_graph_payload(self) -> Dict[str, Any]:
        """Convert to /fund/knowledge/development/log API payload"""
        return {
            "entry_id": self.entry_id,
            "stage": self.stage.lower(),
            "actor_name": self.actor_name,
            "actor_platform": self.actor_platform,
            "actor_model": self.actor_model,
            "actor_provider": self.actor_provider,
            "run_id": self.run_id,
            "branch": self.git_branch,
            "commit_start": self.git_commit_start,
            "commit_end": self.git_commit_end,
            "scope": self.scope,
            "files": self.files,
            "validation": self.validation,
            "notes": self.notes,
        }

    def to_knowledge_graph_jsonl(self) -> str:
        """Format as JSONL event for direct KB storage"""
        event = {
            "namespace": "development",
            "entity_type": "devlog_entry",
            "timestamp": self.timestamp,
            "data": self.to_knowledge_graph_payload(),
        }
        return json.dumps(event)


class DevLogger:
    """Manages dev log entry lifecycle and KB ingestion"""
    
    def __init__(self, repo_root: str = "."):
        self.repo_root = Path(repo_root)
        self.dev_logs_file = self.repo_root / "Dev_Logs.md"
        self.knowledge_graph_dir = self.repo_root / "knowledge_graph"
        self.events_jsonl_file = self.knowledge_graph_dir / "events.jsonl"
        
        # Ensure directories exist
        self.knowledge_graph_dir.mkdir(exist_ok=True)

    def get_git_commit(self) -> str:
        """Get current git commit SHA"""
        try:
            result = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                cwd=self.repo_root,
                capture_output=True,
                text=True,
                timeout=5,
            )
            return result.stdout.strip() if result.returncode == 0 else ""
        except Exception as e:
            logger.warning(f"Could not get git commit: {e}")
            return ""

    def get_git_branch(self) -> str:
        """Get current git branch"""
        try:
            result = subprocess.run(
                ["git", "rev-parse", "--abbrev-ref", "HEAD"],
                cwd=self.repo_root,
                capture_output=True,
                text=True,
                timeout=5,
            )
            return result.stdout.strip() if result.returncode == 0 else "unknown"
        except Exception as e:
            logger.warning(f"Could not get git branch: {e}")
            return "unknown"

    def start_session(
        self,
        scope: str,
        files: list[str] = None,
        notes: str = "",
    ) -> DevLogEntry:
        """Create and log a START entry"""
        entry = DevLogEntry(
            scope=scope,
            files=files or [],
            validation="in_progress",
            notes=notes,
            git_branch=self.get_git_branch(),
            git_commit_start=self.get_git_commit(),
        )
        
        # Append to Dev_Logs.md
        self._append_to_dev_logs(entry)
        
        # Ingest to repo KB (direct file write)
        self._ingest_to_knowledge_graph(entry)
        
        logger.info(f"✅ Session started: {entry.entry_id} (run: {entry.run_id})")
        return entry

    def end_session(
        self,
        entry: DevLogEntry,
        validation: str = "passed",
        notes: str = "",
    ) -> None:
        """Complete and log an END entry"""
        entry.stage = "END"
        entry.validation = validation
        entry.git_commit_end = self.get_git_commit()
        
        if notes:
            entry.notes = notes
        
        # Append to Dev_Logs.md
        self._append_to_dev_logs(entry)
        
        # Ingest to repo KB
        self._ingest_to_knowledge_graph(entry)
        
        logger.info(f"✅ Session ended: {entry.entry_id} ({validation})")

    def _append_to_dev_logs(self, entry: DevLogEntry) -> None:
        """Append formatted entry to Dev_Logs.md"""
        try:
            with open(self.dev_logs_file, "a", encoding="utf-8") as f:
                f.write("\n")
                f.write(entry.to_markdown())
            logger.debug(f"Appended to Dev_Logs.md: {entry.entry_id}")
        except Exception as e:
            logger.error(f"Failed to append to Dev_Logs.md: {e}")

    def _ingest_to_knowledge_graph(self, entry: DevLogEntry) -> None:
        """Write entry to repo knowledge graph (events.jsonl)"""
        try:
            with open(self.events_jsonl_file, "a", encoding="utf-8") as f:
                f.write(entry.to_knowledge_graph_jsonl() + "\n")
            logger.debug(f"Ingested to KB: {entry.entry_id}")
        except Exception as e:
            logger.error(f"Failed to ingest to knowledge graph: {e}")

    async def ingest_to_backend_api(
        self,
        entry: DevLogEntry,
        api_base_url: str = "http://localhost:8000",
    ) -> bool:
        """Send entry to backend API endpoint for KB ingestion"""
        try:
            import httpx
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{api_base_url}/fund/knowledge/development/log",
                    json=entry.to_knowledge_graph_payload(),
                    timeout=10.0,
                )
                if response.status_code == 200:
                    logger.info(f"✅ Ingested to backend KB API: {entry.entry_id}")
                    return True
                else:
                    logger.warning(
                        f"Backend API returned {response.status_code}: {response.text}"
                    )
                    return False
        except Exception as e:
            logger.warning(f"Could not ingest to backend API (fallback to local KB): {e}")
            return False


# Global instance
_dev_logger: Optional[DevLogger] = None


def get_dev_logger(repo_root: str = ".") -> DevLogger:
    """Get or create global dev logger instance"""
    global _dev_logger
    if _dev_logger is None:
        _dev_logger = DevLogger(repo_root)
    return _dev_logger


def create_dev_session(
    scope: str,
    files: list[str] = None,
    notes: str = "",
    repo_root: str = ".",
) -> DevLogEntry:
    """Convenience function to start a dev session"""
    logger = get_dev_logger(repo_root)
    return logger.start_session(scope=scope, files=files, notes=notes)


def complete_dev_session(
    entry: DevLogEntry,
    validation: str = "passed",
    notes: str = "",
) -> None:
    """Convenience function to end a dev session"""
    logger = get_dev_logger()
    logger.end_session(entry=entry, validation=validation, notes=notes)
