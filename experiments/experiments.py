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
from src.evaluation.metrics import compute_metrics, compute_tick_stats
from src.evaluation.reports import (
    write_anchoring_csv,
    write_concession_csv,
    write_deadline_csv,
    write_experiment_summary,
    write_reputation_csv,
    write_reputation_tick_csv,
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


def _run_simulation(cfg: SimulationConfig) -> MarketSimulator:
    """Run a simulation and return the simulator instance."""
    rng = SeededRNG(cfg.seed)
    sim = MarketSimulator(cfg, rng)
    sim.run()
    return sim


# ═══════════════════════════════════════════════════════════════════════
#  A) Concession Curves
# ═══════════════════════════════════════════════════════════════════════

def run_concession(
    base_cfg: SimulationConfig,
    output_base: str = "outputs/experiments",
    seeds: list[int] | None = None,
    conditions: dict[str, dict[str, Any]] | None = None,
) -> str:
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
            "llm_reactive": {"agent_type": "llm_reactive"},
            "llm_deliberative": {"agent_type": "llm_deliberative"},
        }

    run_dir = _make_run_dir(output_base, "concession")
    all_rows: list[dict[str, Any]] = []
    session_counter = 0

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

            sim = _run_simulation(cfg)
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
    return run_dir


# ═══════════════════════════════════════════════════════════════════════
#  B) Anchoring Effect
# ═══════════════════════════════════════════════════════════════════════

def run_anchoring(
    base_cfg: SimulationConfig,
    output_base: str = "outputs/experiments",
    seeds: list[int] | None = None,
) -> str:
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

            sim = _run_simulation(cfg)
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
    return run_dir


# ═══════════════════════════════════════════════════════════════════════
#  C) Deadline Effects
# ═══════════════════════════════════════════════════════════════════════

def run_deadline(
    base_cfg: SimulationConfig,
    output_base: str = "outputs/experiments",
    seeds: list[int] | None = None,
    max_rounds_list: list[int] | None = None,
) -> str:
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

    for mr in max_rounds_list:
        cond_deals = 0
        cond_total = 0
        last_two_agreements = 0
        for seed in seeds:
            cfg = copy.deepcopy(base_cfg)
            cfg.seed = seed
            cfg.negotiation.max_rounds = mr
            cfg.output_dir = os.path.join(run_dir, "runs")

            sim = _run_simulation(cfg)
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
    return run_dir


# ═══════════════════════════════════════════════════════════════════════
#  D) Market Dynamics
# ═══════════════════════════════════════════════════════════════════════

def run_market_dynamics(
    base_cfg: SimulationConfig,
    output_base: str = "outputs/experiments",
    seeds: list[int] | None = None,
) -> str:
    """Run market dynamics experiment.

    Uses market mode with >=20 ticks to observe price trends,
    dispersion, and liquidity over time.

    Returns:
        Path to experiment run directory.
    """
    if seeds is None:
        seeds = [42]

    run_dir = _make_run_dir(output_base, "market_dynamics")

    # aggregate tick stats across seeds
    all_tick_data: list[dict[str, Any]] = []

    for seed in seeds:
        cfg = copy.deepcopy(base_cfg)
        cfg.seed = seed
        cfg.mode = "market"
        if cfg.steps < 20:
            cfg.steps = 20
        cfg.output_dir = os.path.join(run_dir, "runs")

        sim = _run_simulation(cfg)

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
    return run_dir


# ═══════════════════════════════════════════════════════════════════════
#  E) Shock Response (optional but recommended)
# ═══════════════════════════════════════════════════════════════════════

def run_shock_response(
    base_cfg: SimulationConfig,
    output_base: str = "outputs/experiments",
    seeds: list[int] | None = None,
) -> str:
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

            sim = _run_simulation(cfg)

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
    return run_dir


# ═══════════════════════════════════════════════════════════════════════
#  F) Reputation and Memory in Repeated Negotiation
# ═══════════════════════════════════════════════════════════════════════

