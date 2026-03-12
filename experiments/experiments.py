"""Experiment runner: structured experiments for economic analysis.

Each experiment function:
  1. Sets up a run directory
  2. Executes one or more simulation runs (varying seeds or conditions)
  3. Writes aggregated CSVs + experiment_summary.json

All experiments use the existing MarketSimulator and are config-driven
and seed-controlled for reproducibility.
"""
from __future__ import annotations

import copy
import json
import os
import subprocess
import time
from typing import Any

from src.core.config import SimulationConfig, load_config
from src.core.rng import SeededRNG
from src.core.types import ActionType, AgentRole
from src.evaluation.metrics import (
    compute_allocative_efficiency,
    compute_metrics,
    compute_surplus_gini,
    compute_tick_stats,
)
from src.evaluation.reports import (
    write_anchoring_csv,
    write_concession_csv,
    write_deadline_csv,
    write_experiment_summary,
    write_mechanism_csv,
    write_tick_stats_csv,
)
from src.evaluation.stats import pearson_correlation, simple_linear_regression
from src.market.simulator import MarketSimulator


def _git_hash() -> str:
    """Return short git hash or 'unknown'."""
    try:
        out = subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"],
            stderr=subprocess.DEVNULL,
        )
        return out.decode().strip()
    except Exception:
        return "unknown"


def _make_run_dir(base: str, experiment_name: str) -> str:
    """Create a timestamped experiment output directory."""
    ts = time.strftime("%Y%m%d_%H%M%S")
    run_dir = os.path.join(base, f"exp_{experiment_name}_{ts}")
    os.makedirs(run_dir, exist_ok=True)
    return run_dir


def _extract_offers(result) -> list[dict[str, Any]]:
    """Extract per-turn offer prices from a NegotiationResult."""
    rows = []
    for turn in result.history:
        if turn.action.offer_price is not None:
            rows.append({
                "role": turn.agent_role.value,
                "round": turn.round_number,
                "offer_price": turn.action.offer_price,
            })
    return rows


def _run_simulation(cfg: SimulationConfig, on_session=None,
                    backend=None) -> MarketSimulator:
    """Run a simulation and return the simulator instance.

    When *backend* is provided, it is reused instead of creating a new one
    (avoids loading the LLM model multiple times and running out of VRAM).
    After the run, the caller can pass ``sim._backend`` to the next call.
    """
    rng = SeededRNG(cfg.seed)
    sim = MarketSimulator(cfg, rng, backend=backend)
    sim.run(on_session=on_session)
    return sim


# ═══════════════════════════════════════════════════════════════════════
#  A) Concession Curves
# ═══════════════════════════════════════════════════════════════════════

def run_concession(
    base_cfg: SimulationConfig,
    output_base: str = "outputs/experiments",
    seeds: list[int] | None = None,
    conditions: dict[str, dict[str, Any]] | None = None,
    on_session=None,
    backend=None,
) -> str | tuple[str, Any]:
    """Run concession-curve experiment.

    Conditions vary agent type or patience. For each condition and seed,
    run a simulation and extract offer-price trajectories per round.

    Returns:
        Path to experiment run directory.
    """
    if seeds is None:
        seeds = [42, 123, 456]
    if conditions is None:
        conditions = {
            "rule_based": {"agent_type": "rule_based"},
            "llm_free_language": {"agent_type": "llm_free_language"},
        }

    run_dir = _make_run_dir(output_base, "concession")
    all_rows: list[dict[str, Any]] = []
    session_counter = 0
    shared_backend = backend

    for cond_name, overrides in conditions.items():
        for seed in seeds:
            cfg = copy.deepcopy(base_cfg)
            cfg.seed = seed
            cfg.output_dir = os.path.join(run_dir, "runs")
            for key, val in overrides.items():
                if "." in key:
                    section, field = key.split(".", 1)
                    setattr(getattr(cfg, section), field, val)
                else:
                    setattr(cfg, key, val)

            sim = _run_simulation(cfg, on_session=on_session,
                                  backend=shared_backend)
            shared_backend = sim._backend
            for result in sim.results:
                session_counter += 1
                for row in _extract_offers(result):
                    row["condition"] = cond_name
                    row["session_id"] = session_counter
                    all_rows.append(row)

    write_concession_csv(all_rows, run_dir)

    summary = {
        "experiment": "concession",
        "conditions": list(conditions.keys()),
        "seeds": seeds,
        "total_sessions": session_counter,
        "total_offer_rows": len(all_rows),
        "git_hash": _git_hash(),
    }
    write_experiment_summary(summary, run_dir)
    return run_dir, shared_backend


