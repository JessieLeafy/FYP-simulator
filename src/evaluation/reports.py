"""Write summary JSON, deals CSV, and experiment-specific outputs.

All writers are pure functions: they take data + a directory path and
write files.  No LLM calls, no side-effects beyond file I/O.
"""
from __future__ import annotations

import csv
import json
import os
from typing import Any

from src.core.types import MarketTickStats, NegotiationResult


def write_summary(metrics: dict[str, Any], run_dir: str) -> str:
    """Write aggregate metrics as ``summary.json``."""
    path = os.path.join(run_dir, "summary.json")
    with open(path, "w") as f:
        json.dump(metrics, f, indent=2)
    return path


_DEAL_FIELDS = [
    "time_step",
    "item_id",
    "item_name",
    "buyer_id",
    "seller_id",
    "deal_made",
    "deal_price",
    "termination_reason",
    "rounds_taken",
    "buyer_value",
    "seller_cost",
    "buyer_surplus",
    "seller_surplus",
]


def write_deals_csv(results: list[NegotiationResult], run_dir: str) -> str:
    """Write per-negotiation rows as ``deals.csv``."""
    path = os.path.join(run_dir, "deals.csv")
    with open(path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=_DEAL_FIELDS)
        writer.writeheader()
        for r in results:
            writer.writerow({
                "time_step": r.time_step,
                "item_id": r.item.item_id,
                "item_name": r.item.name,
                "buyer_id": r.buyer_id,
                "seller_id": r.seller_id,
                "deal_made": r.deal_made,
                "deal_price": r.deal_price,
                "termination_reason": r.termination_reason.value,
                "rounds_taken": r.rounds_taken,
                "buyer_value": r.buyer_value,
                "seller_cost": r.seller_cost,
                "buyer_surplus": r.buyer_surplus,
                "seller_surplus": r.seller_surplus,
            })
    return path


# ═══════════════════════════════════════════════════════════════════════
#  Experiment-specific outputs
# ═══════════════════════════════════════════════════════════════════════

def write_tick_stats_csv(
    tick_stats: list[MarketTickStats], run_dir: str,
) -> str:
    """Write per-tick market statistics as ``tick_stats.csv``."""
    fields = [
        "tick", "num_sessions", "deals_made", "liquidity",
        "mean_price", "price_std", "buyer_surplus_mean",
        "seller_surplus_mean",
    ]
    path = os.path.join(run_dir, "tick_stats.csv")
    with open(path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for ts in tick_stats:
            writer.writerow({
                "tick": ts.tick,
                "num_sessions": ts.num_sessions,
                "deals_made": ts.deals_made,
                "liquidity": ts.liquidity,
                "mean_price": ts.mean_price,
                "price_std": ts.price_std,
                "buyer_surplus_mean": ts.buyer_surplus_mean,
                "seller_surplus_mean": ts.seller_surplus_mean,
            })
    return path


def write_concession_csv(
    rows: list[dict[str, Any]], run_dir: str,
) -> str:
    """Write concession curve data.

    Expected row keys: condition, session_id, role, round, offer_price.
    """
    fields = ["condition", "session_id", "role", "round", "offer_price"]
    path = os.path.join(run_dir, "concession_curves.csv")
    with open(path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    return path


def write_anchoring_csv(
    rows: list[dict[str, Any]], run_dir: str,
) -> str:
    """Write anchoring experiment data.

    Expected row keys: condition, session_id, first_offer, final_price,
    deal_made.
    """
    fields = ["condition", "session_id", "first_offer", "final_price", "deal_made"]
    path = os.path.join(run_dir, "anchoring.csv")
    with open(path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    return path


def write_deadline_csv(
    rows: list[dict[str, Any]], run_dir: str,
) -> str:
    """Write deadline effects data.

    Expected row keys: condition, session_id, deal_made, rounds_taken.
    """
    fields = ["condition", "session_id", "deal_made", "rounds_taken"]
    path = os.path.join(run_dir, "deadline.csv")
    with open(path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    return path


def write_experiment_summary(
    data: dict[str, Any], run_dir: str,
) -> str:
    """Write ``experiment_summary.json`` with metrics + config + git hash."""
    path = os.path.join(run_dir, "experiment_summary.json")
    with open(path, "w") as f:
        json.dump(data, f, indent=2)
    return path
