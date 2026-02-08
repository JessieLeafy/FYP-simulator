"""Write summary JSON and deals CSV to the run directory."""
from __future__ import annotations

import csv
import json
import os
from typing import Any

from src.core.types import NegotiationResult


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