# ═══════════════════════════════════════════════════════════════════════
#  B) Anchoring Effect
# ═══════════════════════════════════════════════════════════════════════

def run_anchoring(
    base_cfg: SimulationConfig,
    output_base: str = "outputs/experiments",
    seeds: list[int] | None = None,
    on_session=None,
    backend=None,
) -> str | tuple[str, Any]:
    """Run anchoring experiment.

    Uses the agent type from base_cfg (typically llm_reactive) with
    different buyer valuations to create different first-offer anchors
    while keeping seller cost fixed — so the zone of possible agreement
    shifts, naturally changing the opening offer.

    Returns:
        Path to experiment run directory.
    """
    if seeds is None:
        seeds = [42, 123, 456]

    conditions = {
        "anchor_low": {"buyer_value": 100.0, "buyer_budget": 110.0},
        "anchor_mid": {"buyer_value": 120.0, "buyer_budget": 130.0},
        "anchor_high": {"buyer_value": 150.0, "buyer_budget": 160.0},
    }

    run_dir = _make_run_dir(output_base, "anchoring")
    all_rows: list[dict[str, Any]] = []
    session_counter = 0
    shared_backend = backend

    for cond_name, overrides in conditions.items():
        for seed in seeds:
            cfg = copy.deepcopy(base_cfg)
            cfg.seed = seed
            cfg.scenario_mode = "fixed"
            cfg.output_dir = os.path.join(run_dir, "runs")
            if cfg.fixed.seller_cost is None:
                cfg.fixed.seller_cost = 80.0
            if cfg.fixed.seller_target_margin is None:
                cfg.fixed.seller_target_margin = 0.15
            if cfg.fixed.item_reference_price is None:
                cfg.fixed.item_reference_price = 100.0
            cfg.fixed.buyer_value = overrides["buyer_value"]
            cfg.fixed.buyer_budget = overrides["buyer_budget"]

            sim = _run_simulation(cfg, on_session=on_session,
                                  backend=shared_backend)
            shared_backend = sim._backend
            for result in sim.results:
                session_counter += 1
                # extract first offer and final price
                first_offer = None
                for turn in result.history:
                    if turn.action.offer_price is not None:
                        first_offer = turn.action.offer_price
                        break
                all_rows.append({
                    "condition": cond_name,
                    "session_id": session_counter,
                    "first_offer": first_offer,
                    "final_price": result.deal_price,
                    "deal_made": result.deal_made,
                })

    write_anchoring_csv(all_rows, run_dir)

    # compute correlation between first_offer and final_price (deals only)
    deals = [r for r in all_rows if r["deal_made"] and r["first_offer"] is not None]
    first_offers = [r["first_offer"] for r in deals]
    final_prices = [r["final_price"] for r in deals]
    corr = pearson_correlation(first_offers, final_prices)

    summary = {
        "experiment": "anchoring",
        "conditions": list(conditions.keys()),
        "seeds": seeds,
        "total_sessions": session_counter,
        "deals_with_first_offer": len(deals),
        "first_offer_final_price_correlation": round(corr, 4),
        "git_hash": _git_hash(),
    }
    write_experiment_summary(summary, run_dir)
    return run_dir, shared_backend


# ═══════════════════════════════════════════════════════════════════════
#  C) Deadline Effects
# ═══════════════════════════════════════════════════════════════════════

