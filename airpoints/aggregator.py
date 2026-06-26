"""Merge award availability + balances + transfer table into priced options."""

from __future__ import annotations

from .models import AwardOption, PricedOption, Trip
from .transfers import TransferTable


def price_options(
    awards: list[AwardOption],
    balances: dict[str, int],
    table: TransferTable,
    trip: Trip | None = None,
) -> list[PricedOption]:
    """Annotate each award with the user's cheapest funding path.

    If `trip` is given, options are filtered to its requested cabins. Options
    whose program can't be funded from any of the user's currencies are kept
    (with funding=None) so the caller can show them as "no funding path"
    rather than pretending they don't exist.
    """
    priced: list[PricedOption] = []
    for award in awards:
        if trip is not None and not trip.wants_cabin(award.cabin):
            continue
        funding = table.cheapest_funding(award.program, award.miles, balances)
        priced.append(PricedOption(award=award, funding=funding))
    return priced


def affordable_only(options: list[PricedOption]) -> list[PricedOption]:
    return [o for o in options if o.affordable]
