"""Shared fetch + price pipeline used by both the CLI and the monitor."""

from __future__ import annotations

import os

from .aggregator import price_options
from .clients.seatsaero import SeatsAeroClient
from .models import AwardOption, PricedOption, Trip
from .transfers import TransferTable


def fetch_for_trip(
    trip: Trip,
    *,
    fixture: str | None = None,
    api_key: str | None = None,
    client: SeatsAeroClient | None = None,
) -> list[AwardOption]:
    """Pull award availability for one trip.

    `fixture` reads a recorded JSON response (offline). Otherwise a live
    SeatsAeroClient is used — pass one in for tests, or let it build from
    `api_key` / the SEATSAERO_API_KEY env var. Searches each requested cabin.
    """
    if fixture:
        return SeatsAeroClient.from_fixture(fixture)

    if client is None:
        client = SeatsAeroClient(api_key or os.environ.get("SEATSAERO_API_KEY", ""))

    # One query, no cabin filter — each record already carries every cabin, so
    # the parser expands them all and price_options() keeps only the cabins this
    # trip asked for. (Querying per-cabin would re-emit the same record's cabins
    # once per request, producing duplicates.)
    return client.search(
        origin=trip.origin,
        destination=trip.destination,
        start_date=trip.earliest,
        end_date=trip.latest,
    )


def priced_for_trip(
    trip: Trip,
    balances: dict[str, int],
    table: TransferTable,
    **fetch_kwargs,
) -> list[PricedOption]:
    """Fetch + price one trip's awards against the user's balances."""
    awards = fetch_for_trip(trip, **fetch_kwargs)
    return price_options(awards, balances, table, trip)
