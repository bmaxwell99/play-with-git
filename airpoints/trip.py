"""Budget trip optimizer CLI — cheapest cash flight + hotel across windows.

    # offline demo (no keys):
    python -m airpoints.trip --config data/trip.example.yaml \
        --flights-fixture tests/fixtures/amadeus_flights_sample.json \
        --hotels-fixture tests/fixtures/amadeus_hotels_sample.json

    # live (needs AMADEUS_CLIENT_ID / AMADEUS_CLIENT_SECRET in .env):
    python -m airpoints.trip --config data/trip.example.yaml

Config (YAML): origins (airport codes), destination, city_code, adults, an
optional constraints block (nonstop / earliest_depart / latest_arrival),
prefer_hyatt, and a list of windows (name + depart + return dates).
"""

from __future__ import annotations

import argparse
import os
import sys

import yaml

from .budget import Constraints, Window, rank_windows
from .clients.amadeus import AmadeusClient
from .config import load_dotenv


def _load_config(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as fh:
        return yaml.safe_load(fh) or {}


def _constraints(cfg: dict) -> Constraints:
    c = cfg.get("constraints") or {}
    return Constraints(
        nonstop=bool(c.get("nonstop", True)),
        earliest_depart=str(c.get("earliest_depart", "09:00")),
        latest_arrival=str(c.get("latest_arrival", "20:00")),
    )


def _build_windows(cfg: dict, args) -> list[Window]:
    origins = cfg.get("origins") or []
    destination = cfg["destination"]
    city_code = cfg.get("city_code", destination)
    adults = int(cfg.get("adults", 1))
    nonstop = bool((cfg.get("constraints") or {}).get("nonstop", True))
    origin_label = cfg.get("origin_label") or "/".join(origins)

    client = None
    if not (args.flights_fixture and args.hotels_fixture):
        client = AmadeusClient(
            os.environ.get("AMADEUS_CLIENT_ID", ""),
            os.environ.get("AMADEUS_CLIENT_SECRET", ""),
            base_url=os.environ.get("AMADEUS_BASE_URL", "https://test.api.amadeus.com"),
        )

    windows: list[Window] = []
    for w in cfg.get("windows") or []:
        depart, ret = str(w["depart"]), str(w["return"])
        if args.flights_fixture:
            flights = AmadeusClient.flights_from_fixture(args.flights_fixture)
        else:
            flights = []
            for origin in origins:
                try:
                    flights.extend(
                        client.search_flights(
                            origin, destination, depart, ret,
                            adults=adults, nonstop=nonstop,
                        )
                    )
                except Exception as exc:  # one origin failing shouldn't abort
                    print(f"[{w['name']}] flights {origin} failed: {exc}",
                          file=sys.stderr)
        if args.hotels_fixture:
            hotels = AmadeusClient.hotels_from_fixture(args.hotels_fixture)
        else:
            try:
                hotels = client.search_hotels(city_code, depart, ret, adults=adults)
            except Exception as exc:
                print(f"[{w['name']}] hotels failed: {exc}", file=sys.stderr)
                hotels = []
        windows.append(
            Window(
                name=w["name"],
                origin=origin_label,
                destination=destination,
                flights=flights,
                hotels=hotels,
            )
        )
    return windows


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="Rank the cheapest constraint-compliant cash trips."
    )
    parser.add_argument("--config", required=True, help="trip config YAML")
    parser.add_argument("--flights-fixture", help="offline Amadeus flights JSON")
    parser.add_argument("--hotels-fixture", help="offline Amadeus hotels JSON")
    parser.add_argument("--top", type=int, default=10)
    args = parser.parse_args(argv)

    load_dotenv()
    cfg = _load_config(args.config)
    constraints = _constraints(cfg)
    prefer_hyatt = bool(cfg.get("prefer_hyatt", False))

    windows = _build_windows(cfg, args)
    ranked = rank_windows(windows, constraints, prefer_hyatt=prefer_hyatt)

    if not ranked:
        print("No constraint-compliant trips found "
              "(check dates, nonstop availability, or time limits).")
        return 1

    print(f"Cheapest trips ({constraints.earliest_depart}+ dep, "
          f"{constraints.latest_arrival}- arr, "
          f"{'nonstop' if constraints.nonstop else 'any'}):\n")
    for i, opt in enumerate(ranked[: args.top], start=1):
        print(f"#{i} {opt.summary()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
