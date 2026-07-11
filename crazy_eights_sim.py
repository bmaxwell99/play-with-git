#!/usr/bin/env python3
"""Monte Carlo simulator for a Crazy Eights countdown variant.

Rules (as specified):
- 4 players, one standard 52-card deck per round.
- 15 rounds: hand sizes 1,2,3,4,5,6,7,8,7,6,5,4,3,2,1.
- Each round: deal, flip top card to start the pile. If the starter is an 8
  it is shuffled back into the deck and a new card is flipped.
- A play must match the top card's rank or the current suit.
- Special cards (must still match rank-or-suit to be played):
    8   - player names the suit the next player must follow (8 also matches by rank)
    2   - next player draws 2 unless they chain another 2; the pot stacks
          (+2 per chained 2) and the first player who can't/won't chain draws
          the whole pot, ending their turn
    3   - next player's turn is skipped
    Ace - direction of play reverses
- A special starter card affects the first player (flipped 2 starts a 2-pot,
  flipped 3 skips the first player, flipped Ace reverses direction).
- If a player has no legal play they draw exactly 1 card and their turn ends
  (no playing the drawn card).
- When the draw pile is empty, the discard pile except the top card is
  reshuffled into it. If there is still nothing to draw, the turn passes.
- First player to empty their hand ("go out") scores 0; the round ends
  immediately and everyone else scores their hand:
    8 = 50, 2 = 20, J/Q/K = 10, Ace = 1, others = pip value.
- Golf scoring: lowest total over 15 rounds wins. Going out on an 8 is allowed.
"""

from __future__ import annotations

import argparse
import math
import random
from collections import Counter, defaultdict

SUITS = "SHDC"
RANKS = ["A", "2", "3", "4", "5", "6", "7", "8", "9", "10", "J", "Q", "K"]
POINTS = {"A": 1, "2": 20, "3": 3, "4": 4, "5": 5, "6": 6, "7": 7,
          "8": 50, "9": 9, "10": 10, "J": 10, "Q": 10, "K": 10}
HAND_SIZES = list(range(1, 9)) + list(range(7, 0, -1))  # 1..8..1, 15 rounds

FULL_DECK = [(r, s) for r in RANKS for s in SUITS]


def hand_points(hand):
    return sum(POINTS[r] for r, _ in hand)


# ---------------------------------------------------------------------------
# Strategies
#
# A strategy answers three questions:
#   choose_play(hand, legal, state)  -> card to play, or None to draw instead
#   choose_suit(hand, state)         -> suit named after playing an 8
#   chain_two(hand, twos, state)     -> a 2 to chain with, or None to eat the pot
# `state` gives top_rank, current_suit, pot size, opponents' hand sizes, etc.
# ---------------------------------------------------------------------------

class Strategy:
    name = "base"

    def choose_play(self, hand, legal, state):
        raise NotImplementedError

    def choose_suit(self, hand, state):
        # Default: name the suit we hold the most of.
        counts = Counter(s for _, s in hand)
        if not counts:
            return state["rng"].choice(SUITS)
        best = max(counts.values())
        options = [s for s, c in counts.items() if c == best]
        return state["rng"].choice(options)

    def chain_two(self, hand, twos, state):
        # Default: always chain if possible (holding a 2 risks 20 points and
        # eating a stacked pot).
        return twos[0] if twos else None


class RandomStrategy(Strategy):
    """Uniformly random legal play, random suit call."""
    name = "random"

    def choose_play(self, hand, legal, state):
        return state["rng"].choice(legal)

    def choose_suit(self, hand, state):
        return state["rng"].choice(SUITS)

    def chain_two(self, hand, twos, state):
        return state["rng"].choice(twos) if twos and state["rng"].random() < 0.5 else None


class GreedyPointsStrategy(Strategy):
    """Shed the most expensive legal card first (8s, then 2s, then faces)."""
    name = "greedy-points"

    def choose_play(self, hand, legal, state):
        return max(legal, key=lambda c: (POINTS[c[0]], state["rng"].random()))


class LowFirstStrategy(Strategy):
    """Shed the cheapest legal card first (keeps liabilities; control arm)."""
    name = "low-first"

    def choose_play(self, hand, legal, state):
        return min(legal, key=lambda c: (POINTS[c[0]], state["rng"].random()))


