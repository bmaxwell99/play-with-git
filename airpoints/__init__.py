"""airpoints — a personal-scale airline award aggregator.

Pull award availability from seats.aero, price each option against your
transferable points (Amex MR / Chase UR) and direct miles (Alaska), and rank
the best choices — optionally with Claude doing the picking and explaining.
"""

from .aggregator import affordable_only, price_options
from .models import AwardOption, FundingPath, PricedOption, Trip
from .monitor import find_new, option_signature, run_monitor
from .pipeline import fetch_for_trip, priced_for_trip
from .ranker import Recommendation, rank_heuristic, rank_with_llm
from .transfers import TransferTable

__all__ = [
    "AwardOption",
    "FundingPath",
    "PricedOption",
    "Trip",
    "TransferTable",
    "price_options",
    "affordable_only",
    "fetch_for_trip",
    "priced_for_trip",
    "rank_heuristic",
    "rank_with_llm",
    "Recommendation",
    "run_monitor",
    "find_new",
    "option_signature",
]
