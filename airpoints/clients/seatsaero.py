"""seats.aero Partner API client.

seats.aero is the single best personal-scale source of award (points) flight
availability: a real, documented JSON API indexing most loyalty programs
(including Alaska Mileage Plan and the partners Amex/Chase points transfer to).

The cached-search endpoint returns one availability record per route+date, with
per-cabin fields prefixed Y/W/J/F. `parse_availability` expands each record into
one AwardOption per *available* cabin so downstream code never has to know the
wire format.

`requests` is imported lazily inside `search` so the rest of the package — and
the unit tests, which feed recorded JSON to `parse_availability` directly —
import without any network dependency.
"""

from __future__ import annotations

import json
from typing import Iterable, Optional

from ..models import CABIN_PREFIXES, AwardOption

BASE_URL = "https://seats.aero/partnerapi"

# seats.aero reports per-cabin taxes in the field `{prefix}TotalTaxes` (an int).
# Its convention is the smallest currency unit (cents): e.g. 5600 == $56.00.
# If you find a real response where the value is already whole dollars, flip
# this to False. This is the one field unit worth confirming against live data.
TAXES_IN_CENTS = True


def _to_int(value) -> Optional[int]:
    """seats.aero sends mileage costs as strings ('30000'); be defensive."""
    if value in (None, ""):
        return None
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


def _miles(raw: dict, *names: str) -> Optional[int]:
    """First present mileage value among `names` (prefer the int *Raw field,
    fall back to the string field)."""
    for name in names:
        value = _to_int(raw.get(name))
        if value is not None:
            return value
    return None


def _taxes_to_usd(raw: dict, field: str) -> float:
    """Taxes/fees from a `*TotalTaxes` field.

    seats.aero's convention is cents (e.g. 560 == $5.60). `TaxesCurrency` is
    informational; we treat the value as USD — surface it in callers if you
    need exact FX.
    """
    value = _to_int(raw.get(field))
    if value is None:
        return 0.0
    return round(value / 100.0, 2) if TAXES_IN_CENTS else float(value)


def _cabin_options(raw: dict, prefix: str, cabin: str, common: dict) -> list[AwardOption]:
    """Build the AwardOption(s) for one cabin of one record.

    seats.aero packs two things into each cabin: the *cheapest* itinerary
    (`{p}MileageCost`, which may be a connection) and, when `{p}Direct` is set,
    a *nonstop* itinerary (`{p}DirectMileageCost`). We emit the cheapest always,
    and the nonstop separately when it's priced differently — so the
    nonstop-vs-connection mileage trade-off is visible rather than hidden behind
    a single (and previously inaccurate) `direct` flag.
    """
    if not raw.get(f"{prefix}Available"):
        return []
    cheapest = _miles(raw, f"{prefix}MileageCostRaw", f"{prefix}MileageCost")
    if not cheapest or cheapest <= 0:
        return []

    direct_cost = _miles(raw, f"{prefix}DirectMileageCostRaw", f"{prefix}DirectMileageCost")
    has_nonstop = bool(raw.get(f"{prefix}Direct")) and bool(direct_cost) and direct_cost > 0

    options = [
        AwardOption(
            cabin=cabin,
            miles=cheapest,
            taxes_usd=_taxes_to_usd(raw, f"{prefix}TotalTaxes"),
            airlines=raw.get(f"{prefix}Airlines", "") or "",
            direct=has_nonstop and direct_cost == cheapest,
            remaining_seats=_to_int(raw.get(f"{prefix}RemainingSeats")),
            **common,
        )
    ]
    if has_nonstop and direct_cost != cheapest:
        options.append(
            AwardOption(
                cabin=cabin,
                miles=direct_cost,
                taxes_usd=_taxes_to_usd(raw, f"{prefix}DirectTotalTaxes")
                or _taxes_to_usd(raw, f"{prefix}TotalTaxes"),
                airlines=raw.get(f"{prefix}DirectAirlines", "")
                or raw.get(f"{prefix}Airlines", "")
                or "",
                direct=True,
                remaining_seats=_to_int(raw.get(f"{prefix}DirectRemainingSeats")),
                **common,
            )
        )
    return options


def parse_availability(records: Iterable[dict]) -> list[AwardOption]:
    """Expand raw cached-search records into per-cabin AwardOptions."""
    options: list[AwardOption] = []
    for raw in records:
        route = raw.get("Route") or {}
        common = {
            "program": raw.get("Source") or route.get("Source", ""),
            "origin": route.get("OriginAirport") or raw.get("OriginAirport", ""),
            "destination": route.get("DestinationAirport")
            or raw.get("DestinationAirport", ""),
            "date": raw.get("Date", ""),
        }
        for prefix, cabin in CABIN_PREFIXES.items():
            options.extend(_cabin_options(raw, prefix, cabin, common))
    return options


class SeatsAeroClient:
    """Thin wrapper over the seats.aero cached-search endpoint."""

    def __init__(self, api_key: str, base_url: str = BASE_URL, timeout: int = 30):
        if not api_key:
            raise ValueError(
                "seats.aero API key required. Set SEATSAERO_API_KEY in your "
                "environment / .env (never hard-code or paste it)."
            )
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def search(
        self,
        origin: str,
        destination: str,
        start_date: str,
        end_date: str,
        cabin: Optional[str] = None,
        sources: Optional[list[str]] = None,
        max_pages: int = 5,
    ) -> list[AwardOption]:
        """Query cached award availability for a route + date window.

        Pages through results (the API caps each page and returns a cursor).
        `cabin` is the seats.aero cabin name ('economy'/'business'/...);
        `sources` optionally restricts to specific mileage programs.
        """
        import requests  # lazy: keeps import-time dependency-free

        params = {
            "origin_airport": origin,
            "destination_airport": destination,
            "start_date": start_date,
            "end_date": end_date,
            "take": 1000,
        }
        if cabin:
            params["cabin"] = cabin
        if sources:
            params["sources"] = ",".join(sources)

        headers = {
            "Partner-Authorization": self.api_key,
            "Accept": "application/json",
        }

        records: list[dict] = []
        cursor = None
        for _ in range(max_pages):
            if cursor:
                params["cursor"] = cursor
            resp = requests.get(
                f"{self.base_url}/search",
                params=params,
                headers=headers,
                timeout=self.timeout,
            )
            resp.raise_for_status()
            payload = resp.json()
            records.extend(payload.get("data", []))
            if not payload.get("hasMore"):
                break
            cursor = payload.get("cursor")
            if not cursor:
                break

        return parse_availability(records)

    @staticmethod
    def from_fixture(path: str) -> list[AwardOption]:
        """Load and parse a recorded cached-search response (for tests/dev)."""
        with open(path, "r", encoding="utf-8") as fh:
            payload = json.load(fh)
        return parse_availability(payload.get("data", payload))
