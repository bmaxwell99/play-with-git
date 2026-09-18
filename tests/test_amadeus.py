import os
import unittest

from airpoints.clients.amadeus import (
    AmadeusClient,
    parse_flight_offers,
    parse_hotel_offers,
)

HERE = os.path.dirname(__file__)
FLIGHTS = os.path.join(HERE, "fixtures", "amadeus_flights_sample.json")
HOTELS = os.path.join(HERE, "fixtures", "amadeus_hotels_sample.json")


class FlightParseTest(unittest.TestCase):
    def setUp(self):
        self.offers = AmadeusClient.flights_from_fixture(FLIGHTS)

    def test_parses_all_offers(self):
        self.assertEqual(len(self.offers), 3)

    def test_nonstop_roundtrip_fields(self):
        o = next(o for o in self.offers if o.carrier == "JETBLUE AIRWAYS")
        self.assertEqual(o.origin, "JFK")
        self.assertEqual(o.destination, "MSY")
        self.assertEqual(o.price_usd, 168.20)
        self.assertTrue(o.nonstop)
        self.assertEqual(o.depart_at, "2026-11-03T10:30:00")
        self.assertEqual(o.return_arrive_at, "2026-11-06T17:20:00")

    def test_connection_counts_stops(self):
        # offer 3 outbound has two segments -> one stop -> not nonstop
        o = next(o for o in self.offers if o.carrier == "DELTA AIR LINES")
        self.assertEqual(o.outbound_stops, 1)
        self.assertFalse(o.nonstop)
        self.assertEqual(o.origin, "LGA")
        self.assertEqual(o.destination, "MSY")

    def test_grandtotal_preferred(self):
        o = next(o for o in self.offers if o.carrier == "UNITED AIRLINES")
        self.assertEqual(o.price_usd, 142.00)

    def test_requires_credentials(self):
        with self.assertRaises(ValueError):
            AmadeusClient("", "")


class HotelParseTest(unittest.TestCase):
    def setUp(self):
        self.hotels = AmadeusClient.hotels_from_fixture(HOTELS)

    def test_skips_unavailable(self):
        self.assertEqual(len(self.hotels), 2)  # sold-out inn dropped
        self.assertNotIn("Sold Out Inn", [h.name for h in self.hotels])

    def test_cheapest_offer_per_hotel(self):
        hyatt = next(h for h in self.hotels if h.is_hyatt)
        self.assertEqual(hyatt.total_usd, 417.00)  # min of 441 / 417
        self.assertEqual(hyatt.nights, 3)
        self.assertEqual(hyatt.nightly_usd, 139.00)

    def test_hyatt_flagged(self):
        names = {h.name: h.is_hyatt for h in self.hotels}
        self.assertTrue(any(v for v in names.values()))
        ac = next(h for h in self.hotels if "Ac Hotel" in h.name)
        self.assertFalse(ac.is_hyatt)
        self.assertEqual(ac.total_usd, 384.00)

    def test_parse_empty(self):
        self.assertEqual(parse_hotel_offers({}), [])
        self.assertEqual(parse_flight_offers({}), [])


if __name__ == "__main__":
    unittest.main()
