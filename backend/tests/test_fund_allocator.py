from decimal import Decimal

from app.fund.allocator import SleeveAllocationRequest, SleeveAllocator, allocate_sleeves


def test_allocator_assigns_full_capital_with_cent_accuracy():
    allocator = SleeveAllocator()
    out = allocator.allocate(100_000.0)
    total = out["long_term"] + out["recurring"] + out["tactical"]
    assert round(total, 2) == 100_000.00


def test_allocate_sleeves_applies_reserve_cash():
    request = SleeveAllocationRequest(
        run_id="run-alloc-1",
        total_capital_usd=Decimal("100000"),
        reserve_cash_usd=Decimal("10000"),
    )
    result = allocate_sleeves(request)
    assert result.allocatable_capital_usd == Decimal("90000.00")
    assert result.allocated_capital_usd == Decimal("90000.00")
