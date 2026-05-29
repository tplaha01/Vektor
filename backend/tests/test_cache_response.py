import asyncio

from pydantic import BaseModel

from app.cache import cache_response, clear_cache


class _SignalPayload(BaseModel):
    symbol: str
    profile: str = "auto"


def test_cache_response_dedupes_in_flight_pydantic_payloads():
    clear_cache()
    calls = 0

    @cache_response(ttl_seconds=30)
    async def handler(payload: _SignalPayload):
        nonlocal calls
        calls += 1
        await asyncio.sleep(0.01)
        return {"symbol": payload.symbol, "calls": calls}

    async def run():
        first, second = await asyncio.gather(
            handler(_SignalPayload(symbol="AAPL")),
            handler(_SignalPayload(symbol="AAPL")),
        )
        third = await handler(_SignalPayload(symbol="MSFT"))
        return first, second, third

    first, second, third = asyncio.run(run())

    assert first == second
    assert first["symbol"] == "AAPL"
    assert third["symbol"] == "MSFT"
    assert calls == 2
    clear_cache()
