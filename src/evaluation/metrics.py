"""Compute aggregate evaluation metrics from negotiation results."""
from __future__ import annotations

import statistics
from typing import Any

from src.core.types import MarketTickStats, NegotiationResult, TerminationReason


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


def compute_tick_stats(tick: int, results: list[NegotiationResult]) -> MarketTickStats:
    """Compute aggregate statistics for a single market tick."""
    total = len(results)
    if total == 0:
        return MarketTickStats(
            tick=tick, num_sessions=0, deals_made=0, fail_rate=0,
            mean_price=0, price_std=0, liquidity=0,
            buyer_surplus_mean=0, seller_surplus_mean=0,
        )

    deals = [r for r in results if r.deal_made]
    deal_count = len(deals)
    prices = [r.deal_price for r in deals if r.deal_price is not None]

    return MarketTickStats(
        tick=tick,
        num_sessions=total,
        deals_made=deal_count,
        fail_rate=round((total - deal_count) / total, 4),
        mean_price=round(statistics.mean(prices), 2) if prices else 0,
        price_std=(
            round(statistics.stdev(prices), 2) if len(prices) > 1 else 0
        ),
        liquidity=round(deal_count / total, 4),
        buyer_surplus_mean=(
            round(statistics.mean([r.buyer_surplus for r in deals]), 2)
            if deals else 0
        ),
        seller_surplus_mean=(
            round(statistics.mean([r.seller_surplus for r in deals]), 2)
            if deals else 0
        ),
    )


def compute_allocative_efficiency(
    results: list[NegotiationResult],
) -> float:
    """Compute allocative efficiency: realised welfare / theoretical max welfare.

    Theoretical max welfare for each pair = max(buyer_value - seller_cost, 0).
    Realised welfare for deals = buyer_surplus + seller_surplus (= value - cost).
    For non-deals, realised welfare = 0.

    Returns a value in [0, 1].  Returns 0.0 if theoretical max is 0.
    """
    theoretical_max = 0.0
    realised = 0.0
    for r in results:
        max_surplus = max(r.buyer_value - r.seller_cost, 0.0)
        theoretical_max += max_surplus
        if r.deal_made:
            realised += r.buyer_surplus + r.seller_surplus
    if theoretical_max <= 0:
        return 0.0
    return round(realised / theoretical_max, 4)


def compute_surplus_gini(surpluses: list[float]) -> float:
    """Compute Gini coefficient of a list of surplus values.

    Measures inequality in surplus distribution.  0 = perfect equality,
    1 = maximum inequality.  Returns 0.0 for empty or single-element lists.
    """
    n = len(surpluses)
    if n < 2:
        return 0.0
    s = sorted(surpluses)
    total = sum(s)
    if total == 0:
        return 0.0
    cumulative = 0.0
    weighted_sum = 0.0
    for i, val in enumerate(s):
        cumulative += val
        weighted_sum += (2 * (i + 1) - n - 1) * val
    return round(abs(weighted_sum) / (n * total), 4)


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
