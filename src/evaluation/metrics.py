"""Compute aggregate evaluation metrics from negotiation results."""
from __future__ import annotations

import statistics
from typing import Any

from src.core.types import NegotiationResult, TerminationReason


def compute_metrics(results: list[NegotiationResult]) -> dict[str, Any]:
    """Return a flat dict of summary metrics suitable for JSON serialisation."""
    if not results:
        return _empty_metrics()

    total = len(results)
    deals = [r for r in results if r.deal_made]
    deal_count = len(deals)

    deal_prices = [r.deal_price for r in deals if r.deal_price is not None]
    buyer_surpluses = [r.buyer_surplus for r in deals]
    seller_surpluses = [r.seller_surplus for r in deals]

    deal_rounds = [r.rounds_taken for r in deals]
    all_rounds = [r.rounds_taken for r in results]

    # risk events
    all_risk: list[dict] = []
    for r in results:
        all_risk.extend(r.risk_events)
    budget_violations = sum(
        1 for e in all_risk if e.get("violation_type") == "budget"
    )
    cost_violations = sum(
        1 for e in all_risk if e.get("violation_type") == "cost"
    )

    timeouts = sum(
        1 for r in results
        if r.termination_reason == TerminationReason.TIMEOUT
    )

    return {
        "total_negotiations": total,
        "deals_made": deal_count,
        "deal_success_rate": round(deal_count / total, 4) if total else 0,
        "avg_price": round(statistics.mean(deal_prices), 2) if deal_prices else 0,
        "median_price": round(statistics.median(deal_prices), 2) if deal_prices else 0,
        "price_std": (
            round(statistics.stdev(deal_prices), 2) if len(deal_prices) > 1 else 0
        ),
        "buyer_surplus_mean": (
            round(statistics.mean(buyer_surpluses), 2) if buyer_surpluses else 0
        ),
        "seller_surplus_mean": (
            round(statistics.mean(seller_surpluses), 2) if seller_surpluses else 0
        ),
        "welfare_mean": (
            round(
                statistics.mean(
                    [b + s for b, s in zip(buyer_surpluses, seller_surpluses)]
                ),
                2,
            )
            if buyer_surpluses
            else 0
        ),
        "avg_rounds_to_close": (
            round(statistics.mean(deal_rounds), 2) if deal_rounds else 0
        ),
        "avg_rounds_all": round(statistics.mean(all_rounds), 2) if all_rounds else 0,
        "budget_violation_attempts": budget_violations,
        "cost_violation_attempts": cost_violations,
        "deadlock_rate": round(timeouts / total, 4) if total else 0,
        "timeouts": timeouts,
        "total_risk_events": len(all_risk),
    }


def _empty_metrics() -> dict[str, Any]:
    return {
        "total_negotiations": 0,
        "deals_made": 0,
        "deal_success_rate": 0,
        "avg_price": 0,
        "median_price": 0,
        "price_std": 0,
        "buyer_surplus_mean": 0,
        "seller_surplus_mean": 0,
        "welfare_mean": 0,
        "avg_rounds_to_close": 0,
        "avg_rounds_all": 0,
        "budget_violation_attempts": 0,
        "cost_violation_attempts": 0,
        "deadlock_rate": 0,
        "timeouts": 0,
        "total_risk_events": 0,
    }