def run_deadline(
    base_cfg: SimulationConfig,
    output_base: str = "outputs/experiments",
    seeds: list[int] | None = None,
    max_rounds_list: list[int] | None = None,
    on_session=None,
    backend=None,
) -> str | tuple[str, Any]:
    """Run deadline effects experiment.

    Varies max_rounds across {4, 8, 16} and measures agreement-round
    distribution plus success rate.

    Returns:
        Path to experiment run directory.
    """
    if seeds is None:
        seeds = [42, 123, 456]
    if max_rounds_list is None:
        max_rounds_list = [4, 8, 16]

    run_dir = _make_run_dir(output_base, "deadline")
    all_rows: list[dict[str, Any]] = []
    session_counter = 0
    condition_stats: dict[int, dict[str, Any]] = {}
    shared_backend = backend

    for mr in max_rounds_list:
        cond_deals = 0
        cond_total = 0
        last_two_agreements = 0
        for seed in seeds:
            cfg = copy.deepcopy(base_cfg)
            cfg.seed = seed
            cfg.negotiation.max_rounds = mr
            cfg.output_dir = os.path.join(run_dir, "runs")

            sim = _run_simulation(cfg, on_session=on_session,
                                  backend=shared_backend)
            shared_backend = sim._backend
            for result in sim.results:
                session_counter += 1
                cond_total += 1
                if result.deal_made:
                    cond_deals += 1
                    if result.rounds_taken >= mr - 1:
                        last_two_agreements += 1
                all_rows.append({
                    "condition": mr,
                    "session_id": session_counter,
                    "deal_made": result.deal_made,
                    "rounds_taken": result.rounds_taken,
                })

        condition_stats[mr] = {
            "total": cond_total,
            "deals": cond_deals,
            "success_rate": round(cond_deals / cond_total, 4) if cond_total else 0,
            "last_2_round_share": (
                round(last_two_agreements / cond_deals, 4)
                if cond_deals else 0
            ),
        }

    write_deadline_csv(all_rows, run_dir)

    summary = {
        "experiment": "deadline",
        "max_rounds_conditions": max_rounds_list,
        "seeds": seeds,
        "total_sessions": session_counter,
        "condition_stats": {str(k): v for k, v in condition_stats.items()},
        "git_hash": _git_hash(),
    }
    write_experiment_summary(summary, run_dir)
    return run_dir, shared_backend


# ═══════════════════════════════════════════════════════════════════════
#  D) Market Dynamics
# ═══════════════════════════════════════════════════════════════════════

def run_market_dynamics(
    base_cfg: SimulationConfig,
    output_base: str = "outputs/experiments",
    seeds: list[int] | None = None,
    on_session=None,
    backend=None,
    min_steps: int = 20,
) -> str | tuple[str, Any]:
    """Run market dynamics experiment.

    Uses market mode with >=*min_steps* ticks to observe price trends,
    dispersion, and liquidity over time.

    Returns:
        Path to experiment run directory.
    """
    if seeds is None:
        seeds = [42]

    run_dir = _make_run_dir(output_base, "market_dynamics")

    # aggregate tick stats across seeds
    all_tick_data: list[dict[str, Any]] = []
    shared_backend = backend

    for seed in seeds:
        cfg = copy.deepcopy(base_cfg)
        cfg.seed = seed
        cfg.mode = "market"
        if cfg.steps < min_steps:
            cfg.steps = min_steps
        cfg.output_dir = os.path.join(run_dir, "runs")

        sim = _run_simulation(cfg, on_session=on_session,
                              backend=shared_backend)
        shared_backend = sim._backend

        # write per-seed tick stats
        if sim.tick_stats:
            write_tick_stats_csv(sim.tick_stats, run_dir)

        for ts in sim.tick_stats:
            all_tick_data.append({
                "seed": seed,
                "tick": ts.tick,
                "num_sessions": ts.num_sessions,
                "deals_made": ts.deals_made,
                "liquidity": ts.liquidity,
                "mean_price": ts.mean_price,
                "price_std": ts.price_std,
                "buyer_surplus_mean": ts.buyer_surplus_mean,
                "seller_surplus_mean": ts.seller_surplus_mean,
            })

    # compute price trend (simple linear regression over ticks)
    if all_tick_data:
        ticks = [d["tick"] for d in all_tick_data if d["mean_price"] > 0]
        prices = [d["mean_price"] for d in all_tick_data if d["mean_price"] > 0]
        slope, intercept = simple_linear_regression(
            [float(t) for t in ticks], prices,
        )
        liquidity_values = [d["liquidity"] for d in all_tick_data]
        avg_liquidity = sum(liquidity_values) / len(liquidity_values) if liquidity_values else 0
    else:
        slope, intercept, avg_liquidity = 0.0, 0.0, 0.0

    summary = {
        "experiment": "market_dynamics",
        "seeds": seeds,
        "total_ticks": len(all_tick_data),
        "price_trend_slope": round(slope, 4),
        "price_trend_intercept": round(intercept, 2),
        "avg_liquidity": round(avg_liquidity, 4),
        "git_hash": _git_hash(),
    }
    write_experiment_summary(summary, run_dir)
    return run_dir, shared_backend


