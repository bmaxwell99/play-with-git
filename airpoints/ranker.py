"""Rank priced options — deterministic heuristic, plus an optional LLM pass.

`rank_heuristic` is pure Python and always available: it's the default and the
fallback. `rank_with_llm` hands the same options to Claude to pick and explain
the best sweet spots; it imports the Anthropic SDK lazily so the package works
without it installed.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Optional

from .models import PricedOption, Trip

# Default model: Claude Opus 4.8 (most capable). Adaptive thinking on.
DEFAULT_MODEL = "claude-opus-4-8"


def rank_heuristic(options: list[PricedOption]) -> list[PricedOption]:
    """Affordable first, then cheapest miles, then lowest cash co-pay."""

    def key(o: PricedOption):
        return (
            0 if o.affordable else 1,
            o.award.miles,
            o.award.taxes_usd,
            0 if o.award.direct else 1,
        )

    return sorted(options, key=key)


@dataclass
class Recommendation:
    """One LLM-selected option with its reasoning."""

    rank: int
    summary: str
    reason: str
    affordable: bool


# JSON schema the model is constrained to. Parsed with stdlib json — no pydantic.
_SCHEMA = {
    "type": "object",
    "properties": {
        "recommendations": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "rank": {"type": "integer"},
                    "summary": {"type": "string"},
                    "reason": {"type": "string"},
                    "affordable": {"type": "boolean"},
                },
                "required": ["rank", "summary", "reason", "affordable"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["recommendations"],
    "additionalProperties": False,
}


def _options_payload(options: list[PricedOption]) -> list[dict]:
    rows = []
    for o in options:
        a = o.award
        f = o.funding
        rows.append(
            {
                "route": f"{a.origin}-{a.destination}",
                "date": a.date,
                "cabin": a.cabin,
                "program": a.program,
                "miles_per_pax": a.miles,
                "taxes_usd_per_pax": a.taxes_usd,
                "airlines": a.airlines,
                "nonstop": a.direct,
                "remaining_seats": a.remaining_seats,
                "funding": None
                if f is None
                else {
                    "pay_with": f.currency_display,
                    "points_required_per_pax": f.points_required,
                    "transfer_time": f.transfer_time,
                    "held_directly": f.held_directly,
                    "affordable": f.affordable,
                    "shortfall": f.shortfall,
                },
            }
        )
    return rows


def build_prompt(
    options: list[PricedOption], balances: dict[str, int], trip: Trip
) -> str:
    """The user-turn prompt handed to Claude — pure data, no secrets."""
    return (
        "You are a frequent-flyer award-travel analyst. Given my points "
        "balances and a set of bookable award options for an upcoming trip, "
        "rank the best choices and explain why.\n\n"
        "Account for: total points cost after the cheapest transfer path, the "
        "cash co-pay, cabin, nonstop vs connection, and whether I can afford it "
        "today. Flag genuine sweet spots (unusually low miles for the cabin). "
        "Prefer options I can book now over ones I'm short on.\n\n"
        f"Trip: {trip.name} ({trip.origin}->{trip.destination}, "
        f"{trip.earliest}..{trip.latest}, {trip.passengers} pax)\n"
        f"Balances: {json.dumps(balances)}\n"
        f"Options:\n{json.dumps(_options_payload(options), indent=2)}\n\n"
        "Return your ranked recommendations."
    )


def rank_with_llm(
    options: list[PricedOption],
    balances: dict[str, int],
    trip: Trip,
    *,
    model: str = DEFAULT_MODEL,
    client=None,
) -> list[Recommendation]:
    """Ask Claude to rank and explain the options.

    Raises ImportError if the Anthropic SDK isn't installed; callers should
    catch that and fall back to `rank_heuristic`. Pass a pre-built `client`
    to inject a fake in tests.
    """
    if not options:
        return []

    if client is None:
        import anthropic  # lazy import

        client = anthropic.Anthropic()  # reads ANTHROPIC_API_KEY from env

    resp = client.messages.create(
        model=model,
        max_tokens=4096,
        thinking={"type": "adaptive"},
        output_config={"format": {"type": "json_schema", "schema": _SCHEMA}},
        messages=[{"role": "user", "content": build_prompt(options, balances, trip)}],
    )

    text = next((b.text for b in resp.content if b.type == "text"), "{}")
    data = json.loads(text)
    recs = [
        Recommendation(
            rank=r["rank"],
            summary=r["summary"],
            reason=r["reason"],
            affordable=r["affordable"],
        )
        for r in data.get("recommendations", [])
    ]
    return sorted(recs, key=lambda r: r.rank)
