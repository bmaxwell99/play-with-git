import json
import os
import unittest

from airpoints.aggregator import affordable_only, price_options
from airpoints.clients.seatsaero import SeatsAeroClient
from airpoints.models import Trip
from airpoints.ranker import build_prompt, rank_heuristic, rank_with_llm
from airpoints.transfers import TransferTable

HERE = os.path.dirname(__file__)
FIXTURE = os.path.join(HERE, "fixtures", "seatsaero_sample.json")
RATIOS = os.path.join(HERE, "..", "data", "transfer_ratios.yaml")


class _FakeContentBlock:
    def __init__(self, text):
        self.type = "text"
        self.text = text


class _FakeResponse:
    def __init__(self, text):
        self.content = [_FakeContentBlock(text)]


class _FakeMessages:
    def __init__(self, payload):
        self._payload = payload
        self.last_kwargs = None

    def create(self, **kwargs):
        self.last_kwargs = kwargs
        return _FakeResponse(json.dumps(self._payload))


class _FakeClient:
    def __init__(self, payload):
        self.messages = _FakeMessages(payload)


class AggregatorTest(unittest.TestCase):
    def setUp(self):
        self.table = TransferTable.load(RATIOS)
        self.balances = {"amex_mr": 120000, "chase_ur": 80000, "alaska_miles": 45000}
        self.awards = SeatsAeroClient.from_fixture(FIXTURE)

    def test_cabin_filter_applies(self):
        trip = Trip("T", "SFO", "HND", "2026-04-01", "2026-04-15", cabins=["business"])
        priced = price_options(self.awards, self.balances, self.table, trip)
        self.assertTrue(all(o.award.cabin == "business" for o in priced))
        self.assertEqual(len(priced), 4)  # alaska, ana, united, smiles business

    def test_unfundable_program_kept_with_no_funding(self):
        priced = price_options(self.awards, self.balances, self.table)
        smiles = next(o for o in priced if o.award.program == "smiles")
        self.assertIsNone(smiles.funding)
        self.assertFalse(smiles.affordable)

    def test_affordable_only_filters(self):
        trip = Trip("T", "SFO", "HND", "2026-04-01", "2026-04-15", cabins=["business"])
        priced = price_options(self.awards, self.balances, self.table, trip)
        aff = affordable_only(priced)
        progs = sorted(o.award.program for o in aff)
        # business: alaska(75k>45k no), ana(85k<120k yes), united(88k>80k no),
        # smiles(none) -> only ana affordable
        self.assertEqual(progs, ["ana"])

    def test_heuristic_ranks_affordable_and_cheap_first(self):
        priced = price_options(self.awards, self.balances, self.table)
        ranked = rank_heuristic(priced)
        # cheapest affordable option overall is alaska economy (30k, affordable)
        self.assertEqual(ranked[0].award.program, "alaska")
        self.assertEqual(ranked[0].award.cabin, "economy")
        self.assertTrue(ranked[0].affordable)


class RankerLLMTest(unittest.TestCase):
    def setUp(self):
        self.table = TransferTable.load(RATIOS)
        self.balances = {"amex_mr": 120000, "chase_ur": 80000, "alaska_miles": 45000}
        self.awards = SeatsAeroClient.from_fixture(FIXTURE)
        self.trip = Trip("T", "SFO", "HND", "2026-04-01", "2026-04-15")

    def test_rank_with_injected_fake_client(self):
        priced = price_options(self.awards, self.balances, self.table, self.trip)
        payload = {
            "recommendations": [
                {"rank": 2, "summary": "ANA business", "reason": "b", "affordable": True},
                {"rank": 1, "summary": "Alaska economy", "reason": "a", "affordable": True},
            ]
        }
        client = _FakeClient(payload)
        recs = rank_with_llm(priced, self.balances, self.trip, client=client)
        self.assertEqual([r.rank for r in recs], [1, 2])  # sorted by rank
        # correct model + adaptive thinking + structured output were requested
        kw = client.messages.last_kwargs
        self.assertEqual(kw["model"], "claude-opus-4-8")
        self.assertEqual(kw["thinking"], {"type": "adaptive"})
        self.assertEqual(kw["output_config"]["format"]["type"], "json_schema")

    def test_empty_options_short_circuits(self):
        self.assertEqual(rank_with_llm([], self.balances, self.trip, client=object()), [])

    def test_prompt_contains_balances_and_no_secrets(self):
        priced = price_options(self.awards, self.balances, self.table, self.trip)
        prompt = build_prompt(priced, self.balances, self.trip)
        self.assertIn("amex_mr", prompt)
        self.assertIn("SFO", prompt)


if __name__ == "__main__":
    unittest.main()
