from app.fund.runtime_guard import DataIntegrityGuard


def test_strict_guard_halts_on_fallback_event():
    guard = DataIntegrityGuard(strict_real_data_only=True)
    guard.record_provider_event(
        provider="newsapi",
        mode="fallback",
        symbol="AAPL",
        detail="missing_newsapi_key",
    )

    assert guard.halted() is True
    assert (guard.halt_reason() or "").startswith("real_data_required:newsapi")

    status = guard.status()
    assert status["strict_real_data_only"] is True
    assert status["halted"] is True
    assert status["data_source_status"] == "Fallback"
    assert status["last_event"]["provider"] == "newsapi"
    assert status["last_event"]["symbol"] == "AAPL"


def test_non_strict_guard_tracks_degraded_without_halt():
    guard = DataIntegrityGuard(strict_real_data_only=False)
    guard.record_provider_event(
        provider="fmp",
        mode="failed",
        symbol="MSFT",
        detail="provider_timeout",
    )

    assert guard.halted() is False
    assert guard.halt_reason() is None

    status = guard.status()
    assert status["strict_real_data_only"] is False
    assert status["data_source_status"] == "Fallback"
    assert status["providers"][0]["provider"] == "fmp"
