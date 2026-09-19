"""Transfer-ratio table and cheapest-funding logic.

The table is a static, hand-maintained YAML file (transfer ratios change at
most once or twice a year). It maps each transferable currency the user holds
to the loyalty programs it can fund and at what ratio. A program the user
holds directly (e.g. Alaska miles from a Bank of America card) "funds itself"
at ratio 1.0.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import yaml

from .models import FundingPath


@dataclass
class _Funder:
    currency: str
    currency_display: str
    ratio: float
    transfer_time: str
    held_directly: bool


class TransferTable:
    """Loaded transfer-ratio table; answers 'how can I fund program X?'."""

    def __init__(self, currencies: dict):
        # program slug -> list of funders, built once at load time.
        self._by_program: dict[str, list[_Funder]] = {}
        for cur_key, cur in currencies.items():
            display = cur.get("display", cur_key)
            for program, spec in (cur.get("funds") or {}).items():
                # spec may be a bare ratio (1.0) or a dict {ratio, transfer_time}
                if isinstance(spec, dict):
                    ratio = float(spec.get("ratio", 1.0))
                    transfer_time = spec.get("transfer_time", "")
                    held = bool(spec.get("held_directly", False))
                else:
                    ratio = float(spec)
                    transfer_time = ""
                    held = False
                self._by_program.setdefault(program, []).append(
                    _Funder(cur_key, display, ratio, transfer_time, held)
                )

    @classmethod
    def load(cls, path: str) -> "TransferTable":
        with open(path, "r", encoding="utf-8") as fh:
            data = yaml.safe_load(fh) or {}
        return cls(data.get("currencies", {}))

    def programs(self) -> list[str]:
        return sorted(self._by_program)

    def cheapest_funding(
        self, program: str, miles_needed: int, balances: dict[str, int]
    ) -> Optional[FundingPath]:
        """Best way to fund `miles_needed` miles in `program` given balances.

        Ranking: affordable paths first, then fewest points required, then
        prefer directly-held / instant transfers. Returns the single best path,
        or None if no currency can fund this program at all (so callers can
        surface "no funding path" rather than silently dropping the option).
        """
        funders = self._by_program.get(program)
        if not funders:
            return None

        candidates = [
            FundingPath.build(
                currency=f.currency,
                currency_display=f.currency_display,
                program=program,
                ratio=f.ratio,
                miles_needed=miles_needed,
                transfer_time="instant" if f.held_directly else f.transfer_time,
                held_directly=f.held_directly,
                balance=balances.get(f.currency, 0),
            )
            for f in funders
        ]

        def sort_key(p: FundingPath):
            return (
                0 if p.affordable else 1,  # affordable first
                p.points_required,  # cheaper first
                0 if p.held_directly else 1,  # prefer direct holdings
                0 if p.transfer_time == "instant" else 1,
            )

        return min(candidates, key=sort_key)
