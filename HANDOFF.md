# HANDOFF — airpoints (for the local Claude Code instance)

You are picking up a project built in a separate (cloud) Claude Code session
that is **network-isolated** and could not reach live APIs. You are running on
the user's own machine, so **you can do the live work it couldn't**: hold API
keys, hit Amadeus/seats.aero, and browse. Read this whole file, then continue.

The user is **bmaxwell99** (bmaxwell99@gmail.com). Home airports: **NYC (JFK /
EWR / LGA)**.

---

## What this project is

`airpoints` — a personal-scale trip tool with two sides:

- **Award (points) side:** pulls award-flight availability from the seats.aero
  Partner API, prices each option against the user's transferable points (Amex
  MR, Chase UR) and direct Alaska miles, ranks options (heuristic or Claude).
  Entry points: `python -m airpoints.cli` and `python -m airpoints.monitor`.
- **Cash side (newest):** `python -m airpoints.trip` — a budget optimizer that
  finds the **cheapest cash trip** (flight + hotel) across candidate date
  windows using the Amadeus Self-Service API, enforcing hard travel rules.

Architecture notes: dependency-light core (stdlib + PyYAML); `requests`,
`anthropic` imported lazily; secrets load from a gitignored `.env`. 52 tests
(`python -m unittest discover -s tests`). Everything is tested offline against
fixtures in `tests/fixtures/`.

Repo: `bmaxwell99/play-with-git`. Work branch:
`claude/airline-points-marketplace-api-lstgly`. Open PR: **#1** (base `master`).

---

## The user's actual goal (finish this)

Plan a **working travel trip to New Orleans** (they work on the plane, take no
time off, so timing is flexible). Requirements, already captured in
`data/trip.example.yaml`:

- Route: **NYC (JFK/EWR/LGA) → New Orleans (MSY)**, round trip.
- **Nonstop only.**
- **No flight departing before 9:00am; none landing after 8:00pm** — both legs.
- 3–5 business days; **Tue→Fri** shape (3 weekday nights) is preset.
- **Cheapest total cost**, cash-first; use points only where they clearly beat
  cash (break-even ≈ **1.25¢/point**).
- Candidate windows (blackouts already removed — Thanksgiving, Dec 18–Jan 4,
  MLK Jan 15–19, **Carnival Jan 29–Feb 9 2027**): Early Nov, Early Dec, Early
  Jan, **Post-Mardi-Gras Feb 16–19 2027** (usually cheapest).
- Stay in the **New Orleans CBD** (walkable to Deloitte at 701 Poydras + the
  French Quarter). `prefer_hyatt: true` is set — Hyatt is bookable on Chase UR
  points (1:1), often the sweet spot.

### Do this
1. **Get Amadeus free keys:** developers.amadeus.com → create an app → copy the
   API Key + API Secret (Self-Service, free tier).
2. Put them in `.env` (already gitignored — never commit):
   ```
   AMADEUS_CLIENT_ID=...
   AMADEUS_CLIENT_SECRET=...
   ```
   If test-env fares look sparse, add `AMADEUS_BASE_URL=https://api.amadeus.com`
   and flip the app to production in the Amadeus portal (same free quota).
3. Run the optimizer live and read the ranked output:
   ```
   python -m airpoints.trip --config data/trip.example.yaml
   ```
4. **Hotel points check** (Amadeus gives cash rates only): for the winning
   window's dates, look up the **World of Hyatt** award-night cost for the CBD
   Hyatt it flagged, compute `cash ÷ points`; recommend points if > 1.25¢/pt,
   else cash.
5. **Report back to the user**: the single cheapest constraint-compliant trip
   (dates, airline, flight times, price, hotel, total), plus the 2–3 runners-up
   and the flight-vs-cash / hotel-points-vs-cash recommendation. Cross-check the
   flight number/price on Google Flights before they book.

Offline sanity check (no keys) to confirm the tool runs:
```
python -m airpoints.trip --config data/trip.example.yaml \
  --flights-fixture tests/fixtures/amadeus_flights_sample.json \
  --hotels-fixture tests/fixtures/amadeus_hotels_sample.json
```

---

## State of the two sides

**Award side — LIVE and working.** The user already ran it with their real
`SEATSAERO_API_KEY`. The seats.aero parser is pinned to a real response
(`tests/fixtures/seatsaero_sample.json`), tax unit confirmed as cents
(`TAXES_IN_CENTS = True` in `airpoints/clients/seatsaero.py`), and the
connection-vs-nonstop modeling is verified. Award analysis already done: for
short-haul NYC→MSY, cash usually beats points, so this trip is cash-first.

**Cash side — CODE COMPLETE, needs the user's Amadeus keys to run live** (step
above). Never run live from the cloud session, so live output has not been seen
yet.

---

## Conventions if you commit

- Branch: keep working on `claude/airline-points-marketplace-api-lstgly` (PR #1).
- Run `python -m unittest discover -s tests` before pushing; keep it green.
- The cloud session set an hourly self-check watching PR #1 — that watch lives in
  that session and won't follow you here, so just tell the user directly about
  any PR action you take.
- Do not commit `.env` or a real `watchlist.yaml` (both gitignored).

---

## Open question for the user

PR #1 is complete and ready. Ask whether they want it **merged** now, or kept
open while you finish the live New Orleans run.
