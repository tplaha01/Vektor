from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal, ROUND_FLOOR, ROUND_HALF_UP
from typing import Mapping, Sequence

from pydantic import Field, model_validator

from app.fund.contracts import ImmutableModel, SLEEVE_ORDER, Sleeve, make_immutable_id

ZERO = Decimal("0")
CENT = Decimal("0.01")
SLEEVE_KEYS: tuple[str, ...] = tuple(sleeve.value for sleeve in SLEEVE_ORDER)


class SleeveWeights(ImmutableModel):
    long_term: Decimal = Field(default=Decimal("0.50"), ge=ZERO, le=Decimal("1"))
    recurring: Decimal = Field(default=Decimal("0.30"), ge=ZERO, le=Decimal("1"))
    tactical: Decimal = Field(default=Decimal("0.20"), ge=ZERO, le=Decimal("1"))

    @model_validator(mode="after")
    def _validate_total(self) -> "SleeveWeights":
        total = self.long_term + self.recurring + self.tactical
        if abs(total - Decimal("1")) > Decimal("0.0000001"):
            raise ValueError("Sleeve weights must sum to 1.0")
        return self

    def for_sleeve(self, sleeve: Sleeve) -> Decimal:
        if sleeve == Sleeve.LONG_TERM:
            return self.long_term
        if sleeve == Sleeve.RECURRING:
            return self.recurring
        return self.tactical

    def as_dict(self) -> dict[str, float]:
        return {
            "long_term": float(self.long_term),
            "recurring": float(self.recurring),
            "tactical": float(self.tactical),
        }


class SleeveAllocationRequest(ImmutableModel):
    run_id: str = Field(..., min_length=3, max_length=128)
    decision_id: str | None = Field(default=None, min_length=3, max_length=128)
    total_capital_usd: Decimal = Field(..., gt=ZERO)
    reserve_cash_usd: Decimal = Field(default=ZERO, ge=ZERO)
    target_weights: SleeveWeights = Field(default_factory=SleeveWeights)

    @model_validator(mode="after")
    def _validate_capital(self) -> "SleeveAllocationRequest":
        if self.reserve_cash_usd >= self.total_capital_usd:
            raise ValueError("reserve_cash_usd must be less than total_capital_usd")
        return self


class SleeveAllocationLine(ImmutableModel):
    sleeve: Sleeve
    weight: Decimal = Field(..., ge=ZERO, le=Decimal("1"))
    cents: int = Field(..., ge=0)
    amount_usd: Decimal = Field(..., ge=ZERO)


class SleeveAllocationResult(ImmutableModel):
    allocation_id: str = Field(..., min_length=8, max_length=128)
    run_id: str = Field(..., min_length=3, max_length=128)
    decision_id: str | None = Field(default=None, min_length=3, max_length=128)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    total_capital_usd: Decimal = Field(..., ge=ZERO)
    reserve_cash_usd: Decimal = Field(..., ge=ZERO)
    allocatable_capital_usd: Decimal = Field(..., ge=ZERO)
    lines: tuple[SleeveAllocationLine, ...] = Field(..., min_length=3, max_length=3)

    @property
    def allocated_capital_usd(self) -> Decimal:
        return sum((line.amount_usd for line in self.lines), ZERO)


def _to_cents(value: Decimal) -> int:
    cents = (value / CENT).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
    return int(cents)


def _from_cents(cents: int) -> Decimal:
    return (Decimal(cents) * CENT).quantize(CENT)


def _allocate_cents(total_cents: int, weights: Sequence[tuple[Sleeve, Decimal]]) -> dict[Sleeve, int]:
    if total_cents < 0:
        raise ValueError("total_cents must be non-negative")

    floor_map: dict[Sleeve, int] = {}
    fractional_parts: list[tuple[Decimal, Sleeve]] = []

    for sleeve, weight in weights:
        raw_cents = Decimal(total_cents) * weight
        floor_cents = int(raw_cents.to_integral_value(rounding=ROUND_FLOOR))
        floor_map[sleeve] = floor_cents
        fractional_parts.append((raw_cents - Decimal(floor_cents), sleeve))

    assigned = sum(floor_map.values())
    remainder = total_cents - assigned
    if remainder < 0:
        raise ValueError("invalid allocation state: assigned cents exceed total cents")

    ordered_remainders = sorted(
        fractional_parts,
        key=lambda item: (-item[0], SLEEVE_ORDER.index(item[1])),
    )

    for index in range(remainder):
        sleeve = ordered_remainders[index % len(ordered_remainders)][1]
        floor_map[sleeve] += 1

    return floor_map