class SuitMajorityStrategy(Strategy):
    """Steer the pile toward the suit we hold most of; high points tiebreak.

    Playing into our long suit keeps future turns playable, reducing draws.
    """
    name = "suit-major"

    def choose_play(self, hand, legal, state):
        counts = Counter(s for _, s in hand)
        return max(legal, key=lambda c: (counts[c[1]], POINTS[c[0]], state["rng"].random()))


class Hoard8Strategy(Strategy):
    """Greedy on points but keeps 8s as a going-out tool until the hand is
    small (<=2 cards) or an 8 is the only legal play."""
    name = "hoard-8"

    def choose_play(self, hand, legal, state):
        non_eights = [c for c in legal if c[0] != "8"]
        if non_eights and len(hand) > 2:
            legal = non_eights
        return max(legal, key=lambda c: (POINTS[c[0]], state["rng"].random()))


class DefensiveStrategy(Strategy):
    """Greedy points, but when any opponent is close to going out (<=2 cards),
    prefer specials that disrupt them: 3 (skip) and 2 (force draws) get a big
    bonus, and 8 lets us steer the suit."""
    name = "defensive"

    BONUS = {"3": 100, "2": 90, "A": 40, "8": 60}

    def choose_play(self, hand, legal, state):
        threat = min(state["opp_sizes"]) <= 2

        def score(c):
            pts = POINTS[c[0]]
            if threat and c[0] in self.BONUS:
                pts += self.BONUS[c[0]]
            return (pts, state["rng"].random())

        return max(legal, key=score)


class HybridStrategy(Strategy):
    """Shed by points first, break ties toward our most-held suit."""
    name = "hybrid"

    def choose_play(self, hand, legal, state):
        counts = Counter(s for _, s in hand)
        return max(legal, key=lambda c: (POINTS[c[0]], counts[c[1]], state["rng"].random()))


class CountingStrategy(Strategy):
    """Hybrid plus card counting of the discard pile.

    Tracks which suits/ranks remain unseen (opponents' hands + draw pile).
    Sheds by points, then long-suit, then prefers to discard the card least
    likely to be playable later (fewest unseen suit/rank matches). After an 8,
    names its longest suit, breaking ties toward the suit opponents are least
    likely to hold.
    """
    name = "counter"

    @staticmethod
    def _unseen(hand, state):
        suit_unseen = Counter({s: 13 for s in SUITS})
        rank_unseen = Counter({r: 4 for r in RANKS})
        for r, s in state["discard"]:
            suit_unseen[s] -= 1
            rank_unseen[r] -= 1
        for r, s in hand:
            suit_unseen[s] -= 1
            rank_unseen[r] -= 1
        return suit_unseen, rank_unseen

    def choose_play(self, hand, legal, state):
        counts = Counter(s for _, s in hand)
        suit_unseen, rank_unseen = self._unseen(hand, state)

        def liveness(c):
            return suit_unseen[c[1]] + rank_unseen[c[0]]

        return max(legal, key=lambda c: (POINTS[c[0]], counts[c[1]],
                                         -liveness(c), state["rng"].random()))

    def choose_suit(self, hand, state):
        counts = Counter(s for _, s in hand)
        suit_unseen, _ = self._unseen(hand, state)
        return max(SUITS, key=lambda s: (counts[s], -suit_unseen[s],
                                         state["rng"].random()))


STRATEGIES = {cls.name: cls for cls in
              (RandomStrategy, GreedyPointsStrategy, LowFirstStrategy,
               SuitMajorityStrategy, Hoard8Strategy, DefensiveStrategy,
               HybridStrategy, CountingStrategy)}


# ---------------------------------------------------------------------------
# Round engine
# ---------------------------------------------------------------------------

