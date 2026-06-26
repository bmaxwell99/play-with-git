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


if __name__ == "__main__":
    unittest.main()
