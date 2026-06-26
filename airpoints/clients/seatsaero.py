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


def _to_int(value) -> Optional[int]:
    """seats.aero sends numbers as strings ('30000'); be defensive."""
    if value in (None, ""):
        return None
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


def _taxes_to_usd(raw: dict, prefix: str) -> float:
    """Per-cabin taxes/fees. seats.aero reports these in cents (e.g. '5600')."""
    cents = _to_int(raw.get(f"{prefix}TaxesFees"))
    if cents is None:
        return 0.0
    # Currency field is informational; we treat the minor-unit value as USD
    # cents unless told otherwise. Non-USD currencies pass through unscaled-ish;
    # surface the raw currency in callers if you need exact FX.
    return round(cents / 100.0, 2)


def parse_availability(records: Iterable[dict]) -> list[AwardOption]:
    """Expand raw cached-search records into per-cabin AwardOptions."""
    options: list[AwardOption] = []
    for raw in records:
        route = raw.get("Route") or {}
        origin = route.get("OriginAirport") or raw.get("OriginAirport", "")
        destination = route.get("DestinationAirport") or raw.get(
            "DestinationAirport", ""
        )
        program = raw.get("Source") or route.get("Source", "")
        date = raw.get("Date", "")

        for prefix, cabin in CABIN_PREFIXES.items():
            if not raw.get(f"{prefix}Available"):
                continue
            miles = _to_int(raw.get(f"{prefix}MileageCost"))
            if miles is None or miles <= 0:
                continue
            options.append(
                AwardOption(
                    program=program,
                    origin=origin,
                    destination=destination,
                    date=date,
                    cabin=cabin,
                    miles=miles,
                    taxes_usd=_taxes_to_usd(raw, prefix),
                    airlines=raw.get(f"{prefix}Airlines", "") or "",
                    direct=bool(raw.get(f"{prefix}Direct", False)),
                    remaining_seats=_to_int(raw.get(f"{prefix}RemainingSeats")),
                )
            )
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
