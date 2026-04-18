from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from threading import RLock
from typing import Any, Literal

from app.config import get_settings

DataMode = Literal["provider", "fallback", "failed"]


def _utc_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


@dataclass(frozen=True)
class ProviderEvent:
    provider: str
    mode: DataMode
    at: str
    symbol: str | None
    detail: str | None


class DataIntegrityGuard:
    """
    Global runtime guard for strict provider-only data policies.

    Behavior:
    - Tracks provider/fallback/failed data events.
    - When strict mode is enabled, any fallback/failed event trips a system halt.
    - Halt state is read by runtime/execution layers to stop further activity.
    """

    def __init__(self, *, strict_real_data_only: bool) -> None:
        self._strict = bool(strict_real_data_only)
        self._lock = RLock()
        self._halted = False
        self._halt_reason: str | None = None
        self._halted_at: str | None = None
        self._last_event: ProviderEvent | None = None
        self._provider_states: dict[str, dict[str, Any]] = {}

    def strict_mode_enabled(self) -> bool:
        return self._strict

    def record_provider_event(
        self,
        *,
        provider: str,
        mode: DataMode,
        symbol: str | None = None,
        detail: str | None = None,
    ) -> None:
        provider_key = str(provider or "unknown").strip().lower() or "unknown"
        now = _utc_iso()
        event = ProviderEvent(
            provider=provider_key,
            mode=mode,
            at=now,
            symbol=(str(symbol).upper().strip() if symbol else None),
            detail=(str(detail).strip() if detail else None),
        )

        with self._lock:
            self._last_event = event
            self._provider_states[provider_key] = {
                "provider": provider_key,
                "mode": mode,
                "last_at": now,
                "symbol": event.symbol,
                "detail": event.detail,
            }
            if self._strict and mode in {"fallback", "failed"}:
                self._halted = True
                self._halt_reason = (
                    f"real_data_required:{provider_key}:{event.detail}"
                    if event.detail
                    else f"real_data_required:{provider_key}:{mode}"
                )
                self._halted_at = now

    def halted(self) -> bool:
        with self._lock:
            return self._halted

    def halt_reason(self) -> str | None:
        with self._lock:
            return self._halt_reason

    def assert_not_halted(self) -> None:
        with self._lock:
            if self._halted:
                raise RuntimeError(self._halt_reason or "system_halted")

    def clear_halt(self, *, reason: str = "manual_clear") -> dict[str, Any]:
        now = _utc_iso()
        with self._lock:
            prev_reason = self._halt_reason
            prev_halted_at = self._halted_at
            self._halted = False
            self._halt_reason = None
            self._halted_at = None
        return {
            "cleared": True,
            "cleared_at": now,
            "reason": reason,
            "previous_halt_reason": prev_reason,
            "previous_halted_at": prev_halted_at,
        }

    def status(self) -> dict[str, Any]:
        with self._lock:
            states = [dict(row) for row in self._provider_states.values()]
            last_event = {
                "provider": self._last_event.provider,
                "mode": self._last_event.mode,
                "at": self._last_event.at,
                "symbol": self._last_event.symbol,
                "detail": self._last_event.detail,
            } if self._last_event else None
            degraded = any(row.get("mode") in {"fallback", "failed"} for row in states)
            data_source_status = "Fallback" if degraded else "Provider"
            return {
                "strict_real_data_only": self._strict,
                "halted": self._halted,
                "halt_reason": self._halt_reason,
                "halted_at": self._halted_at,
                "data_source_status": data_source_status,
                "last_event": last_event,
                "providers": sorted(states, key=lambda row: row.get("provider") or ""),
            }


def _build_guard() -> DataIntegrityGuard:
    settings = get_settings()
    return DataIntegrityGuard(strict_real_data_only=settings.REAL_DATA_STRICT_MODE)


data_integrity_guard = _build_guard()

