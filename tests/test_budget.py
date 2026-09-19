import os
import unittest

from airpoints.budget import (
    Constraints,
    Window,
    build_option,
    cheapest_flight,
    cheapest_hotel,
    flight_ok,
    rank_windows,
)
from airpoints.clients.amadeus import AmadeusClient
from airpoints.models import FlightOffer

HERE = os.path.dirname(__file__)
FLIGHTS = os.path.join(HERE, "fixtures", "amadeus_flights_sample.json")
HOTELS = os.path.join(HERE, "fixtures", "amadeus_hotels_sample.json")


def _offer(depart, arrive, r_depart=None, r_arrive=None, stops=0, r_stops=None, price=200.0):
    return FlightOffer(
        origin="JFK", destination="MSY",
        depart_at=depart, arrive_at=arrive,
        return_depart_at=r_depart, return_arrive_at=r_arrive,
        outbound_stops=stops, return_stops=r_stops, price_usd=price,
    )


class FlightConstraintTest(unittest.TestCase):
    C = Constraints()  # nonstop, 09:00 dep, 20:00 arr

    def test_compliant_nonstop_passes(self):
        o = _offer("2026-11-03T10:30:00", "2026-11-03T12:45:00",
                   "2026-11-06T13:00:00", "2026-11-06T17:20:00")
        self.assertTrue(flight_ok(o, self.C))

    def test_early_departure_rejected(self):
        o = _offer("2026-11-03T07:15:00", "2026-11-03T09:40:00",
                   "2026-11-06T13:00:00", "2026-11-06T17:20:00")
        self.assertFalse(flight_ok(o, self.C))

    def test_late_landing_rejected(self):
        o = _offer("2026-11-03T10:30:00", "2026-11-03T12:45:00",
                   "2026-11-06T18:00:00", "2026-11-06T21:10:00")  # lands 21:10
        self.assertFalse(flight_ok(o, self.C))

    def test_connection_rejected_when_nonstop(self):
        o = _offer("2026-11-03T10:00:00", "2026-11-03T16:00:00", stops=1)
        self.assertFalse(flight_ok(o, self.C))

    def test_connection_allowed_when_nonstop_off(self):
        o = _offer("2026-11-03T10:00:00", "2026-11-03T16:00:00", stops=1)
        self.assertTrue(flight_ok(o, Constraints(nonstop=False)))


class CheapestSelectionTest(unittest.TestCase):
    def setUp(self):
        self.flights = AmadeusClient.flights_from_fixture(FLIGHTS)
        self.hotels = AmadeusClient.hotels_from_fixture(HOTELS)

    def test_cheapest_compliant_flight_is_jetblue(self):
        # UA is cheaper but departs 07:15; DL is cheapest but has a stop.
        # Only JetBlue ($168.20) satisfies nonstop + time rules.
        f = cheapest_flight(self.flights, Constraints())
        self.assertEqual(f.carrier, "JETBLUE AIRWAYS")
        self.assertEqual(f.price_usd, 168.20)

    def test_dropping_nonstop_lets_cheaper_connection_win(self):
        f = cheapest_flight(self.flights, Constraints(nonstop=False))
        self.assertEqual(f.carrier, "DELTA AIR LINES")  # $121.40 connection
        self.assertEqual(f.price_usd, 121.40)

    def test_cheapest_hotel_overall_vs_prefer_hyatt(self):
        self.assertEqual(cheapest_hotel(self.hotels).total_usd, 384.00)  # AC
        self.assertTrue(cheapest_hotel(self.hotels, prefer_hyatt=True).is_hyatt)

    def test_no_compliant_flight_returns_none(self):
        early = [_offer("2026-11-03T06:00:00", "2026-11-03T08:00:00")]
        self.assertIsNone(cheapest_flight(early, Constraints()))


class RankTest(unittest.TestCase):
    def setUp(self):
        self.flights = AmadeusClient.flights_from_fixture(FLIGHTS)
        self.hotels = AmadeusClient.hotels_from_fixture(HOTELS)

    def test_build_option_totals_flight_plus_hotel(self):
        w = Window("Nov", "NYC", "MSY", self.flights, self.hotels)
        opt = build_option(w, Constraints(), prefer_hyatt=True)
        # JetBlue 168.20 + Hyatt 417.00
        self.assertAlmostEqual(opt.total_usd, 585.20, places=2)

    def test_rank_orders_by_total_and_drops_flightless(self):
        good = Window("Nov", "NYC", "MSY", self.flights, self.hotels)
        # window with only an early-departure flight -> no compliant option
        bad = Window(
            "BadDates", "NYC", "MSY",
            [_offer("2026-12-01T06:00:00", "2026-12-01T08:00:00")],
            self.hotels,
        )
        ranked = rank_windows([bad, good], Constraints())
        self.assertEqual(len(ranked), 1)
        self.assertEqual(ranked[0].window, "Nov")


if __name__ == "__main__":
    unittest.main()
