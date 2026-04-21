from __future__ import annotations

import json
import logging
import shlex
import shutil
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from threading import RLock, Thread
from time import monotonic
from typing import Any, Dict, Iterable, List

from app.config import get_settings


logger = logging.getLogger("alfred.fund.knowledge")


def _utc_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _normalize_ts(value: str | None) -> str:
    if not value:
        return _utc_iso()
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc).isoformat().replace(
            "+00:00", "Z"
        )
    except ValueError:
        return _utc_iso()


def _safe_filename(value: str) -> str:
    allowed = []
    for ch in value:
        if ch.isalnum() or ch in ("-", "_", "."):
            allowed.append(ch)
        else:
            allowed.append("_")
    return "".join(allowed)[:180]


def _as_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, (list, tuple, set)):
        return [str(item) for item in value if str(item).strip()]
    if isinstance(value, str):
        return [value] if value.strip() else []
    return [str(value)]


ALLOWED_EVENT_NAMESPACES: set[str] = {
    "allocator",
    "audit_log",
    "decision_ledger",
    "development",
    "docs",
    "execution",
    "fund",
    "knowledge",
    "openclaw",
    "orchestrator",
    "research",
    "research_memory",
    "risk",
    "runtime",
    "security",
    "sentiment",
    "sentiment_ingest",
    "system",
    "task_bus",
}


def _normalize_event_type(source: str, event_type: str) -> tuple[str, str]:
    normalized_source = str(source or "system").strip().lower().replace(" ", "_")
    normalized_type = str(event_type or "unknown").strip().lower().replace(" ", "_")
    if "." in normalized_type:
        prefix = normalized_type.split(".", 1)[0]
        if prefix in ALLOWED_EVENT_NAMESPACES:
            return normalized_type, prefix
        return f"{normalized_source}.{normalized_type}", normalized_source
    return f"{normalized_source}.{normalized_type}", normalized_source


@dataclass(frozen=True)
class KnowledgeEvent:
    event_id: str
    source: str
    namespace: str
    source_event_id: str | None
    event_type: str
    occurred_at: str
    run_id: str | None
    agent_id: str | None
    decision_id: str | None
    order_id: str | None
    entities: dict[str, list[str]]
    payload: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "event_id": self.event_id,
            "source": self.source,
            "namespace": self.namespace,
            "source_event_id": self.source_event_id,
            "event_type": self.event_type,
            "occurred_at": self.occurred_at,
            "run_id": self.run_id,
            "agent_id": self.agent_id,
            "decision_id": self.decision_id,
            "order_id": self.order_id,
            "entities": {k: list(v) for k, v in self.entities.items()},
            "payload": dict(self.payload),
        }


