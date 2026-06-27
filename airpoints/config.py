"""Configuration loading: watchlist + balances + secrets.

Secrets (the seats.aero key, the Anthropic key) come from the environment so
they never live in the repo. A `.env` file is loaded if present, using a tiny
built-in parser so `python-dotenv` is optional.
"""

from __future__ import annotations

import os

import yaml

from .models import CABINS, Trip


def load_dotenv(path: str = ".env") -> None:
    """Minimal .env loader (KEY=VALUE lines). No dependency on python-dotenv."""
    if not os.path.exists(path):
        return
    with open(path, "r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            key, value = key.strip(), value.strip().strip("'\"")
            # Real environment variables win over .env defaults.
            os.environ.setdefault(key, value)


def load_watchlist(path: str) -> tuple[dict[str, int], list[Trip]]:
    """Parse a watchlist YAML into (balances, trips)."""
    with open(path, "r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh) or {}

    balances = {k: int(v) for k, v in (data.get("balances") or {}).items()}

    trips: list[Trip] = []
    for t in data.get("trips") or []:
        trips.append(
            Trip(
                name=t.get("name", f"{t['origin']}-{t['destination']}"),
                origin=t["origin"],
                destination=t["destination"],
                earliest=str(t["earliest"]),
                latest=str(t["latest"]),
                cabins=t.get("cabins") or list(CABINS),
                passengers=int(t.get("passengers", 1)),
            )
        )
    return balances, trips