def play_round(strategies, hand_size, start_player, rng, max_turns=2000,
               stats=None):
    """Play one round; return list of scores per seat (0 for the winner).

    If `stats` is a list, appends (dealt_hand_size, end_hand_sizes_per_seat,
    winner_seat_or_None) when the round ends."""
    n = len(strategies)
    deck = FULL_DECK[:]
    rng.shuffle(deck)
    hands = [[deck.pop() for _ in range(hand_size)] for _ in range(n)]

    # Flip the starter; 8s go back into the deck.
    starter = deck.pop()
    while starter[0] == "8":
        deck.append(starter)
        rng.shuffle(deck)
        starter = deck.pop()
    discard = [starter]
    top_rank, current_suit = starter
    direction = 1
    pot = 0            # stacked draw-2 pot awaiting the current player
    skip_next = False  # current player is skipped
    turn = start_player

    # Starter specials hit the first player.
    if starter[0] == "2":
        pot = 2
    elif starter[0] == "3":
        skip_next = True
    elif starter[0] == "A":
        direction = -1

    def draw_one():
        if not deck:
            if len(discard) > 1:
                deck.extend(discard[:-1])
                del discard[:-1]
                rng.shuffle(deck)
            else:
                return None
        return deck.pop()

    for _ in range(max_turns):
        if skip_next:
            skip_next = False
            turn = (turn + direction) % n
            continue

        hand = hands[turn]
        strat = strategies[turn]
        state = {
            "top_rank": top_rank,
            "current_suit": current_suit,
            "pot": pot,
            "hand_size": hand_size,
            "opp_sizes": [len(hands[i]) for i in range(n) if i != turn],
            "discard": discard,
            "rng": rng,
        }

        played = None
        if pot:
            twos = [c for c in hand if c[0] == "2"]
            played = strat.chain_two(hand, twos, state)
            if played is None:
                for _ in range(pot):
                    card = draw_one()
                    if card is None:
                        break
                    hand.append(card)
                pot = 0
        else:
            legal = [c for c in hand if c[0] == top_rank or c[1] == current_suit]
            if legal:
                played = strat.choose_play(hand, legal, state)
            if played is None:
                card = draw_one()
                if card is not None:
                    hand.append(card)

        if played is not None:
            hand.remove(played)
            discard.append(played)
            top_rank, current_suit = played
            if played[0] == "8":
                current_suit = strat.choose_suit(hand, state)
            if not hand:  # went out — round over, specials fizzle
                if stats is not None:
                    stats.append((hand_size, [len(h) for h in hands], turn))
                return [0 if i == turn else hand_points(hands[i]) for i in range(n)]
            if played[0] == "2":
                pot += 2
            elif played[0] == "3":
                skip_next = True
            elif played[0] == "A":
                direction = -direction

        turn = (turn + direction) % n

    # Safety valve: deadlocked round (essentially unreachable) — score as-is.
    if stats is not None:
        stats.append((hand_size, [len(h) for h in hands], None))
    return [hand_points(h) for h in hands]


def play_game(strategies, rng, stats=None):
    """15-round game; returns total score per seat."""
    totals = [0] * len(strategies)
    for rnd, hand_size in enumerate(HAND_SIZES):
        scores = play_round(strategies, hand_size, rnd % len(strategies), rng,
                            stats=stats)
        for i, s in enumerate(scores):
            totals[i] += s
    return totals


# ---------------------------------------------------------------------------
# Experiment harness
# ---------------------------------------------------------------------------

def run_experiment(games, seed, strategy_names):
    rng = random.Random(seed)
    pool = list(strategy_names)
    score_sum = defaultdict(float)
    score_sqsum = defaultdict(float)
    wins = defaultdict(int)
    plays = defaultdict(int)

    for _ in range(games):
        chosen = rng.sample(pool, 4) if len(pool) > 4 else pool[:]
        rng.shuffle(chosen)  # random seating
        strats = [STRATEGIES[name]() for name in chosen]
        totals = play_game(strats, rng)
        best = min(totals)
        n_best = totals.count(best)
        for name, total in zip(chosen, totals):
            score_sum[name] += total
            score_sqsum[name] += total * total
            plays[name] += 1
            if total == best:
                wins[name] += 1 / n_best  # split ties
    return score_sum, score_sqsum, wins, plays


def report(score_sum, score_sqsum, wins, plays):
    rows = []
    for name in plays:
        n = plays[name]
        mean = score_sum[name] / n
        var = max(score_sqsum[name] / n - mean * mean, 0.0)
        ci95 = 1.96 * math.sqrt(var / n)
        rows.append((mean, ci95, 100 * wins[name] / n, n, name))
    rows.sort()
    print(f"{'strategy':<15}{'mean score':>12}{'±95% CI':>10}{'win rate':>10}{'games':>8}")
    for mean, ci, wr, n, name in rows:
        print(f"{name:<15}{mean:>12.1f}{ci:>9.1f}{wr:>9.1f}%{n:>8}")
    return rows


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--games", type=int, default=10000)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--strategies", nargs="*", default=list(STRATEGIES),
                    help=f"subset of: {', '.join(STRATEGIES)}")
    args = ap.parse_args()

    print(f"Simulating {args.games} games of 15 rounds, 4 players "
          f"(strategies sampled from: {', '.join(args.strategies)})\n")
    report(*run_experiment(args.games, args.seed, args.strategies))


if __name__ == "__main__":
    main()