class KnowledgeGraph:
    """
    Live-growing in-process knowledge graph index with optional Graphify sync.
    """

    def __init__(
        self,
        *,
        enabled: bool = True,
        storage_dir: str = "knowledge_graph",
        max_events: int = 50_000,
        persist: bool = True,
        graphify_sync_enabled: bool = False,
        graphify_update_command: str = "py -3 -m graphify update .",
        graphify_sync_min_interval_seconds: int = 30,
    ) -> None:
        self.enabled = bool(enabled)
        self.max_events = int(max_events)
        self.persist = bool(persist)
        self._storage_dir = Path(storage_dir)
        self._events_file = self._storage_dir / "events.jsonl"
        self._events_notes_dir = self._storage_dir / "events"
        self._entities_dir = self._storage_dir / "entities"
        self._graphify_sync_enabled = bool(graphify_sync_enabled)
        self._graphify_update_command = graphify_update_command.strip()
        self._graphify_sync_min_interval_seconds = max(5, int(graphify_sync_min_interval_seconds))

        self._lock = RLock()
        self._seq = 0
        self._events: dict[str, KnowledgeEvent] = {}
        self._ordered_ids: list[str] = []
        self._source_dedupe: dict[str, str] = {}
        self._last_graphify_sync_at: str | None = None
        self._last_graphify_sync_status: str | None = None
        self._last_graphify_sync_error: str | None = None
        self._graphify_failures = 0
        self._graphify_sync_running = False
        self._graphify_last_monotonic = 0.0

        if self.enabled and self.persist:
            self._bootstrap_storage()
            self._load_persisted_events()

    def ingest(
        self,
        *,
        source: str,
        event_type: str,
        payload: dict[str, Any] | None = None,
        occurred_at: str | None = None,
        source_event_id: str | None = None,
        run_id: str | None = None,
        agent_id: str | None = None,
        decision_id: str | None = None,
        order_id: str | None = None,
    ) -> dict[str, Any]:
        if not self.enabled:
            return {"enabled": False}

        clean_source = str(source or "unknown").strip().lower()
        clean_event_type, clean_namespace = _normalize_event_type(clean_source, str(event_type or "unknown").strip())
        clean_payload = dict(payload or {})
        occurred_iso = _normalize_ts(occurred_at)
        normalized_source_event_id = str(source_event_id).strip() if source_event_id is not None else None
        dedupe_key = (
            f"{clean_source}:{normalized_source_event_id}:{occurred_iso}"
            if normalized_source_event_id
            else None
        )

        with self._lock:
            if dedupe_key and dedupe_key in self._source_dedupe:
                existing_id = self._source_dedupe[dedupe_key]
                existing = self._events.get(existing_id)
                return existing.to_dict() if existing else {"event_id": existing_id}

            self._seq += 1
            event_id = f"kge-{self._seq:08d}"
            entities = self._extract_entities(
                run_id=run_id,
                agent_id=agent_id,
                decision_id=decision_id,
                order_id=order_id,
                payload=clean_payload,
            )
            event = KnowledgeEvent(
                event_id=event_id,
                source=clean_source,
                namespace=clean_namespace,
                source_event_id=normalized_source_event_id,
                event_type=clean_event_type,
                occurred_at=occurred_iso,
                run_id=run_id,
                agent_id=agent_id,
                decision_id=decision_id,
                order_id=order_id,
                entities=entities,
                payload=clean_payload,
            )
            self._events[event.event_id] = event
            self._ordered_ids.append(event.event_id)
            if dedupe_key:
                self._source_dedupe[dedupe_key] = event.event_id
            self._prune_locked()

        self._persist_event(event)
        self._maybe_trigger_graphify_sync()
        return event.to_dict()

    def capture(self, source: str, event: dict[str, Any]) -> dict[str, Any]:
        raw_payload = event.get("payload")
        payload = dict(raw_payload) if isinstance(raw_payload, dict) else {}
        return self.ingest(
            source=source,
            source_event_id=event.get("event_id") or event.get("ingest_id") or event.get("reject_id"),
            event_type=str(event.get("event_type") or event.get("event") or "unknown"),
            occurred_at=event.get("event_ts") or event.get("ts") or event.get("received_at") or event.get("created_at"),
            run_id=event.get("run_id") or payload.get("run_id"),
            agent_id=event.get("agent_id") or payload.get("agent_id"),
            decision_id=event.get("decision_id") or payload.get("decision_id"),
            order_id=event.get("order_id") or payload.get("order_id"),
            payload={k: v for k, v in event.items() if k not in {"event_id", "event_ts"}},
        )

    def list_events(
        self,
        *,
        limit: int = 200,
        namespace: str | None = None,
        source: str | None = None,
        event_type: str | None = None,
        run_id: str | None = None,
        agent_id: str | None = None,
        decision_id: str | None = None,
        order_id: str | None = None,
    ) -> list[dict[str, Any]]:
        with self._lock:
            ordered = [self._events[eid] for eid in self._ordered_ids if eid in self._events]

        filtered: list[KnowledgeEvent] = []
        for event in reversed(ordered):
            if namespace and event.namespace != namespace:
                continue
            if source and event.source != source:
                continue
            if event_type and event.event_type != event_type:
                continue
            if run_id and event.run_id != run_id:
                continue
            if agent_id and event.agent_id != agent_id:
                continue
            if decision_id and event.decision_id != decision_id:
                continue
            if order_id and event.order_id != order_id:
                continue
            filtered.append(event)
            if len(filtered) >= max(1, limit):
                break
        return [event.to_dict() for event in filtered]

    def lineage(
        self,
        *,
        run_id: str | None = None,
        decision_id: str | None = None,
        order_id: str | None = None,
        report_id: str | None = None,
        limit: int = 500,
    ) -> list[dict[str, Any]]:
        with self._lock:
            ordered = [self._events[eid] for eid in self._ordered_ids if eid in self._events]

        def _matches(event: KnowledgeEvent) -> bool:
            if run_id and event.run_id == run_id:
                return True
            if decision_id and event.decision_id == decision_id:
                return True
            if order_id and event.order_id == order_id:
                return True
            if report_id and report_id in event.entities.get("report_id", []):
                return True
            return False

        rows: list[dict[str, Any]] = []
        for event in ordered:
            if _matches(event):
                rows.append(event.to_dict())
        if limit >= 0:
            rows = rows[-limit:]
        return rows

    def stats(self) -> dict[str, Any]:
        with self._lock:
            event_count = len(self._events)
            source_count = len({event.source for event in self._events.values()})
            namespace_counts: dict[str, int] = {}
            for event in self._events.values():
                namespace_counts[event.namespace] = namespace_counts.get(event.namespace, 0) + 1
        return {
            "enabled": self.enabled,
            "canonical_store": "sqlite",
            "projection_store": "filesystem_notes",
            "event_count": event_count,
            "source_count": source_count,
            "namespace_counts": dict(sorted(namespace_counts.items(), key=lambda item: item[0])),
            "namespace_policy": sorted(ALLOWED_EVENT_NAMESPACES),
            "storage_dir": str(self._storage_dir),
            "persist": self.persist,
            "graphify_sync_enabled": self._graphify_sync_enabled,
            "graphify_update_command": self._graphify_update_command,
            "last_graphify_sync_at": self._last_graphify_sync_at,
            "last_graphify_sync_status": self._last_graphify_sync_status,
            "last_graphify_sync_error": self._last_graphify_sync_error,
            "graphify_failures": self._graphify_failures,
            "graphify_sync_running": self._graphify_sync_running,
        }

    def restore_from_storage(self) -> dict[str, Any]:
        with self._lock:
            in_memory_events = [self._events[eid] for eid in self._ordered_ids if eid in self._events]

        loaded_from_db = self._load_sqlite_events(reset_existing=True)
        if loaded_from_db > 0:
            self._prune_locked()
            return {
                "restored": 1,
                "source": "sqlite",
                "event_count": loaded_from_db,
            }

        migrated = 0
        for event in in_memory_events:
            try:
                from app.storage import db as storage_db

                storage_db.save_knowledge_event(event.to_dict())
                migrated += 1
            except Exception as exc:  # pragma: no cover
                logger.warning("knowledge_graph.migrate_to_db_failed: %s", exc)
                break

        return {
            "restored": 1 if in_memory_events else 0,
            "source": "memory_projection" if in_memory_events else "empty",
            "event_count": len(in_memory_events),
            "migrated_to_sqlite": migrated,
        }

    def reset(self, *, clear_storage: bool = True) -> dict[str, Any]:
        cleared_db_events = 0
        with self._lock:
            previous_event_count = len(self._events)
            previous_seq = self._seq
            self._seq = 0
            self._events.clear()
            self._ordered_ids.clear()
            self._source_dedupe.clear()
            self._last_graphify_sync_at = None
            self._last_graphify_sync_status = None
            self._last_graphify_sync_error = None
            self._graphify_failures = 0
            self._graphify_sync_running = False
            self._graphify_last_monotonic = 0.0

        if self.persist and clear_storage:
            try:
                from app.storage import db as storage_db

                cleared_db_events = int(storage_db.clear_knowledge_events())
            except Exception as exc:  # pragma: no cover
                logger.warning("knowledge_graph.reset_db_failed: %s", exc)
            try:
                if self._events_file.exists():
                    self._events_file.unlink(missing_ok=True)
                if self._events_notes_dir.exists():
                    shutil.rmtree(self._events_notes_dir, ignore_errors=True)
                if self._entities_dir.exists():
                    shutil.rmtree(self._entities_dir, ignore_errors=True)
                self._bootstrap_storage()
            except Exception as exc:  # pragma: no cover
                logger.warning("knowledge_graph.reset_storage_failed: %s", exc)

        return {
            "reset": True,
            "clear_storage": bool(clear_storage),
            "previous_event_count": previous_event_count,
            "previous_seq": previous_seq,
            "cleared_db_events": cleared_db_events,
            "storage_dir": str(self._storage_dir),
        }

    def rebuild_projection(self) -> dict[str, Any]:
        with self._lock:
            events = [self._events[eid] for eid in self._ordered_ids if eid in self._events]

        if self.persist:
            try:
                if self._events_file.exists():
                    self._events_file.unlink(missing_ok=True)
                if self._events_notes_dir.exists():
                    shutil.rmtree(self._events_notes_dir, ignore_errors=True)
                if self._entities_dir.exists():
                    shutil.rmtree(self._entities_dir, ignore_errors=True)
                self._bootstrap_storage()
            except Exception as exc:  # pragma: no cover
                logger.warning("knowledge_graph.rebuild_projection_storage_failed: %s", exc)

        rebuilt = 0
        for event in events:
            self._persist_projection_only(event)
            rebuilt += 1
        return {
            "rebuilt": True,
            "rebuilt_event_count": rebuilt,
            "storage_dir": str(self._storage_dir),
        }

    def _bootstrap_storage(self) -> None:
        self._storage_dir.mkdir(parents=True, exist_ok=True)
        self._events_notes_dir.mkdir(parents=True, exist_ok=True)
        self._entities_dir.mkdir(parents=True, exist_ok=True)
        if not self._events_file.exists():
            self._events_file.touch()

    def _load_persisted_events(self) -> None:
        loaded_from_db = self._load_sqlite_events()
        if loaded_from_db > 0:
            self._prune_locked()
            return
        if not self._events_file.exists():
            return
        loaded = 0
        try:
            with self._events_file.open("r", encoding="utf-8") as handle:
                for line in handle:
                    row = line.strip()
                    if not row:
                        continue
                    try:
                        payload = json.loads(row)
                    except json.JSONDecodeError:
                        continue
                    event_id = str(payload.get("event_id") or f"kge-{loaded + 1:08d}")
                    normalized_event_type, derived_namespace = _normalize_event_type(
                        str(payload.get("source") or "unknown"),
                        str(payload.get("event_type") or "unknown"),
                    )
                    event = KnowledgeEvent(
                        event_id=event_id,
                        source=str(payload.get("source") or "unknown"),
                        namespace=str(payload.get("namespace") or derived_namespace),
                        source_event_id=payload.get("source_event_id"),
                        event_type=normalized_event_type,
                        occurred_at=_normalize_ts(payload.get("occurred_at")),
                        run_id=payload.get("run_id"),
                        agent_id=payload.get("agent_id"),
                        decision_id=payload.get("decision_id"),
                        order_id=payload.get("order_id"),
                        entities=dict(payload.get("entities") or {}),
                        payload=dict(payload.get("payload") or {}),
                    )
                    self._events[event.event_id] = event
                    self._ordered_ids.append(event.event_id)
                    if event.source_event_id:
                        key = f"{event.source}:{event.source_event_id}:{event.occurred_at}"
                        self._source_dedupe[key] = event.event_id
                    loaded += 1

                    if event.event_id.startswith("kge-"):
                        try:
                            suffix = int(event.event_id.split("kge-")[1])
                            self._seq = max(self._seq, suffix)
                        except ValueError:
                            pass
            self._prune_locked()
        except Exception as exc:  # pragma: no cover
            logger.warning("knowledge_graph.load_failed: %s", exc)

    def _persist_event(self, event: KnowledgeEvent) -> None:
        if not self.persist:
            return
        try:
            from app.storage import db as storage_db

            storage_db.save_knowledge_event(event.to_dict())
        except Exception as exc:  # pragma: no cover
            logger.warning("knowledge_graph.persist_db_failed: %s", exc)
        self._persist_projection_only(event)

    def _persist_projection_only(self, event: KnowledgeEvent) -> None:
        if not self.persist:
            return
        try:
            self._bootstrap_storage()
            with self._events_file.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(event.to_dict(), sort_keys=True, default=str) + "\n")
            self._write_event_note(event)
        except Exception as exc:  # pragma: no cover
            logger.warning("knowledge_graph.persist_projection_failed: %s", exc)

    def _load_sqlite_events(self, *, reset_existing: bool = False) -> int:
        try:
            from app.storage import db as storage_db

            rows = storage_db.load_knowledge_events()
        except Exception as exc:  # pragma: no cover
            if "Database not initialized" in str(exc):
                logger.debug("knowledge_graph.load_db_skipped_until_init")
            else:
                logger.warning("knowledge_graph.load_db_failed: %s", exc)
            return 0

        if reset_existing:
            with self._lock:
                self._seq = 0
                self._events.clear()
                self._ordered_ids.clear()
                self._source_dedupe.clear()

        loaded = 0
        for payload in rows:
            event_id = str(payload.get("event_id") or f"kge-{loaded + 1:08d}")
            normalized_event_type, derived_namespace = _normalize_event_type(
                str(payload.get("source") or "unknown"),
                str(payload.get("event_type") or "unknown"),
            )
            event = KnowledgeEvent(
                event_id=event_id,
                source=str(payload.get("source") or "unknown"),
                namespace=str(payload.get("namespace") or derived_namespace),
                source_event_id=payload.get("source_event_id"),
                event_type=normalized_event_type,
                occurred_at=_normalize_ts(payload.get("occurred_at")),
                run_id=payload.get("run_id"),
                agent_id=payload.get("agent_id"),
                decision_id=payload.get("decision_id"),
                order_id=payload.get("order_id"),
                entities=dict(payload.get("entities") or {}),
                payload=dict(payload.get("payload") or {}),
            )
            self._events[event.event_id] = event
            self._ordered_ids.append(event.event_id)
            if event.source_event_id:
                key = f"{event.source}:{event.source_event_id}:{event.occurred_at}"
                self._source_dedupe[key] = event.event_id
            loaded += 1

            if event.event_id.startswith("kge-"):
                try:
                    suffix = int(event.event_id.split("kge-")[1])
                    self._seq = max(self._seq, suffix)
                except ValueError:
                    pass
        return loaded

    def _write_event_note(self, event: KnowledgeEvent) -> None:
        links = self._event_links(event)
        lines = [
            "---",
            f"event_id: {event.event_id}",
            f"source: {event.source}",
            f"namespace: {event.namespace}",
            f"event_type: {event.event_type}",
            f"occurred_at: {event.occurred_at}",
            f"run_id: {event.run_id or ''}",
            f"agent_id: {event.agent_id or ''}",
            f"decision_id: {event.decision_id or ''}",
            f"order_id: {event.order_id or ''}",
            f"source_event_id: {event.source_event_id or ''}",
            "---",
            "",
            "# Event",
            "",
            f"- Source: `{event.source}`",
            f"- Type: `{event.event_type}`",
            f"- Timestamp: `{event.occurred_at}`",
            "",
            "## Links",
            "",
        ]
        if links:
            lines.extend([f"- {value}" for value in links])
        else:
            lines.append("- (none)")

        lines.extend(
            [
                "",
                "## Payload",
                "",
                "```json",
                json.dumps(event.payload, indent=2, sort_keys=True, default=str),
                "```",
                "",
            ]
        )
        note = "\n".join(lines)
        note_path = self._events_notes_dir / f"{_safe_filename(event.event_id)}.md"
        note_path.write_text(note, encoding="utf-8")
        self._write_entity_notes(event)

    def _write_entity_notes(self, event: KnowledgeEvent) -> None:
        for kind, values in event.entities.items():
            entity_kind_dir = self._entities_dir / _safe_filename(kind)
            entity_kind_dir.mkdir(parents=True, exist_ok=True)
            for value in values:
                note_path = entity_kind_dir / f"{_safe_filename(value)}.md"
                if note_path.exists():
                    continue
                content = "\n".join(
                    [
                        "---",
                        f"entity_type: {kind}",
                        f"entity_id: {value}",
                        "---",
                        "",
                        f"# {kind}:{value}",
                        "",
                        "Auto-created entity node for Vektor knowledge graph.",
                        "",
                    ]
                )
                note_path.write_text(content, encoding="utf-8")

    def _event_links(self, event: KnowledgeEvent) -> list[str]:
        links: list[str] = []
        for kind, values in sorted(event.entities.items(), key=lambda item: item[0]):
            for value in values:
                links.append(f"[[entities/{kind}/{_safe_filename(value)}]]")
        return links

    def _extract_entities(
        self,
        *,
        run_id: str | None,
        agent_id: str | None,
        decision_id: str | None,
        order_id: str | None,
        payload: dict[str, Any],
    ) -> dict[str, list[str]]:
        entities: dict[str, list[str]] = {
            "run_id": _as_list(run_id),
            "agent_id": _as_list(agent_id),
            "decision_id": _as_list(decision_id),
            "order_id": _as_list(order_id),
        }
        if isinstance(payload, dict):
            for key, value in payload.items():
                lowered = str(key).strip().lower()
                if lowered.endswith("_id"):
                    entities.setdefault(lowered, [])
                    entities[lowered].extend(_as_list(value))
                elif lowered.endswith("_ids"):
                    singular = lowered[:-1]
                    entities.setdefault(singular, [])
                    entities[singular].extend(_as_list(value))
                elif lowered in {"symbol", "asset"}:
                    entities.setdefault("asset_symbol", [])
                    entities["asset_symbol"].extend(_as_list(str(value).upper()))
                elif lowered in {"assets", "asset_universe"}:
                    entities.setdefault("asset_symbol", [])
                    entities["asset_symbol"].extend([item.upper() for item in _as_list(value)])

        normalized: dict[str, list[str]] = {}
        for key, values in entities.items():
            clean: list[str] = []
            seen = set()
            for value in values:
                text = str(value).strip()
                if not text or text in seen:
                    continue
                seen.add(text)
                clean.append(text)
            if clean:
                normalized[key] = clean
        return normalized

    def _prune_locked(self) -> None:
        while len(self._ordered_ids) > self.max_events:
            oldest_id = self._ordered_ids.pop(0)
            old = self._events.pop(oldest_id, None)
            if not old:
                continue
            if old.source_event_id:
                dedupe_key = f"{old.source}:{old.source_event_id}:{old.occurred_at}"
                if self._source_dedupe.get(dedupe_key) == oldest_id:
                    self._source_dedupe.pop(dedupe_key, None)

    def _maybe_trigger_graphify_sync(self) -> None:
        if not self._graphify_sync_enabled or not self._graphify_update_command:
            return
        with self._lock:
            if self._graphify_sync_running:
                return
            now = monotonic()
            if (now - self._graphify_last_monotonic) < self._graphify_sync_min_interval_seconds:
                return
            self._graphify_sync_running = True
            self._graphify_last_monotonic = now
        Thread(target=self._run_graphify_sync, daemon=True).start()

    def _run_graphify_sync(self) -> None:
        try:
            command = shlex.split(self._graphify_update_command, posix=False)
            if not command:
                raise ValueError("empty_graphify_command")
            completed = subprocess.run(
                command,
                cwd=str(self._storage_dir),
                capture_output=True,
                text=True,
                timeout=180,
                check=False,
            )
            with self._lock:
                self._last_graphify_sync_at = _utc_iso()
                if completed.returncode == 0:
                    self._last_graphify_sync_status = "ok"
                    self._last_graphify_sync_error = None
                else:
                    self._last_graphify_sync_status = "failed"
                    self._graphify_failures += 1
                    stderr = (completed.stderr or completed.stdout or "").strip()
                    self._last_graphify_sync_error = stderr[:2000] if stderr else "graphify_failed"
        except Exception as exc:  # pragma: no cover
            with self._lock:
                self._last_graphify_sync_at = _utc_iso()
                self._last_graphify_sync_status = "failed"
                self._graphify_failures += 1
                self._last_graphify_sync_error = str(exc)[:2000]
        finally:
            with self._lock:
                self._graphify_sync_running = False


def _build_default_knowledge_graph() -> KnowledgeGraph:
    settings = get_settings()
    return KnowledgeGraph(
        enabled=settings.KNOWLEDGE_GRAPH_ENABLED,
        storage_dir=settings.KNOWLEDGE_GRAPH_DIR,
        max_events=settings.KNOWLEDGE_GRAPH_MAX_EVENTS,
        persist=settings.KNOWLEDGE_GRAPH_PERSIST,
        graphify_sync_enabled=settings.GRAPHIFY_SYNC_ENABLED,
        graphify_update_command=settings.GRAPHIFY_UPDATE_COMMAND,
        graphify_sync_min_interval_seconds=settings.GRAPHIFY_SYNC_MIN_INTERVAL_SECONDS,
    )


knowledge_graph = _build_default_knowledge_graph()