# ═══════════════════════════════════════════════════════════════════════
#  E) Shock Response (optional but recommended)
# ═══════════════════════════════════════════════════════════════════════

def run_shock_response(
    base_cfg: SimulationConfig,
    output_base: str = "outputs/experiments",
    seeds: list[int] | None = None,
    on_session=None,
    backend=None,
) -> str | tuple[str, Any]:
    """Run shock-response experiment.

    Compares market dynamics with and without shocks enabled.

    Returns:
        Path to experiment run directory.
    """
    if seeds is None:
        seeds = [42]

    run_dir = _make_run_dir(output_base, "shock_response")

    conditions = {
        "no_shock": {"shock.enabled": False},
        "with_shock": {
            "shock.enabled": True,
            "shock.shock_probability": 0.3,
        },
    }

    all_tick_data: list[dict[str, Any]] = []
    shared_backend = backend

    for cond_name, overrides in conditions.items():
        for seed in seeds:
            cfg = copy.deepcopy(base_cfg)
            cfg.seed = seed
            cfg.mode = "market"
            if cfg.steps < 20:
                cfg.steps = 20
            cfg.output_dir = os.path.join(run_dir, "runs")

            for key, val in overrides.items():
                if "." in key:
                    section, field = key.split(".", 1)
                    setattr(getattr(cfg, section), field, val)
                else:
                    setattr(cfg, key, val)

            sim = _run_simulation(cfg, on_session=on_session,
                                  backend=shared_backend)
            shared_backend = sim._backend

            for ts in sim.tick_stats:
                all_tick_data.append({
                    "condition": cond_name,
                    "seed": seed,
                    "tick": ts.tick,
                    "mean_price": ts.mean_price,
                    "price_std": ts.price_std,
                    "liquidity": ts.liquidity,
                })

    # write combined tick data as CSV
    if all_tick_data:
        import csv
        fields = list(all_tick_data[0].keys())
        path = os.path.join(run_dir, "shock_tick_data.csv")
        with open(path, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fields)
            writer.writeheader()
            writer.writerows(all_tick_data)

    summary = {
        "experiment": "shock_response",
        "conditions": list(conditions.keys()),
        "seeds": seeds,
        "total_tick_records": len(all_tick_data),
        "git_hash": _git_hash(),
    }
    write_experiment_summary(summary, run_dir)
    return run_dir, shared_backend


# ═══════════════════════════════════════════════════════════════════════
#  H) Market Mechanism Comparison
# ═══════════════════════════════════════════════════════════════════════

def run_mechanism(
    base_cfg: SimulationConfig,
    output_base: str = "outputs/experiments",
    seeds: list[int] | None = None,
    conditions: list[str] | None = None,
    on_session=None,
    backend=None,
) -> str | tuple[str, Any]:
    """Run market mechanism comparison experiment.

    Compares different buyer-seller matching mechanisms (e.g. random vs
    surplus_max) to measure effects on allocative efficiency, price
    convergence, and welfare distribution.

    Returns:
        Path to experiment run directory.
    """
    if seeds is None:
        seeds = [42, 123, 456]
    if conditions is None:
        conditions = ["random", "surplus_max"]

    run_dir = _make_run_dir(output_base, "mechanism")
    all_tick_data: list[dict[str, Any]] = []
    condition_results: dict[str, list[Any]] = {c: [] for c in conditions}
    shared_backend = backend

    for cond_name in conditions:
        for seed in seeds:
            cfg = copy.deepcopy(base_cfg)
            cfg.seed = seed
            cfg.mode = "market"
            cfg.matching = cond_name
            cfg.output_dir = os.path.join(run_dir, "runs")

            sim = _run_simulation(cfg, on_session=on_session,
                                  backend=shared_backend)
            shared_backend = sim._backend

            # collect results for per-condition aggregates
            condition_results[cond_name].extend(sim.results)

            for ts in sim.tick_stats:
                all_tick_data.append({
                    "condition": cond_name,
                    "seed": seed,
                    "tick": ts.tick,
                    "num_sessions": ts.num_sessions,
                    "deals_made": ts.deals_made,
                    "liquidity": ts.liquidity,
                    "mean_price": ts.mean_price,
                    "price_std": ts.price_std,
                    "buyer_surplus_mean": ts.buyer_surplus_mean,
                    "seller_surplus_mean": ts.seller_surplus_mean,
                })

    # write combined tick-level CSV
    if all_tick_data:
        write_mechanism_csv(all_tick_data, run_dir)

    # compute per-condition aggregates
    condition_stats: dict[str, dict[str, Any]] = {}
    for cond_name in conditions:
        results = condition_results[cond_name]
        deals = [r for r in results if r.deal_made]
        deal_prices = [r.deal_price for r in deals if r.deal_price is not None]
        all_surpluses = [
            r.buyer_surplus + r.seller_surplus for r in deals
        ]

        alloc_eff = compute_allocative_efficiency(results)
        gini = compute_surplus_gini(all_surpluses)

        condition_stats[cond_name] = {
            "total_sessions": len(results),
            "deals_made": len(deals),
            "deal_rate": round(len(deals) / len(results), 4) if results else 0,
            "mean_price": (
                round(sum(deal_prices) / len(deal_prices), 2)
                if deal_prices else 0
            ),
            "price_std": (
                round(
                    (sum((p - sum(deal_prices) / len(deal_prices)) ** 2
                         for p in deal_prices) / len(deal_prices)) ** 0.5, 2
                )
                if len(deal_prices) > 1 else 0
            ),
            "allocative_efficiency": alloc_eff,
            "surplus_gini": gini,
            "buyer_surplus_mean": (
                round(sum(r.buyer_surplus for r in deals) / len(deals), 2)
                if deals else 0
            ),
            "seller_surplus_mean": (
                round(sum(r.seller_surplus for r in deals) / len(deals), 2)
                if deals else 0
            ),
        }

    summary = {
        "experiment": "mechanism",
        "conditions": conditions,
        "seeds": seeds,
        "total_tick_records": len(all_tick_data),
        "condition_stats": condition_stats,
        "git_hash": _git_hash(),
    }
    write_experiment_summary(summary, run_dir)
    return run_dir, shared_backend