def run_reputation(
    base_cfg: SimulationConfig,
    output_base: str = "outputs/experiments",
    seeds: list[int] | None = None,
    conditions: dict[str, dict[str, Any]] | None = None,
) -> str:
    """Run reputation & memory experiment.

    Compares two conditions across repeated interactions:
      - no_memory: llm_reactive agents (fresh each session)
      - reputation: ReputationAgent with per-agent memory + opponent
        reputation tracking

    Both conditions use round-robin matching (same buyer-seller pairs
    meet across ticks) and gate_enabled=False so that memory/reputation
    can influence behaviour.

    When *base_cfg.agent_type* is ``rule_based`` the default conditions
    are adjusted so both arms use rule_based agents (useful for smoke
    testing without an LLM backend).

    Returns:
        Path to experiment run directory.
    """
    if seeds is None:
        seeds = [42]

    if conditions is None:
        if base_cfg.agent_type == "rule_based":
            # smoke-test mode: both conditions use rule_based
            conditions = {
                "no_memory": {"agent_type": "rule_based", "memory_per_agent": False},
                "reputation": {"agent_type": "rule_based", "memory_per_agent": False},
            }
        else:
            conditions = {
                "no_memory": {
                    "agent_type": "llm_deliberative",
                    "memory_per_agent": False,
                },
                "reputation": {
                    "agent_type": "reputation",
                    "memory_per_agent": True,
                },
            }

    run_dir = _make_run_dir(output_base, "reputation")
    all_result_rows: list[dict[str, Any]] = []
    all_tick_rows: list[dict[str, Any]] = []
    condition_agg: dict[str, dict[str, Any]] = {}

    for cond_name, overrides in conditions.items():
        cond_deals = 0
        cond_total = 0
        cond_prices: list[float] = []
        cond_buyer_surplus: list[float] = []
        cond_seller_surplus: list[float] = []
        cond_rounds: list[int] = []

        for seed in seeds:
            cfg = copy.deepcopy(base_cfg)
            cfg.seed = seed
            cfg.mode = "market"
            cfg.matching = "round_robin"
            cfg.negotiation.gate_enabled = False
            cfg.output_dir = os.path.join(run_dir, "runs")

            for key, val in overrides.items():
                setattr(cfg, key, val)

            sim = _run_simulation(cfg)

            # collect per-result rows
            for result in sim.results:
                cond_total += 1
                if result.deal_made:
                    cond_deals += 1
                    cond_prices.append(result.deal_price)
                    cond_buyer_surplus.append(result.buyer_surplus)
                    cond_seller_surplus.append(result.seller_surplus)
                cond_rounds.append(result.rounds_taken)

                all_result_rows.append({
                    "condition": cond_name,
                    "seed": seed,
                    "tick": result.time_step,
                    "session_id": f"{cond_name}_s{seed}_t{result.time_step}_{result.buyer_id}_{result.seller_id}",
                    "buyer_id": result.buyer_id,
                    "seller_id": result.seller_id,
                    "deal_made": result.deal_made,
                    "deal_price": result.deal_price,
                    "rounds_taken": result.rounds_taken,
                    "buyer_surplus": result.buyer_surplus,
                    "seller_surplus": result.seller_surplus,
                })

            # collect per-tick rows
            for ts in sim.tick_stats:
                all_tick_rows.append({
                    "condition": cond_name,
                    "seed": seed,
                    "tick": ts.tick,
                    "num_sessions": ts.num_sessions,
                    "deals_made": ts.deals_made,
                    "liquidity": ts.liquidity,
                    "mean_price": ts.mean_price,
                    "buyer_surplus_mean": ts.buyer_surplus_mean,
                    "seller_surplus_mean": ts.seller_surplus_mean,
                })

        condition_agg[cond_name] = {
            "total_sessions": cond_total,
            "deals": cond_deals,
            "deal_rate": round(cond_deals / cond_total, 4) if cond_total else 0,
            "mean_price": (
                round(sum(cond_prices) / len(cond_prices), 2)
                if cond_prices else 0
            ),
            "mean_buyer_surplus": (
                round(sum(cond_buyer_surplus) / len(cond_buyer_surplus), 2)
                if cond_buyer_surplus else 0
            ),
            "mean_seller_surplus": (
                round(sum(cond_seller_surplus) / len(cond_seller_surplus), 2)
                if cond_seller_surplus else 0
            ),
            "mean_rounds": (
                round(sum(cond_rounds) / len(cond_rounds), 2)
                if cond_rounds else 0
            ),
        }

    # write CSVs
    write_reputation_csv(all_result_rows, run_dir)
    write_reputation_tick_csv(all_tick_rows, run_dir)

    summary = {
        "experiment": "reputation",
        "research_question": (
            "Does accumulated experience (memory of past interactions with "
            "specific opponents) affect LLM agent negotiation strategy in "
            "repeated interactions?"
        ),
        "conditions": list(conditions.keys()),
        "seeds": seeds,
        "total_result_rows": len(all_result_rows),
        "total_tick_rows": len(all_tick_rows),
        "condition_stats": condition_agg,
        "git_hash": _git_hash(),
    }
    write_experiment_summary(summary, run_dir)
    return run_dir


# ═══════════════════════════════════════════════════════════════════════
#  Dispatcher
# ═══════════════════════════════════════════════════════════════════════

EXPERIMENT_REGISTRY = {
    "concession": run_concession,
    "anchoring": run_anchoring,
    "deadline": run_deadline,
    "market_dynamics": run_market_dynamics,
    "shock_response": run_shock_response,
    "reputation": run_reputation,
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
