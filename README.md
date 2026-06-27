# airpoints

A personal-scale aggregator for award (points) flights. It pulls award
availability from [seats.aero](https://seats.aero), prices each option against
**your** transferable points (Amex Membership Rewards, Chase Ultimate Rewards)
and direct miles (Alaska Mileage Plan), and ranks the best choices — optionally
with Claude doing the picking and explaining.

No web scraping: seats.aero exposes a real JSON API that indexes most loyalty
programs (including Alaska and the partners Amex/Chase transfer to).

## How it works

```
watchlist.yaml ──┐
                 ├─► seats.aero API ──► award options ──┐
transfer_ratios ─┘                                      ├─► price each option
                                                        │   (cheapest funding
your balances ──────────────────────────────────────────┘    path per program)
                                                            │
                                                            ▼
                                            rank (heuristic, or Claude --llm)
```

1. **Award availability** comes from the seats.aero cached-search endpoint
   (`airpoints/clients/seatsaero.py`).
2. **Conversion logic** is a hand-maintained table (`data/transfer_ratios.yaml`)
   mapping each currency you hold to the programs it can fund and at what ratio.
   Transfer ratios change rarely, so this is static config, not a live feed.
3. **Pricing** (`airpoints/transfers.py` + `aggregator.py`) finds the cheapest
   way you can pay for each award and whether you can afford it today.
4. **Ranking** is either a deterministic heuristic or a Claude pass
   (`airpoints/ranker.py`) that flags sweet spots and explains trade-offs.

## Setup

```bash
pip install -r requirements.txt
cp .env.example .env          # add your keys (gitignored)
cp data/watchlist.example.yaml watchlist.yaml   # add your trips + balances
```

Get a seats.aero **Partner API** key (Pro/API tier, ~$10/mo) and put it in
`.env` as `SEATSAERO_API_KEY`. For `--llm` ranking, also set `ANTHROPIC_API_KEY`.

## Run

Offline demo against the bundled fixture (no keys needed):

```bash
python -m airpoints.cli --watchlist data/watchlist.example.yaml \
    --fixture tests/fixtures/seatsaero_sample.json
```

Live, with Claude ranking:

```bash
python -m airpoints.cli --watchlist watchlist.yaml --llm
```

Flags: `--ratios` (transfer table path), `--top N` (options per trip),
`--fixture` (offline JSON), `--llm` (rank with Claude).

## Monitoring (cron)

`airpoints.monitor` runs the same fetch+price pipeline, remembers what it has
already seen in a small state file, and **alerts only on newly-affordable sweet
spots** — including price drops (a cheaper award on a route you've seen counts
as new). Notifiers are pluggable: stdout by default, plus an append file and/or
a webhook (e.g. Slack/Discord).

```bash
python -m airpoints.monitor --watchlist watchlist.yaml \
    --state ~/.airpoints_state.json \
    --max-miles 90000 \
    --webhook "$SLACK_WEBHOOK_URL"
```

Flags: `--state` (seen-set path), `--max-miles N` (ignore pricier options to cut
noise), `--notify-file PATH`, `--webhook URL`, `--quiet` (suppress stdout),
`--fixture` (offline demo). The state file is written even if a single route's
fetch fails, so transient errors don't lose progress.

Run it on a schedule — e.g. every 6 hours via cron:

```cron
0 */6 * * *  cd /path/to/play-with-git && /usr/bin/python3 -m airpoints.monitor \
  --watchlist watchlist.yaml --state ~/.airpoints_state.json \
  --max-miles 90000 --quiet --webhook "$SLACK_WEBHOOK_URL" >> ~/airpoints.log 2>&1
```

With `--quiet` it stays silent unless there's something new — so a webhook ping
means a genuinely new sweet spot.

## Configuration

**`watchlist.yaml`** — your balances and the trips to monitor:

```yaml
balances:
  amex_mr: 120000
  chase_ur: 80000
  alaska_miles: 45000
trips:
  - name: "Spring Tokyo"
    origin: SFO
    destination: HND
    earliest: 2026-04-01
    latest: 2026-04-15
    cabins: [business, first]
    passengers: 2
```

**`data/transfer_ratios.yaml`** — the conversion table. `balances` keys must
match the `currencies` keys here. Alaska is its own bucket because it is *not*
an Amex/Chase transfer partner — its miles are earned directly on the Bank of
America card.

## Design notes

- **Dependency-light core.** Models, transfer math, and aggregation use only the
  standard library + PyYAML, so the logic runs and tests anywhere. `requests`
  (live fetch) and `anthropic` (`--llm`) are imported lazily — the heuristic
  ranker works without `anthropic` installed.
- **Secrets stay out of the repo and out of prompts.** Keys load from the
  environment / `.env`; the LLM prompt contains only balances and option data.
- **Claude usage** (`airpoints/ranker.py`): `claude-opus-4-8` with adaptive
  thinking and a JSON-schema `output_config`, parsed with stdlib `json`.

## Extending it

- **Cash-fare comparison:** add a client under `airpoints/clients/` (Amadeus
  self-service or Duffel both have free tiers) and merge cash options alongside
  award options before ranking.
- **More currencies/programs:** edit `data/transfer_ratios.yaml`.
- **Monitoring/alerts:** wrap the CLI in a cron job; diff results to alert on new
  sweet spots.

## Tests

```bash
python -m unittest discover -s tests      # stdlib, no extra deps
# or, once pytest is installed:
pytest
```