class SleeveAllocator:
    """
    Deterministic sleeve allocator for long_term, recurring, tactical.
    """

    def __init__(self, base_weights: Mapping[str, float] | None = None) -> None:
        provided = dict(base_weights) if base_weights is not None else {
            "long_term": 0.50,
            "recurring": 0.30,
            "tactical": 0.20,
        }
        self._base_weights = self._normalize_weights(provided, context="base_weights")

    @staticmethod
    def _normalize_weights(weights: Mapping[str, float], *, context: str) -> dict[str, Decimal]:
        unknown = set(weights.keys()) - set(SLEEVE_KEYS)
        if unknown:
            raise ValueError(f"{context} contains unsupported sleeves: {sorted(unknown)}")

        normalized_inputs = {key: Decimal(str(weights.get(key, 0.0))) for key in SLEEVE_KEYS}
        if any(value < ZERO for value in normalized_inputs.values()):
            raise ValueError(f"{context} cannot contain negative values")

        total = sum(normalized_inputs.values())
        if total <= ZERO:
            raise ValueError(f"{context} must sum to a positive value")

        return {key: normalized_inputs[key] / total for key in SLEEVE_KEYS}

    def _resolved_weights(self, sleeve_scores: Mapping[str, float] | None) -> dict[str, Decimal]:
        if sleeve_scores is None:
            return dict(self._base_weights)

        unknown = set(sleeve_scores.keys()) - set(SLEEVE_KEYS)
        if unknown:
            raise ValueError(f"sleeve_scores contains unsupported sleeves: {sorted(unknown)}")

        scores = {key: Decimal(str(sleeve_scores.get(key, 1.0))) for key in SLEEVE_KEYS}
        if any(score < ZERO for score in scores.values()):
            raise ValueError("sleeve_scores cannot contain negative values")

        weighted = {key: self._base_weights[key] * scores[key] for key in SLEEVE_KEYS}
        if sum(weighted.values()) <= ZERO:
            return dict(self._base_weights)

        return self._normalize_weights({key: float(value) for key, value in weighted.items()}, context="resolved_weights")

    def allocate(self, total_capital: float, sleeve_scores: dict[str, float] | None = None) -> dict[str, float]:
        capital = Decimal(str(total_capital)).quantize(CENT, rounding=ROUND_HALF_UP)
        if capital <= ZERO:
            raise ValueError("total_capital must be positive")

        weights = self._resolved_weights(sleeve_scores)
        total_cents = _to_cents(capital)
        cents_map = _allocate_cents(
            total_cents,
            [
                (Sleeve.LONG_TERM, weights["long_term"]),
                (Sleeve.RECURRING, weights["recurring"]),
                (Sleeve.TACTICAL, weights["tactical"]),
            ],
        )

        return {
            "long_term": float(_from_cents(cents_map[Sleeve.LONG_TERM])),
            "recurring": float(_from_cents(cents_map[Sleeve.RECURRING])),
            "tactical": float(_from_cents(cents_map[Sleeve.TACTICAL])),
        }


def allocate_sleeves(request: SleeveAllocationRequest) -> SleeveAllocationResult:
    allocatable_usd = (request.total_capital_usd - request.reserve_cash_usd).quantize(CENT, rounding=ROUND_HALF_UP)
    allocator = SleeveAllocator(base_weights=request.target_weights.as_dict())
    allocated = allocator.allocate(float(allocatable_usd))

    lines = tuple(
        SleeveAllocationLine(
            sleeve=sleeve,
            weight=request.target_weights.for_sleeve(sleeve),
            cents=_to_cents(Decimal(str(allocated[sleeve.value]))),
            amount_usd=Decimal(str(allocated[sleeve.value])).quantize(CENT),
        )
        for sleeve in SLEEVE_ORDER
    )

    allocation_id = make_immutable_id(
        "alloc",
        request.run_id,
        request.decision_id or "none",
        str(request.total_capital_usd),
        str(request.reserve_cash_usd),
        str(request.target_weights.long_term),
        str(request.target_weights.recurring),
        str(request.target_weights.tactical),
        *(str(line.cents) for line in lines),
    )

    return SleeveAllocationResult(
        allocation_id=allocation_id,
        run_id=request.run_id,
        decision_id=request.decision_id,
        total_capital_usd=request.total_capital_usd,
        reserve_cash_usd=request.reserve_cash_usd,
        allocatable_capital_usd=allocatable_usd,
        lines=lines,
    )
