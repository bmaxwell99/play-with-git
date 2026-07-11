# Crazy Eights Countdown — Monte Carlo Strategy Experiment

Simulator: `crazy_eights_sim.py` (Python 3, stdlib only).

## Game rules simulated

- 4 players, fresh 52-card deck each round, 15 rounds with hand sizes
  1,2,3,4,5,6,7,8,7,6,5,4,3,2,1. Golf scoring: lowest total wins.
- Play must match the top card's rank or the current suit.
- Specials (still must match rank-or-suit to be played):
  **8** = player names next suit (8s cost 50 in hand; a flipped starter 8 is
  shuffled back), **2** = draw-2, chainable with a stacking pot (+2 per chained
  2; first player who can't chain draws the whole pot, turn ends), **3** = skip
  next player, **Ace** = reverse direction.
- No legal play → draw exactly 1 card, turn ends (drawn card not playable).
- Starter specials affect the first player. Empty draw pile → reshuffle the
  discard pile except its top card.
- Hand scoring when someone goes out: 8=50, 2=20, J/Q/K=10, A=1, rest pip value.
- Going out on an 8 is allowed. Seats and starting player rotate; strategy
  seating is shuffled every game.

## Strategies tested

| name | rule |
|---|---|
| `random` | uniformly random legal card, random suit call, chains 2s half the time |
| `low-first` | sheds the *cheapest* legal card first (control arm) |
| `hoard-8` | greedy on points but keeps 8s until hand ≤ 2 cards or forced |
| `defensive` | greedy on points, but when an opponent has ≤2 cards, strongly prefers 3s (skip), 2s (attack), and 8s (steer suit) |
| `suit-major` | plays into its most-held suit first, points as tiebreak |
| `greedy-points` | sheds the most expensive legal card first (8 → 2 → faces …) |
| `hybrid` | greedy points, ties broken toward its most-held suit |

All non-random strategies always chain 2s when possible and name their
most-held suit after an 8.

## Results

Main sweep — 10,000 games × 15 rounds, 4 of 6 strategies sampled per game
(seed 42):

| strategy | mean score | ±95% CI | win rate |
|---|---|---|---|
| greedy-points | 311.5 | 2.2 | 38.4% |
| suit-major | 312.8 | 2.2 | 37.3% |
| defensive | 324.5 | 2.2 | 33.2% |
| hoard-8 | 391.7 | 2.8 | 17.5% |
| random | 402.2 | 2.6 | 14.0% |
| low-first | 443.2 | 2.9 | 10.0% |

Top-four head-to-head — 20,000 games (seed 789), adding `hybrid`:

| strategy | mean score | ±95% CI | win rate |
|---|---|---|---|
| hybrid | 309.3 | 1.2 | 26.6% |
| greedy-points | 310.4 | 1.2 | 26.6% |
| suit-major | 313.5 | 1.3 | 25.2% |
| defensive | 323.8 | 1.3 | 21.6% |

Mirror match, 2× hybrid vs 2× greedy-points — 30,000 games (seed 999):
hybrid 306.8 ± 0.7 (25.4% wins) vs greedy-points 308.2 ± 0.7 (24.6% wins).

## Conclusions

1. **Dump your liabilities: shedding the most expensive card first is the
   dominant heuristic.** The gap between greedy-points (~311) and the
   cheapest-first control (~443) is enormous — about 130 points over a game,
   almost 9 points per round. Because you only score when you *lose* a round,
   and most rounds you lose, minimizing expected hand value matters more than
   anything else.
2. **Never hoard 8s.** Keeping an 8 as a going-out tool costs ~80 points per
   game (hoard-8 ~392 vs greedy ~311) — worse than playing randomly. A 50-point
   card caught in hand erases many rounds of clever play.
3. **Suit awareness is a real but small refinement.** Steering the pile toward
   your long suit as the *primary* criterion (suit-major) roughly matches pure
   greed; using it only as a tiebreak among equal-point cards (hybrid) is the
   best strategy tested — about 1.4 points per game better than pure greed,
   statistically significant at 30k games.
4. **Attacking the leader underperforms.** Saving 2s/3s to disrupt an opponent
   with ≤2 cards (defensive) costs ~14 points per game versus greed: the
   disruption rarely stops them, and the withheld high cards get caught.

**Best strategy found:** *hybrid* — always play the highest-point legal card,
break ties toward the suit you hold most of, always chain 2s, name your
longest suit after an 8.

## Does card counting help? (yes, a little)

The `counter` strategy is hybrid plus a running count of the discard pile,
which tells it exactly which suits/ranks remain among opponents' hands and the
draw pile. It uses the count two ways:

1. **Shed order tiebreak** — among equal-point/equal-suit-length cards, discard
   the one *least* likely to be playable later (fewest unseen suit+rank
   matches), keeping "live" cards.
2. **Suit naming after an 8** — among its longest suits, name the one
   opponents are least likely to be able to follow, forcing draws.

Results (30,000 games each):

| matchup | counter mean | hybrid mean | edge |
|---|---|---|---|
| 1 counter vs 3 hybrid | 304.4 ± 1.0 | 308.1 ± 0.6 | −3.7 pts/game |
| 2 counters vs 2 hybrid | 305.0 ± 0.7 | 308.8 ± 0.7 | −3.8 pts/game |
| shed-tiebreak counting only | 305.1 ± 1.0 | 306.8 ± 0.6 | −1.7 |
| suit-naming counting only | 305.6 ± 1.0 | 307.4 ± 0.6 | −1.8 |

A lone counter's win rate rises from the fair 25.0% to **25.9%** per seat.
The two uses of the count are roughly additive (~1.7 + ~1.8 ≈ 3.7). The edge
is real (confidence intervals well separated) but tiny relative to luck: the
best-vs-worst spread in a single all-hybrid game averages ~191 points, so
~4 points/game only shows up over many games.

## Score distributions in all-hybrid games

From 50,000 games where all four seats play `hybrid`:

- Any player's total: mean ~307, sd ~89. Winner's total: **mean 215, sd 48,
  median 215** (middle 50%: 182–247; 5th/95th pct: 135/295).
- Average best-vs-worst spread within a game: **~191 points** (median 183) —
  luck dwarfs the few-points-per-game strategy edges in any single game.
- **A final total ≤ 180 wins the game 95% of the time.** Other landmarks for
  P(win | final total ≤ T): 150 → 98.8%, 200 → 90%, 230 → 79%, 290 → 52%.
  Only 1% of winners ever score above 326.
- **A final total ≥ 271 loses the game 95% of the time** (300 → 98%,
  319 → 99%; no player in 50k games won after reaching 380). Highest winning
  score observed: 406.

## Reproduce

```bash
python3 crazy_eights_sim.py --games 10000 --seed 42
python3 crazy_eights_sim.py --games 20000 --seed 789 --strategies greedy-points hybrid suit-major defensive
python3 crazy_eights_sim.py --games 30000 --seed 999 --strategies hybrid greedy-points hybrid greedy-points
```
