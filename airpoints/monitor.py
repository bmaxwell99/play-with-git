"""Scheduled monitoring: alert only on *newly* affordable award sweet spots.

Run on a cron. Each run fetches + prices every watched trip, compares the
affordable options against a persisted "seen" set, and notifies only on ones
that are new. The signature includes the mileage cost, so a price drop on a
route you've already seen counts as new (that's a sweet spot worth flagging).

    python -m airpoints.monitor --watchlist watchlist.yaml \
        --state .airpoints_state.json --max-miles 90000

Notifiers are pluggable: stdout by default, plus optional --notify-file (append
a line per alert) and --webhook (POST JSON, e.g. a Slack/Discord webhook).
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Callable, Iterable, Optional

from .config import load_dotenv, load_watchlist
from .models import PricedOption, Trip
from .pipeline import priced_for_trip
from .transfers import TransferTable

# A notifier receives a trip and its list of newly-found options.
Notifier = Callable[[Trip, list[PricedOption]], None]


def option_signature(opt: PricedOption) -> str:
    """Stable identity for an option. Includes miles so price drops re-alert."""
    a = opt.award
    return f"{a.origin}-{a.destination}|{a.date}|{a.cabin}|{a.program}|{a.miles}"


def load_state(path: str) -> set[str]:
    if not os.path.exists(path):
        return set()
    with open(path, "r", encoding="utf-8") as fh:
        data = json.load(fh)
    return set(data.get("seen", []))


def save_state(path: str, seen: Iterable[str]) -> None:
    with open(path, "w", encoding="utf-8") as fh:
        json.dump({"seen": sorted(seen)}, fh, indent=2)


def find_new(
    options: list[PricedOption],
    seen: set[str],
    max_miles: Optional[int] = None,
) -> tuple[list[PricedOption], set[str]]:
    """Affordable options not seen before (optionally under a miles ceiling).

    Returns (new_options, updated_seen). `updated_seen` adds the signatures of
    every option that *qualified* as a sweet spot this run, so each alerts once.
    """
    new: list[PricedOption] = []
    updated = set(seen)
    for opt in options:
        if not opt.affordable:
            continue
        if max_miles is not None and opt.award.miles > max_miles:
            continue
        sig = option_signature(opt)
        if sig not in seen:
            new.append(opt)
        updated.add(sig)
    return new, updated


# --- Notifiers ---------------------------------------------------------------


def stdout_notifier(trip: Trip, new: list[PricedOption]) -> None:
    print(f"[{trip.name}] {len(new)} new sweet spot(s):")
    for opt in new:
        print(f"  + {opt.summary()}")


def file_notifier(path: str) -> Notifier:
    def notify(trip: Trip, new: list[PricedOption]) -> None:
        with open(path, "a", encoding="utf-8") as fh:
            for opt in new:
                fh.write(f"{trip.name}\t{opt.summary()}\n")

    return notify


def webhook_notifier(url: str) -> Notifier:
    def notify(trip: Trip, new: list[PricedOption]) -> None:
        import requests  # lazy

        lines = [opt.summary() for opt in new]
        text = f"*{trip.name}* — {len(new)} new award sweet spot(s):\n" + "\n".join(
            f"• {ln}" for ln in lines
        )
        requests.post(url, json={"text": text}, timeout=15)

    return notify


def run_monitor(
    trips: list[Trip],
    balances: dict[str, int],
    table: TransferTable,
    state_path: str,
    *,
    notifiers: list[Notifier],
    max_miles: Optional[int] = None,
    fetch_kwargs: Optional[dict] = None,
) -> int:
    """Check every trip, fire notifiers on new sweet spots, persist state.

    Returns the total count of new options found. State is saved even if a
    single trip's fetch fails, so transient errors don't lose progress.
    """
    fetch_kwargs = fetch_kwargs or {}
    seen = load_state(state_path)
    total_new = 0
    try:
        for trip in trips:
            try:
                options = priced_for_trip(trip, balances, table, **fetch_kwargs)
            except Exception as exc:  # one bad route shouldn't abort the run
                print(f"[{trip.name}] fetch failed: {exc}", file=sys.stderr)
                continue
            new, seen = find_new(options, seen, max_miles=max_miles)
            if new:
                total_new += len(new)
                for notify in notifiers:
                    notify(trip, new)
    finally:
        save_state(state_path, seen)
    return total_new


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="Monitor watched routes; alert on new affordable sweet spots."
    )
    parser.add_argument("--watchlist", required=True)
    parser.add_argument("--ratios", default="data/transfer_ratios.yaml")
    parser.add_argument("--state", default=".airpoints_state.json")
    parser.add_argument(
        "--fixture", help="recorded seats.aero JSON (offline mode; no API key)"
    )
    parser.add_argument(
        "--max-miles", type=int, default=None, help="ignore options above this cost"
    )
    parser.add_argument("--notify-file", help="append each alert to this file")
    parser.add_argument("--webhook", help="POST alerts as JSON {text} to this URL")
    parser.add_argument(
        "--quiet", action="store_true", help="suppress the stdout notifier"
    )
    args = parser.parse_args(argv)

    load_dotenv()
    table = TransferTable.load(args.ratios)
    balances, trips = load_watchlist(args.watchlist)

    notifiers: list[Notifier] = []
    if not args.quiet:
        notifiers.append(stdout_notifier)
    if args.notify_file:
        notifiers.append(file_notifier(args.notify_file))
    if args.webhook:
        notifiers.append(webhook_notifier(args.webhook))

    total = run_monitor(
        trips,
        balances,
        table,
        args.state,
        notifiers=notifiers,
        max_miles=args.max_miles,
        fetch_kwargs={"fixture": args.fixture},
    )
    if not args.quiet and total == 0:
        print("No new sweet spots.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
