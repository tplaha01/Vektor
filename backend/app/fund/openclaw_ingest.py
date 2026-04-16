from __future__ import annotations

import json
import os
import secrets
from datetime import datetime, timezone
from threading import RLock
from typing import Any, Callable, Dict, List

from app.fund.audit_log import AuditLog, audit_log


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class OpenClawIngestService:
    """
    Authenticated ingest path for OpenClaw artifacts.

    This service never grants direct trading authority. Trade/order-like payloads
    are rejected and logged.
    """

    _DISALLOWED_KINDS = {
        "order",
        "orders",
        "trade",
        "trades",
        "execution_intent",
        "execution",
        "broker_command",
    }
    _DISALLOWED_KEYS = {
        "order",
        "orders",
        "trade",
        "trades",
        "submit_order",
        "place_order",
        "execution_intent",
        "broker_action",
    }

    def __init__(
        self,
        *,
        token: str | None = None,
        log: AuditLog | None = None,
        max_payload_bytes: int = 256_000,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        configured = token if token is not None else os.getenv("OPENCLAW_INGEST_TOKEN")
        self._token = configured
        self._log = log or audit_log
        self._max_payload_bytes = max_payload_bytes
        self._clock = clock or _utc_now
        self._lock = RLock()

        self._seq = 0
        self._accepted: List[Dict[str, Any]] = []
        self._rejected: List[Dict[str, Any]] = []
        self._rejection_counts: Dict[str, int] = {}
        self._auth_failures = 0
        self._last_accepted_at: str | None = None
        self._last_rejected_at: str | None = None

    def ingest(self, kind: str, payload: Dict[str, Any], token: str) -> Dict[str, Any]:
        now = self._clock().isoformat()

        if not self._is_authorized(token):
            return self._reject(
                kind=kind,
                payload=payload,
                reason="unauthorized",
                occurred_at=now,
                auth_failure=True,
            )

        if not isinstance(kind, str) or not kind.strip():
            return self._reject(kind=str(kind), payload=payload, reason="invalid_kind", occurred_at=now)
        normalized_kind = kind.strip().lower()

        if not isinstance(payload, dict):
            return self._reject(kind=normalized_kind, payload={}, reason="invalid_payload_type", occurred_at=now)

        encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
        if len(encoded) > self._max_payload_bytes:
            return self._reject(kind=normalized_kind, payload=payload, reason="payload_too_large", occurred_at=now)

        if normalized_kind in self._DISALLOWED_KINDS or self._contains_disallowed_key(payload):
            return self._reject(
                kind=normalized_kind,
                payload=payload,
                reason="trading_authority_not_allowed",
                occurred_at=now,
            )

        with self._lock:
            self._seq += 1
            ingest_id = f"ocli-{self._seq:08d}"
            record = {
                "ingest_id": ingest_id,
                "kind": normalized_kind,
                "received_at": now,
                "payload": json.loads(encoded.decode("utf-8")),
                "status": "accepted",
            }
            self._accepted.append(record)
            self._last_accepted_at = now

        self._log.record(
            "openclaw.ingest.accepted",
            {
                "ingest_id": record["ingest_id"],
                "kind": normalized_kind,
                "run_id": payload.get("run_id"),
                "decision_id": payload.get("decision_id"),
                "agent_id": payload.get("agent_id"),
            },
        )
        return {"accepted": True, "ingest_id": ingest_id, "kind": normalized_kind}

    def health(self) -> Dict[str, Any]:
        with self._lock:
            accepted_count = len(self._accepted)
            rejected_count = len(self._rejected)
            attempts = accepted_count + rejected_count
            rejection_counts = dict(sorted(self._rejection_counts.items(), key=lambda kv: kv[0]))
            status = "healthy" if attempts == 0 or (accepted_count >= rejected_count) else "degraded"
            return {
                "status": status,
                "auth_configured": bool(self._token),
                "total_attempts": attempts,
                "accepted_count": accepted_count,
                "rejected_count": rejected_count,
                "auth_failures": self._auth_failures,
                "last_accepted_at": self._last_accepted_at,
                "last_rejected_at": self._last_rejected_at,
                "rejection_reason_counts": rejection_counts,
            }

    def list_rejected(self, limit: int = 100) -> List[Dict[str, Any]]:
        with self._lock:
            items = list(self._rejected)
        return items[-limit:] if limit >= 0 else items

    def list_accepted(self, limit: int = 100) -> List[Dict[str, Any]]:
        with self._lock:
            items = list(self._accepted)
        return items[-limit:] if limit >= 0 else items

    def _is_authorized(self, token: str) -> bool:
        return bool(self._token) and bool(token) and secrets.compare_digest(str(token), self._token)

    def _contains_disallowed_key(self, payload: Dict[str, Any]) -> bool:
        stack: List[Any] = [payload]
        while stack:
            current = stack.pop()
            if isinstance(current, dict):
                for key, value in current.items():
                    if str(key).strip().lower() in self._DISALLOWED_KEYS:
                        return True
                    stack.append(value)
            elif isinstance(current, list):
                stack.extend(current)
        return False

    def _reject(
        self,
        *,
        kind: str,
        payload: Dict[str, Any],
        reason: str,
        occurred_at: str,
        auth_failure: bool = False,
    ) -> Dict[str, Any]:
        with self._lock:
            self._seq += 1
            reject_id = f"ocli-rej-{self._seq:08d}"
            entry = {
                "reject_id": reject_id,
                "kind": kind,
                "status": "rejected",
                "reason": reason,
                "received_at": occurred_at,
                "payload": payload,
            }
            self._rejected.append(entry)
            self._last_rejected_at = occurred_at
            self._rejection_counts[reason] = self._rejection_counts.get(reason, 0) + 1
            if auth_failure:
                self._auth_failures += 1

        self._log.record(
            "openclaw.ingest.rejected",
            {
                "reject_id": reject_id,
                "kind": kind,
                "reason": reason,
                "run_id": payload.get("run_id") if isinstance(payload, dict) else None,
                "decision_id": payload.get("decision_id") if isinstance(payload, dict) else None,
                "agent_id": payload.get("agent_id") if isinstance(payload, dict) else None,
            },
        )
        return {"accepted": False, "reason": reason, "kind": kind}


openclaw_ingest_service = OpenClawIngestService()
