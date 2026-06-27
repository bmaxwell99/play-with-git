import os
import unittest

from airpoints.clients.seatsaero import SeatsAeroClient, parse_availability

FIXTURE = os.path.join(os.path.dirname(__file__), "fixtures", "seatsaero_sample.json")


class ParseAvailabilityTest(unittest.TestCase):
    def setUp(self):
        self.opts = SeatsAeroClient.from_fixture(FIXTURE)

    def test_expands_one_option_per_available_cabin(self):
        # rec-1: economy+business, rec-2: business+first, rec-3: business, rec-4: business
        self.assertEqual(len(self.opts), 6)

    def test_skips_unavailable_cabins(self):
        # rec-1 W/F are not available
        alaska = [o for o in self.opts if o.program == "alaska"]
        cabins = sorted(o.cabin for o in alaska)
        self.assertEqual(cabins, ["business", "economy"])

    def test_parses_miles_and_taxes(self):
        eco = next(
            o for o in self.opts if o.program == "alaska" and o.cabin == "economy"
        )
        self.assertEqual(eco.miles, 30000)
        self.assertEqual(eco.taxes_usd, 56.00)  # "5600" cents -> $56.00
        self.assertTrue(eco.direct)
        self.assertEqual(eco.remaining_seats, 5)
        self.assertEqual(eco.airlines, "JL")

    def test_string_costs_coerced_to_int(self):
        ana_first = next(
            o for o in self.opts if o.program == "ana" and o.cabin == "first"
        )
        self.assertIsInstance(ana_first.miles, int)
        self.assertEqual(ana_first.miles, 165000)

    def test_requires_api_key(self):
        with self.assertRaises(ValueError):
            SeatsAeroClient("")

    def test_parse_accepts_bare_list(self):
        # parse_availability should work on a raw record list too
        self.assertEqual(parse_availability([]), [])


class ConnectionVsNonstopTest(unittest.TestCase):
    """Driven by a real seats.aero record (SFO-CDG jetblue, 2026-07-10).

    Economy has a cheaper connection (32,400, B6+UA) AND a pricier nonstop
    (55,000, UA). They must surface as two distinct options.
    """

    RECORD = {
        "Route": {"OriginAirport": "SFO", "DestinationAirport": "CDG", "Source": "jetblue"},
        "Date": "2026-07-10",
        "Source": "jetblue",
        "YAvailable": True,
        "JAvailable": True,
        "YMileageCostRaw": 32400,
        "JMileageCostRaw": 209600,
        "YDirectMileageCostRaw": 55000,
        "JDirectMileageCostRaw": 0,
        "YTotalTaxes": 560,
        "JTotalTaxes": 560,
        "YDirectTotalTaxes": 560,
        "YAirlines": "B6, UA",
        "JAirlines": "B6",
        "YDirectAirlines": "UA",
        "YRemainingSeats": 9,
        "JRemainingSeats": 2,
        "YDirectRemainingSeats": 9,
        "YDirect": True,
        "JDirect": False,
    }

    def setUp(self):
        self.opts = parse_availability([self.RECORD])

    def test_economy_yields_connection_and_nonstop(self):
        eco = [o for o in self.opts if o.cabin == "economy"]
        self.assertEqual(len(eco), 2)
        by_miles = {o.miles: o for o in eco}
        self.assertEqual(set(by_miles), {32400, 55000})
        self.assertFalse(by_miles[32400].direct)  # cheaper = the connection
        self.assertEqual(by_miles[32400].airlines, "B6, UA")
        self.assertTrue(by_miles[55000].direct)  # pricier = the nonstop
        self.assertEqual(by_miles[55000].airlines, "UA")

    def test_business_no_nonstop_single_option(self):
        biz = [o for o in self.opts if o.cabin == "business"]
        self.assertEqual(len(biz), 1)  # JDirect false -> no second option
        self.assertFalse(biz[0].direct)
        self.assertEqual(biz[0].miles, 209600)

    def test_taxes_in_cents_confirmed(self):
        eco = next(o for o in self.opts if o.cabin == "economy")
        self.assertEqual(eco.taxes_usd, 5.60)  # 560 cents -> $5.60


if __name__ == "__main__":
    unittest.main()
