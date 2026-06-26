"""Command-line entry point.

    python -m airpoints.cli --watchlist data/watchlist.example.yaml --fixture \
        tests/fixtures/seatsaero_sample.json

Live mode (needs SEATSAERO_API_KEY, and ANTHROPIC_API_KEY for --llm):

    python -m airpoints.cli --watchlist my_watchlist.yaml --llm
"""

from __future__ import annotations

import argparse
import os
import sys

from .aggregator import price_options
from .clients.seatsaero import SeatsAeroClient
from .config import load_dotenv, load_watchlist
from .models import PricedOption, Trip
from .ranker import rank_heuristic, rank_with_llm
from .transfers import TransferTable


def _fetch_awards(trip: Trip, args) -> list:
    if args.fixture:
        # Dev/offline mode: every trip reads the same recorded response.
        return SeatsAeroClient.from_fixture(args.fixture)

    api_key = os.environ.get("SEATSAERO_API_KEY", "")
    client = SeatsAeroClient(api_key)
    awards = []
    for cabin in trip.cabins:
        awards.extend(
            client.search(
                origin=trip.origin,
                destination=trip.destination,
                start_date=trip.earliest,
                end_date=trip.latest,
                cabin=cabin,
            )
        )
    return awards


def _report_trip(trip: Trip, options: list[PricedOption], args, balances) -> None:
    print(f"\n=== {trip.name}: {trip.origin} -> {trip.destination} "
          f"({trip.earliest}..{trip.latest}) ===")
    if not options:
        print("  no award availability found for the requested cabins")
        return

    if args.llm:
        try:
            recs = rank_with_llm(options, balances, trip)
            for r in recs:
                tag = "" if r.affordable else "  (short)"
                print(f"  #{r.rank}{tag} {r.summary}")
                print(f"        {r.reason}")
            return
        except ImportError:
            print("  [anthropic SDK not installed; using heuristic ranking]")
        except Exception as exc:  # network/auth/etc. — degrade gracefully
            print(f"  [LLM ranking failed ({exc}); using heuristic ranking]")

    for i, opt in enumerate(rank_heuristic(options)[: args.top], start=1):
        print(f"  #{i} {opt.summary()}")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Aggregate airline award options.")
    parser.add_argument("--watchlist", required=True, help="watchlist YAML path")
    parser.add_argument(
        "--ratios",
        default="data/transfer_ratios.yaml",
        help="transfer-ratio table YAML",
    )
    parser.add_argument(
        "--fixture", help="recorded seats.aero JSON (offline mode; no API key)"
    )
    parser.add_argument(
        "--llm", action="store_true", help="rank with Claude (needs ANTHROPIC_API_KEY)"
    )
    parser.add_argument("--top", type=int, default=5, help="options to show per trip")
    args = parser.parse_args(argv)

    load_dotenv()
    table = TransferTable.load(args.ratios)
    balances, trips = load_watchlist(args.watchlist)

    if not trips:
        print("No trips in watchlist.", file=sys.stderr)
        return 1

    print(f"Balances: {balances}")
    for trip in trips:
        awards = _fetch_awards(trip, args)
        options = price_options(awards, balances, table, trip)
        _report_trip(trip, options, args, balances)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
