"""Core data structures for the airline-points aggregator.

These are plain dataclasses so the core logic runs with only the standard
library — no pydantic, no third-party deps. The Anthropic SDK and `requests`
are pulled in lazily elsewhere, only when actually talking to a network.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Optional

# seats.aero encodes cabins as single-letter prefixes on its availability
# records (YMileageCost, JAvailable, ...). Map them to friendly names.
CABIN_PREFIXES = {
    "Y": "economy",
    "W": "premium",
    "J": "business",
    "F": "first",
}
CABINS = list(CABIN_PREFIXES.values())
PREFIX_FOR_CABIN = {v: k for k, v in CABIN_PREFIXES.items()}


@dataclass
class Trip:
    """A route + date window the user wants monitored."""

    name: str
    origin: str
    destination: str
    earliest: str  # YYYY-MM-DD
    latest: str  # YYYY-MM-DD
    cabins: list[str] = field(default_factory=lambda: list(CABINS))
    passengers: int = 1

    def wants_cabin(self, cabin: str) -> bool:
        return cabin in self.cabins


@dataclass
class AwardOption:
    """A single bookable award (one cabin, one date) from seats.aero."""

    program: str  # seats.aero "Source" slug, e.g. "alaska", "aeroplan"
    origin: str
    destination: str
    date: str
    cabin: str  # friendly cabin name
    miles: int  # mileage cost per passenger
    taxes_usd: float  # cash co-pay per passenger, in USD
    airlines: str = ""  # operating carrier code(s), e.g. "JL"
    direct: bool = False  # nonstop availability
    remaining_seats: Optional[int] = None


@dataclass
class FundingPath:
    """How the user would pay for an award: which currency, at what cost."""

    currency: str  # e.g. "amex_mr", "chase_ur", "alaska_miles"
    currency_display: str
    program: str  # program the points are transferred into
    ratio: float  # program-miles produced per 1 point of `currency`
    miles_needed: int  # program miles required (per passenger)
    points_required: int  # points of `currency` required (per passenger)
    transfer_time: str = ""
    held_directly: bool = False  # currency already is the program currency
    balance: int = 0  # current balance in `currency`

    @property
    def affordable(self) -> bool:
        return self.balance >= self.points_required

    @property
    def shortfall(self) -> int:
        return max(0, self.points_required - self.balance)

    @classmethod
    def build(
        cls,
        *,
        currency: str,
        currency_display: str,
        program: str,
        ratio: float,
        miles_needed: int,
        transfer_time: str,
        held_directly: bool,
        balance: int,
    ) -> "FundingPath":
        points_required = math.ceil(miles_needed / ratio) if ratio else 0
        return cls(
            currency=currency,
            currency_display=currency_display,
            program=program,
            ratio=ratio,
            miles_needed=miles_needed,
            points_required=points_required,
            transfer_time=transfer_time,
            held_directly=held_directly,
            balance=balance,
        )


@dataclass
class PricedOption:
    """An award option annotated with the user's cheapest way to pay for it."""

    award: AwardOption
    funding: Optional[FundingPath]  # None => no known way to fund this program

    @property
    def affordable(self) -> bool:
        return self.funding is not None and self.funding.affordable

    @property
    def total_miles_per_pax(self) -> int:
        return self.award.miles

    def summary(self) -> str:
        a = self.award
        base = (
            f"{a.origin}->{a.destination} {a.date} {a.cabin} "
            f"{a.miles:,} {a.program} miles + ${a.taxes_usd:,.0f}"
        )
        if self.funding is None:
            return base + " [no funding path]"
        f = self.funding
        if f.held_directly:
            pay = f"pay from {f.currency_display}"
        else:
            pay = (
                f"transfer {f.points_required:,} {f.currency_display} "
                f"-> {f.program} ({f.transfer_time})"
            )
        status = "AFFORDABLE" if f.affordable else f"short {f.shortfall:,}"
        return f"{base} | {pay} | {status}"
