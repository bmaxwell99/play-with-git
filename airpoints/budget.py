"""Budget trip optimizer: combine cash flights + hotels under time constraints.

Given candidate travel windows (each a depart/return date pair) and the user's
hard rules — nonstop only, no departure before 9am, no landing after 8pm, on
*either* leg — pick the cheapest compliant flight and cheapest hotel per window,
then rank windows by total cash cost.

The flight-time rule is applied to both legs because the user dislikes early
departures and late landings on any flight, not just the outbound.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, time
from typing import Optional

from .models import FlightOffer, HotelOffer, TripOption


@dataclass
class Constraints:
    nonstop: bool = True
    earliest_depart: str = "09:00"  # no flight departs before this (local)
    latest_arrival: str = "20:00"  # no flight lands after this (local)


def _hhmm(s: str) -> time:
    h, m = s.split(":")
    return time(int(h), int(m))


def _leg_ok(depart_at: str, arrive_at: str, earliest: time, latest: time) -> bool:
    try:
        if datetime.fromisoformat(depart_at).time() < earliest:
            return False
        if datetime.fromisoformat(arrive_at).time() > latest:
            return False
    except (ValueError, TypeError):
        return False
    return True


def flight_ok(offer: FlightOffer, c: Constraints) -> bool:
    """Both legs must depart >= earliest and arrive <= latest; nonstop if asked."""
    if c.nonstop and not offer.nonstop:
        return False
    earliest, latest = _hhmm(c.earliest_depart), _hhmm(c.latest_arrival)
    if not _leg_ok(offer.depart_at, offer.arrive_at, earliest, latest):
        return False
    if offer.return_depart_at and offer.return_arrive_at:
        if not _leg_ok(offer.return_depart_at, offer.return_arrive_at, earliest, latest):
            return False
    return True


def cheapest_flight(
    offers: list[FlightOffer], c: Constraints = Constraints()
) -> Optional[FlightOffer]:
    ok = [o for o in offers if flight_ok(o, c)]
    return min(ok, key=lambda o: o.price_usd) if ok else None


def cheapest_hotel(
    offers: list[HotelOffer], *, prefer_hyatt: bool = False
) -> Optional[HotelOffer]:
    """Cheapest hotel. With prefer_hyatt, the cheapest Hyatt wins when present
    (it's the one bookable on Chase points), else fall back to cheapest overall."""
    if not offers:
        return None
    if prefer_hyatt:
        hyatts = [h for h in offers if h.is_hyatt]
        if hyatts:
            return min(hyatts, key=lambda h: h.total_usd)
    return min(offers, key=lambda h: h.total_usd)


@dataclass
class Window:
    """One candidate trip: a labeled date pair plus the offers fetched for it."""

    name: str
    origin: str  # label, e.g. "NYC" (may span multiple airports)
    destination: str
    flights: list[FlightOffer] = field(default_factory=list)
    hotels: list[HotelOffer] = field(default_factory=list)


def build_option(
    window: Window, c: Constraints = Constraints(), *, prefer_hyatt: bool = False
) -> Optional[TripOption]:
    flight = cheapest_flight(window.flights, c)
    if flight is None:
        return None  # no constraint-compliant flight this window
    hotel = cheapest_hotel(window.hotels, prefer_hyatt=prefer_hyatt)
    return TripOption(
        window=window.name,
        origin=window.origin,
        destination=window.destination,
        flight=flight,
        hotel=hotel,
    )


def rank_windows(
    windows: list[Window], c: Constraints = Constraints(), *, prefer_hyatt: bool = False
) -> list[TripOption]:
    """Cheapest-total-first ranking across all windows (windows with no
    compliant flight are dropped)."""
    options = [build_option(w, c, prefer_hyatt=prefer_hyatt) for w in windows]
    return sorted((o for o in options if o), key=lambda o: o.total_usd)
