from __future__ import annotations

from datetime import datetime, timedelta, timezone
from threading import RLock
from typing import Any
from uuid import uuid4

from app.storage import db as storage_db


def _utc_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


class ApprovalCenter:
    def __init__(self) -> None:
        self._lock = RLock()

    def create_request(
        self,
        *,
        request_type: str,
        run_id: str | None,
        subject_id: str | None,
        requested_by: str,
        summary: str,
        payload: dict[str, Any] | None = None,
        expires_in_hours: float | None = 24.0,
    ) -> dict[str, Any]:
        now = _utc_iso()
        expires_at = None
        if expires_in_hours and expires_in_hours > 0:
            expires_at = (
                datetime.now(timezone.utc) + timedelta(hours=float(expires_in_hours))
            ).replace(microsecond=0).isoformat().replace("+00:00", "Z")
        row = {
            "request_id": f"apr-{uuid4().hex}",
            "run_id": str(run_id or "").strip() or None,
            "request_type": str(request_type or "unknown").strip().lower(),
            "subject_id": str(subject_id or "").strip() or None,
            "requested_by": str(requested_by or "vektor"),
            "status": "pending",
            "summary": str(summary or "Approval required"),
            "payload": dict(payload or {}),
            "created_at": now,
            "updated_at": now,
            "expires_at": expires_at,
        }
        with self._lock:
            storage_db.save_approval_request(row)
        return row

    def get_request(self, request_id: str) -> dict[str, Any] | None:
        try:
            row = storage_db.load_approval_request(str(request_id or "").strip())
        except RuntimeError:
            return None
        if not row:
            return None
        return self._normalize_request_status(row)

    def list_requests(
        self,
        *,
        limit: int = 100,
        status: str | None = None,
        request_type: str | None = None,
        run_id: str | None = None,
        subject_id: str | None = None,
    ) -> list[dict[str, Any]]:
        try:
            rows = storage_db.load_approval_requests(
                limit=limit,
                status=status,
                request_type=request_type,
                run_id=run_id,
                subject_id=subject_id,
            )
        except RuntimeError:
            return []
        return [self._normalize_request_status(row) for row in rows]

    def resolve_request(
        self,
        request_id: str,
        *,
        resolution: str,
        reviewed_by: str,
        notes: str | None = None,
        resolution_payload: dict[str, Any] | None = None,
    ) -> dict[str, Any] | None:
        row = self.get_request(request_id)
        if not row:
            return None
        clean_resolution = str(resolution or "").strip().lower()
        if clean_resolution not in {"approved", "rejected"}:
            raise ValueError("invalid_resolution")
        payload = dict(row.get("payload") or {})
        payload["review"] = {
            "resolution": clean_resolution,
            "reviewed_by": str(reviewed_by or "vektor"),
            "reviewed_at": _utc_iso(),
            "notes": str(notes or "").strip(),
            **dict(resolution_payload or {}),
        }
        updated = {
            **row,
            "status": clean_resolution,
            "payload": payload,
            "updated_at": _utc_iso(),
        }
        with self._lock:
            storage_db.save_approval_request(updated)
        return updated

    def find_pending_by_subject(self, *, request_type: str | None = None, subject_id: str | None = None) -> dict[str, Any] | None:
        if not subject_id:
            return None
        rows = self.list_requests(limit=20, status="pending", request_type=request_type, subject_id=subject_id)
        return rows[0] if rows else None

    def _normalize_request_status(self, row: dict[str, Any]) -> dict[str, Any]:
        payload = dict(row.get("payload") or {})
        status = str(row.get("status") or "pending").strip().lower() or "pending"
        expires_at = str(row.get("expires_at") or "").strip()
        if status == "pending" and expires_at:
            try:
                expires_dt = datetime.fromisoformat(expires_at.replace("Z", "+00:00"))
                if expires_dt <= datetime.now(timezone.utc):
                    status = "expired"
            except Exception:
                pass
        return {
            **row,
            "status": status,
            "payload": payload,
        }


approval_center = ApprovalCenter()
