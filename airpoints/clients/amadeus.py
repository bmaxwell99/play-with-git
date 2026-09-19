"""Amadeus Self-Service API client — cash flights and hotels.

Amadeus offers a free tier (a client_id / client_secret pair from
developers.amadeus.com) that covers BOTH flight offers and hotel offers, so one
credential unlocks the whole cash side. OAuth2 client-credentials token is
fetched and cached; `requests` is imported lazily so the package and tests load
without a network.

Times in Amadeus responses are *local* (ISO with no timezone), which is exactly
what the user's "no departure before 9am / no landing after 8pm" rule is about —
so the budget filters can compare the time component directly.
"""

from __future__ import annotations

import json
import time
from typing import Optional

from ..models import FlightOffer, HotelOffer

TEST_BASE = "https://test.api.amadeus.com"
PROD_BASE = "https://api.amadeus.com"


def _to_float(value) -> Optional[float]:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def parse_flight_offers(payload: dict) -> list[FlightOffer]:
    """Turn a /v2/shopping/flight-offers response into FlightOffers.

    Each offer's `itineraries` are [outbound, return?]; each itinerary has
    `segments`. Nonstop means one segment per itinerary. Carrier names are
    resolved from `dictionaries.carriers` when present.
    """
    carriers = (payload.get("dictionaries") or {}).get("carriers") or {}
    offers: list[FlightOffer] = []
    for offer in payload.get("data", []):
        itins = offer.get("itineraries") or []
        if not itins:
            continue
        out = itins[0]
        out_segs = out.get("segments") or []
        if not out_segs:
            continue
        first, last = out_segs[0], out_segs[-1]
        code = offer.get("validatingAirlineCodes", [None])[0] or first.get(
            "carrierCode", ""
        )
        price = _to_float((offer.get("price") or {}).get("grandTotal")) or _to_float(
            (offer.get("price") or {}).get("total")
        )
        if price is None:
            continue

        ret_depart = ret_arrive = None
        ret_stops = None
        if len(itins) > 1:
            ret_segs = itins[1].get("segments") or []
            if ret_segs:
                ret_depart = ret_segs[0]["departure"]["at"]
                ret_arrive = ret_segs[-1]["arrival"]["at"]
                ret_stops = len(ret_segs) - 1

        offers.append(
            FlightOffer(
                origin=first["departure"]["iataCode"],
                destination=last["arrival"]["iataCode"],
                depart_at=first["departure"]["at"],
                arrive_at=last["arrival"]["at"],
                price_usd=price,
                carrier=carriers.get(code, code),
                outbound_stops=len(out_segs) - 1,
                return_depart_at=ret_depart,
                return_arrive_at=ret_arrive,
                return_stops=ret_stops,
            )
        )
    return offers


def parse_hotel_offers(payload: dict) -> list[HotelOffer]:
    """Turn a /v3/shopping/hotel-offers response into HotelOffers (cheapest
    offer per hotel)."""
    results: list[HotelOffer] = []
    for entry in payload.get("data", []):
        if entry.get("available") is False:
            continue
        hotel = entry.get("hotel") or {}
        offers = entry.get("offers") or []
        priced = [
            (o, _to_float((o.get("price") or {}).get("total")))
            for o in offers
        ]
        priced = [(o, p) for o, p in priced if p is not None]
        if not priced:
            continue
        offer, total = min(priced, key=lambda op: op[1])
        checkin = offer.get("checkInDate", "")
        checkout = offer.get("checkOutDate", "")
        results.append(
            HotelOffer(
                name=hotel.get("name", "").title() or hotel.get("hotelId", ""),
                total_usd=total,
                nights=_nights(checkin, checkout),
                checkin=checkin,
                checkout=checkout,
                hotel_id=hotel.get("hotelId", ""),
                latitude=hotel.get("latitude"),
                longitude=hotel.get("longitude"),
            )
        )
    return results


def _nights(checkin: str, checkout: str) -> int:
    from datetime import date

    try:
        d1 = date.fromisoformat(checkin)
        d2 = date.fromisoformat(checkout)
        return max(1, (d2 - d1).days)
    except ValueError:
        return 1


class AmadeusClient:
    """OAuth2 client for Amadeus flight + hotel offers (test env by default)."""

    def __init__(
        self,
        client_id: str,
        client_secret: str,
        *,
        base_url: str = TEST_BASE,
        timeout: int = 30,
    ):
        if not client_id or not client_secret:
            raise ValueError(
                "Amadeus credentials required. Set AMADEUS_CLIENT_ID and "
                "AMADEUS_CLIENT_SECRET in your environment / .env."
            )
        self.client_id = client_id
        self.client_secret = client_secret
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self._token: Optional[str] = None
        self._token_expiry: float = 0.0

    def _get_token(self) -> str:
        import requests  # lazy

        if self._token and time.time() < self._token_expiry - 30:
            return self._token
        resp = requests.post(
            f"{self.base_url}/v1/security/oauth2/token",
            data={
                "grant_type": "client_credentials",
                "client_id": self.client_id,
                "client_secret": self.client_secret,
            },
            timeout=self.timeout,
        )
        resp.raise_for_status()
        data = resp.json()
        self._token = data["access_token"]
        self._token_expiry = time.time() + data.get("expires_in", 1799)
        return self._token

    def _get(self, path: str, params: dict) -> dict:
        import requests  # lazy

        resp = requests.get(
            f"{self.base_url}{path}",
            params=params,
            headers={"Authorization": f"Bearer {self._get_token()}"},
            timeout=self.timeout,
        )
        resp.raise_for_status()
        return resp.json()

    def search_flights(
        self,
        origin: str,
        destination: str,
        depart_date: str,
        return_date: Optional[str] = None,
        *,
        adults: int = 1,
        nonstop: bool = True,
        currency: str = "USD",
        max_results: int = 20,
    ) -> list[FlightOffer]:
        params = {
            "originLocationCode": origin,
            "destinationLocationCode": destination,
            "departureDate": depart_date,
            "adults": adults,
            "currencyCode": currency,
            "max": max_results,
        }
        if return_date:
            params["returnDate"] = return_date
        if nonstop:
            params["nonStop"] = "true"
        return parse_flight_offers(self._get("/v2/shopping/flight-offers", params))

    def hotel_ids_for_city(self, city_code: str, limit: int = 30) -> list[str]:
        payload = self._get(
            "/v1/reference-data/locations/hotels/by-city",
            {"cityCode": city_code},
        )
        return [h["hotelId"] for h in payload.get("data", [])][:limit]

    def search_hotels(
        self,
        city_code: str,
        checkin: str,
        checkout: str,
        *,
        adults: int = 1,
        currency: str = "USD",
        hotel_id_limit: int = 30,
    ) -> list[HotelOffer]:
        hotel_ids = self.hotel_ids_for_city(city_code, limit=hotel_id_limit)
        if not hotel_ids:
            return []
        payload = self._get(
            "/v3/shopping/hotel-offers",
            {
                "hotelIds": ",".join(hotel_ids),
                "checkInDate": checkin,
                "checkOutDate": checkout,
                "adults": adults,
                "currency": currency,
                "bestRateOnly": "true",
            },
        )
        return parse_hotel_offers(payload)

    @staticmethod
    def flights_from_fixture(path: str) -> list[FlightOffer]:
        with open(path, "r", encoding="utf-8") as fh:
            return parse_flight_offers(json.load(fh))

    @staticmethod
    def hotels_from_fixture(path: str) -> list[HotelOffer]:
        with open(path, "r", encoding="utf-8") as fh:
            return parse_hotel_offers(json.load(fh))
