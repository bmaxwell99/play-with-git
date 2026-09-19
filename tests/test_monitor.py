import json
import os
import tempfile
import unittest

from airpoints.models import AwardOption, FundingPath, PricedOption, Trip
from airpoints.monitor import (
    find_new,
    load_state,
    option_signature,
    run_monitor,
    save_state,
)
from airpoints.transfers import TransferTable

HERE = os.path.dirname(__file__)
FIXTURE = os.path.join(HERE, "fixtures", "seatsaero_sample.json")
RATIOS = os.path.join(HERE, "..", "data", "transfer_ratios.yaml")


def _priced(program, miles, balance, *, cabin="business", date="2026-04-10"):
    award = AwardOption(
        program=program,
        origin="SFO",
        destination="HND",
        date=date,
        cabin=cabin,
        miles=miles,
        taxes_usd=50.0,
    )
    funding = FundingPath.build(
        currency="x",
        currency_display="X",
        program=program,
        ratio=1.0,
        miles_needed=miles,
        transfer_time="instant",
        held_directly=False,
        balance=balance,
    )
    return PricedOption(award=award, funding=funding)


class FindNewTest(unittest.TestCase):
    def test_first_run_all_affordable_are_new(self):
        opts = [_priced("ana", 50000, 60000), _priced("united", 99000, 60000)]
        new, seen = find_new(opts, set())
        self.assertEqual([o.award.program for o in new], ["ana"])  # united unafford.
        self.assertEqual(len(seen), 1)

    def test_seen_options_not_realerted(self):
        opts = [_priced("ana", 50000, 60000)]
        _, seen = find_new(opts, set())
        new, _ = find_new(opts, seen)
        self.assertEqual(new, [])

    def test_price_drop_realerts(self):
        first = [_priced("ana", 60000, 100000)]
        _, seen = find_new(first, set())
        cheaper = [_priced("ana", 45000, 100000)]  # same route/cabin, fewer miles
        new, _ = find_new(cheaper, seen)
        self.assertEqual(len(new), 1)

    def test_max_miles_filters(self):
        opts = [_priced("ana", 95000, 200000)]
        new, seen = find_new(opts, set(), max_miles=90000)
        self.assertEqual(new, [])
        self.assertEqual(seen, set())  # filtered options aren't tracked

    def test_signature_includes_miles(self):
        a = option_signature(_priced("ana", 50000, 1))
        b = option_signature(_priced("ana", 45000, 1))
        self.assertNotEqual(a, b)


class StateTest(unittest.TestCase):
    def test_roundtrip(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "state.json")
            self.assertEqual(load_state(path), set())  # missing file -> empty
            save_state(path, {"a", "b"})
            self.assertEqual(load_state(path), {"a", "b"})
            with open(path) as fh:
                self.assertIn("seen", json.load(fh))


class RunMonitorTest(unittest.TestCase):
    def setUp(self):
        self.table = TransferTable.load(RATIOS)
        self.balances = {"amex_mr": 120000, "chase_ur": 80000, "alaska_miles": 45000}
        self.trip = Trip(
            "Tokyo", "SFO", "HND", "2026-04-01", "2026-04-15",
            cabins=["economy", "business"],
        )

    def test_alerts_once_then_quiet(self):
        captured = []

        def capture(trip, new):
            captured.append((trip.name, [o.award.program for o in new]))

        with tempfile.TemporaryDirectory() as d:
            state = os.path.join(d, "state.json")
            # Run 1: alaska economy (30k) + ana business (85k) are affordable.
            n1 = run_monitor(
                [self.trip], self.balances, self.table, state,
                notifiers=[capture], fetch_kwargs={"fixture": FIXTURE},
            )
            self.assertEqual(n1, 2)
            programs = sorted(captured[0][1])
            self.assertEqual(programs, ["alaska", "ana"])

            # Run 2: nothing new.
            captured.clear()
            n2 = run_monitor(
                [self.trip], self.balances, self.table, state,
                notifiers=[capture], fetch_kwargs={"fixture": FIXTURE},
            )
            self.assertEqual(n2, 0)
            self.assertEqual(captured, [])

    def test_state_persisted_even_when_no_alerts(self):
        with tempfile.TemporaryDirectory() as d:
            state = os.path.join(d, "state.json")
            run_monitor(
                [self.trip], self.balances, self.table, state,
                notifiers=[], fetch_kwargs={"fixture": FIXTURE},
            )
            self.assertTrue(os.path.exists(state))
            self.assertGreater(len(load_state(state)), 0)


if __name__ == "__main__":
    unittest.main()
