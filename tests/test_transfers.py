import os
import unittest

from airpoints.transfers import TransferTable

RATIOS = os.path.join(
    os.path.dirname(__file__), "..", "data", "transfer_ratios.yaml"
)


class TransferTableTest(unittest.TestCase):
    def setUp(self):
        self.table = TransferTable.load(RATIOS)
        self.balances = {"amex_mr": 120000, "chase_ur": 80000, "alaska_miles": 45000}

    def test_alaska_held_directly(self):
        path = self.table.cheapest_funding("alaska", 30000, self.balances)
        self.assertIsNotNone(path)
        self.assertEqual(path.currency, "alaska_miles")
        self.assertTrue(path.held_directly)
        self.assertEqual(path.points_required, 30000)
        self.assertTrue(path.affordable)

    def test_alaska_business_unaffordable(self):
        path = self.table.cheapest_funding("alaska", 75000, self.balances)
        self.assertFalse(path.affordable)
        self.assertEqual(path.shortfall, 30000)

    def test_ana_funded_by_amex(self):
        path = self.table.cheapest_funding("ana", 85000, self.balances)
        self.assertEqual(path.currency, "amex_mr")
        self.assertTrue(path.affordable)

    def test_united_funded_by_chase_but_short(self):
        path = self.table.cheapest_funding("united", 88000, self.balances)
        self.assertEqual(path.currency, "chase_ur")
        self.assertFalse(path.affordable)
        self.assertEqual(path.shortfall, 8000)

    def test_unknown_program_has_no_funding(self):
        self.assertIsNone(self.table.cheapest_funding("smiles", 90000, self.balances))

    def test_points_required_rounds_up_on_non_unit_ratio(self):
        table = TransferTable({"x": {"display": "X", "funds": {"p": {"ratio": 1.5}}}})
        path = table.cheapest_funding("p", 1000, {"x": 5000})
        # 1000 / 1.5 = 666.67 -> ceil to 667
        self.assertEqual(path.points_required, 667)

    def test_affordable_path_preferred_over_cheaper_unaffordable(self):
        # program fundable by two currencies: a cheaper one you can't afford,
        # and a pricier one you can. The affordable one should win.
        table = TransferTable(
            {
                "cheap": {"display": "Cheap", "funds": {"p": {"ratio": 2.0}}},
                "rich": {"display": "Rich", "funds": {"p": {"ratio": 1.0}}},
            }
        )
        path = table.cheapest_funding("p", 10000, {"cheap": 100, "rich": 50000})
        self.assertEqual(path.currency, "rich")
        self.assertTrue(path.affordable)


if __name__ == "__main__":
    unittest.main()