# ═══════════════════════════════════════════════════════════════════════
#  I) Supply-Demand Structure
# ═══════════════════════════════════════════════════════════════════════

def run_supply_demand(
    base_cfg: SimulationConfig,
    output_base: str = "outputs/experiments",
    seeds: list[int] | None = None,
    on_session=None,
    backend=None,
) -> str | tuple[str, Any]:
    """Run supply-demand structure experiment.

    Tests the law of supply and demand: do transaction prices and trade
    volume respond in the expected direction when demand or supply shifts?

    Conditions:
        baseline:     standard buyer/seller distributions
        demand_shock: buyer values shifted upward (+20)
        supply_shock: seller costs shifted upward (+20)

    Returns:
        Path to experiment run directory.
    """
    if seeds is None:
        seeds = [42]

    run_dir = _make_run_dir(output_base, "supply_demand")

    # Define conditions as overrides to market distribution parameters.
    # Baseline matches the YAML config.  Demand/supply shifts are +20
    # relative to the baseline ranges.
    conditions = {
        "baseline": {
            "market.buyer_value_min": 90.0,
            "market.buyer_value_max": 170.0,
            "market.seller_cost_min": 40.0,
            "market.seller_cost_max": 90.0,
        },
        "demand_shock": {
            "market.buyer_value_min": 110.0,
            "market.buyer_value_max": 190.0,
            "market.seller_cost_min": 40.0,
            "market.seller_cost_max": 90.0,
        },
        "supply_shock": {
            "market.buyer_value_min": 90.0,
            "market.buyer_value_max": 170.0,
            "market.seller_cost_min": 60.0,
            "market.seller_cost_max": 110.0,
        },
    }

    all_condition_data: list[dict[str, Any]] = []
    shared_backend = backend

    for cond_name, overrides in conditions.items():
        # Compute expected average values from distribution
        avg_buyer_value = (overrides["market.buyer_value_min"] +
                           overrides["market.buyer_value_max"]) / 2
        avg_seller_cost = (overrides["market.seller_cost_min"] +
                           overrides["market.seller_cost_max"]) / 2

        for seed in seeds:
            cfg = copy.deepcopy(base_cfg)
            cfg.seed = seed
            cfg.mode = "market"
            cfg.output_dir = os.path.join(run_dir, "runs")

            # Apply market distribution overrides
            for key, val in overrides.items():
                section, field = key.split(".", 1)
                setattr(getattr(cfg, section), field, val)

            sim = _run_simulation(cfg, on_session=on_session,
                                  backend=shared_backend)
            shared_backend = sim._backend

            # Aggregate tick stats for this condition+seed
            if sim.tick_stats:
                prices = [ts.mean_price for ts in sim.tick_stats if ts.mean_price > 0]
                liquidity_vals = [ts.liquidity for ts in sim.tick_stats]
                buyer_surp = [ts.buyer_surplus_mean for ts in sim.tick_stats if ts.deals_made > 0]
                seller_surp = [ts.seller_surplus_mean for ts in sim.tick_stats if ts.deals_made > 0]
                price_stds = [ts.price_std for ts in sim.tick_stats if ts.price_std > 0]

                mean_price = sum(prices) / len(prices) if prices else 0
                avg_liquidity = sum(liquidity_vals) / len(liquidity_vals) if liquidity_vals else 0
                avg_buyer_surplus = sum(buyer_surp) / len(buyer_surp) if buyer_surp else 0
                avg_seller_surplus = sum(seller_surp) / len(seller_surp) if seller_surp else 0
                total_welfare = avg_buyer_surplus + avg_seller_surplus
                avg_price_std = sum(price_stds) / len(price_stds) if price_stds else 0

                all_condition_data.append({
                    "condition": cond_name,
                    "seed": seed,
                    "avg_buyer_value": round(avg_buyer_value, 2),
                    "avg_seller_cost": round(avg_seller_cost, 2),
                    "mean_price": round(mean_price, 2),
                    "liquidity": round(avg_liquidity, 4),
                    "total_welfare": round(total_welfare, 2),
                    "buyer_surplus": round(avg_buyer_surplus, 2),
                    "seller_surplus": round(avg_seller_surplus, 2),
                    "price_dispersion": round(avg_price_std, 2),
                })

    # Write results CSV
    if all_condition_data:
        import csv
        fields = list(all_condition_data[0].keys())
        path = os.path.join(run_dir, "supply_demand_results.csv")
        with open(path, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fields)
            writer.writeheader()
            writer.writerows(all_condition_data)

    # Compute summary statistics per condition
    condition_summaries = {}
    for cond_name in conditions:
        cond_rows = [r for r in all_condition_data if r["condition"] == cond_name]
        if cond_rows:
            condition_summaries[cond_name] = {
                "avg_buyer_value": cond_rows[0]["avg_buyer_value"],
                "avg_seller_cost": cond_rows[0]["avg_seller_cost"],
                "mean_price": round(sum(r["mean_price"] for r in cond_rows) / len(cond_rows), 2),
                "liquidity": round(sum(r["liquidity"] for r in cond_rows) / len(cond_rows), 4),
                "total_welfare": round(sum(r["total_welfare"] for r in cond_rows) / len(cond_rows), 2),
                "buyer_surplus": round(sum(r["buyer_surplus"] for r in cond_rows) / len(cond_rows), 2),
                "seller_surplus": round(sum(r["seller_surplus"] for r in cond_rows) / len(cond_rows), 2),
                "price_dispersion": round(sum(r["price_dispersion"] for r in cond_rows) / len(cond_rows), 2),
            }

    summary = {
        "experiment": "supply_demand",
        "conditions": list(conditions.keys()),
        "seeds": seeds,
        "total_condition_seed_runs": len(all_condition_data),
        "condition_summaries": condition_summaries,
        "git_hash": _git_hash(),
    }
    write_experiment_summary(summary, run_dir)
    return run_dir, shared_backend


# ═══════════════════════════════════════════════════════════════════════
#  Dispatcher
# ═══════════════════════════════════════════════════════════════════════

EXPERIMENT_REGISTRY = {
    "concession": run_concession,
    "anchoring": run_anchoring,
    "deadline": run_deadline,
    "market_dynamics": run_market_dynamics,
    "shock_response": run_shock_response,
    "mechanism": run_mechanism,
    "supply_demand": run_supply_demand,
}


def run_experiment(
    name: str,
    base_cfg: SimulationConfig,
    output_base: str = "outputs/experiments",
    seeds: list[int] | None = None,
    **kwargs: Any,
) -> str:
    """Dispatch to the named experiment runner.

    Returns:
        Path to experiment run directory.
    """
    if name not in EXPERIMENT_REGISTRY:
        raise ValueError(
            f"Unknown experiment: {name!r}. "
            f"Available: {list(EXPERIMENT_REGISTRY.keys())}"
        )
    runner = EXPERIMENT_REGISTRY[name]
    return runner(base_cfg, output_base=output_base, seeds=seeds, **kwargs)
