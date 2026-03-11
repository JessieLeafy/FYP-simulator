#!/usr/bin/env python3
"""Gate ablation experiment: gate_enabled=True vs gate_enabled=False.

Runs identical bilateral negotiations under both conditions across
multiple seeds, then parses JSONL event logs to produce a detailed
metrics comparison including acceptance-source breakdown.

No simulator code is modified — only the gate_enabled config flag differs.
"""
from __future__ import annotations

import copy
import json
import os
import sys
import time
from collections import defaultdict
from typing import Any

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.core.config import SimulationConfig, load_config
from src.core.rng import SeededRNG
from src.market.simulator import MarketSimulator


def run_condition(
    config_path: str,
    seeds: list[int],
    output_base: str,
    condition_name: str,
) -> list[str]:
    """Run all seeds for one condition, return list of run_dirs."""
    run_dirs = []
    for seed in seeds:
        cfg = load_config(config_path)
        cfg.seed = seed
        cfg.output_dir = os.path.join(output_base, condition_name, f"seed_{seed}")

        rng = SeededRNG(cfg.seed)
        sim = MarketSimulator(cfg, rng)

        print(f"  [{condition_name}] seed={seed} starting...")
        t0 = time.time()
        sim.run()
        elapsed = time.time() - t0
        print(f"  [{condition_name}] seed={seed} done in {elapsed:.1f}s → {sim.run_dir}")
        run_dirs.append(sim.run_dir)
    return run_dirs


def parse_events(run_dirs: list[str]) -> dict[str, Any]:
    """Parse JSONL event logs from multiple run_dirs into aggregate metrics."""
    results = []  # result events
    turns = []    # turn events
    risks = []    # risk events

    for run_dir in run_dirs:
        events_path = os.path.join(run_dir, "events.jsonl")
        if not os.path.exists(events_path):
            print(f"  WARNING: {events_path} not found")
            continue
        with open(events_path) as f:
            for line in f:
                ev = json.loads(line.strip())
                if ev["event"] == "result":
                    results.append(ev)
                elif ev["event"] == "turn":
                    turns.append(ev)
                elif ev["event"] == "risk":
                    risks.append(ev)

    total = len(results)
    if total == 0:
        return {"total_sessions": 0, "error": "no results found"}

    deals = [r for r in results if r["deal_made"]]
    timeouts = [r for r in results if r["termination"] == "timeout"]
    rejects = [r for r in results if r["termination"] == "rejected"]

    deal_prices = [r["deal_price"] for r in deals]
    deal_rounds = [r["rounds_taken"] for r in deals]
    buyer_surpluses = [r["buyer_surplus"] for r in deals]
    seller_surpluses = [r["seller_surplus"] for r in deals]

    # Acceptance source breakdown from turn events
    # Categories:
    #   pre_llm_gate: llm_action="skipped", override_flag=True
    #   post_llm_override: override_flag=True, llm_action != "skipped"
    #   llm_accept: effective_action="accept", override_flag=False, llm_action="accept"
    #   fallback_accept: effective_action="accept", and rationale contains "Fallback"
    #     (we can't easily detect this from turns alone, but we can infer from llm_action)

    accept_turns = [t for t in turns if t.get("effective_action") == "accept"]
    pre_llm_gate = 0
    post_llm_override = 0
    llm_accept = 0
    other_accept = 0

    for t in accept_turns:
        if t.get("llm_action") == "skipped" and t.get("override_flag"):
            pre_llm_gate += 1
        elif t.get("override_flag") and t.get("llm_action") != "skipped":
            post_llm_override += 1
        elif not t.get("override_flag") and t.get("llm_action") == "accept":
            llm_accept += 1
        else:
            other_accept += 1

    # Count reject actions from turns (not termination-level)
    reject_turns = [t for t in turns if t.get("effective_action") == "reject"]

    # Count invalid actions (risk events)
    invalid_count = len(risks)

    # Parser fallback detection: look for "Fallback" in message_public or offer patterns
    # The fallback produces messages like "I propose $X.XX." — hard to distinguish.
    # Better: count turns where llm_action differs from effective_action but isn't an override
    # Actually, fallback is invisible in logs. Let's count LLM calls that hit fallback
    # by looking for turns with action but no override, where the message hints at fallback.
    fallback_turns = [
        t for t in turns
        if t.get("message_public", "").startswith("I propose $")
        and "Fallback" not in t.get("override_reason", "")
        and t.get("llm_action") not in ("skipped",)
    ]
    # More reliable: count turns where llm_action is not in standard set
    # Actually let's just count the "I accept your offer." with llm_action != "accept"
    # and not an override — these are fallback accepts
    fallback_accepts = [
        t for t in accept_turns
        if not t.get("override_flag")
        and t.get("llm_action") != "accept"
        and t.get("llm_action") != "skipped"
    ]

    # First-offer settlements: deals that settled on round 1
    # (buyer offers on round 0, seller accepts/gate on round 1)
    first_offer_deals = [r for r in deals if r["rounds_taken"] <= 2]

    def safe_mean(lst):
        return sum(lst) / len(lst) if lst else 0.0

    def safe_std(lst):
        if len(lst) < 2:
            return 0.0
        m = safe_mean(lst)
        return (sum((x - m) ** 2 for x in lst) / len(lst)) ** 0.5

    return {
        "total_sessions": total,
        "deals_made": len(deals),
        "agreement_rate": round(len(deals) / total, 4),
        "timeout_count": len(timeouts),
        "timeout_rate": round(len(timeouts) / total, 4),
        "reject_count": len(rejects),
        "reject_rate": round(len(rejects) / total, 4),
        "avg_rounds_to_agreement": round(safe_mean(deal_rounds), 2),
        "avg_deal_price": round(safe_mean(deal_prices), 2),
        "std_deal_price": round(safe_std(deal_prices), 2),
        "avg_buyer_surplus": round(safe_mean(buyer_surpluses), 2),
        "avg_seller_surplus": round(safe_mean(seller_surpluses), 2),
        "first_offer_settlements": len(first_offer_deals),
        "first_offer_rate": round(len(first_offer_deals) / total, 4) if total else 0,
        "invalid_action_count": invalid_count,
        "invalid_action_rate": round(invalid_count / len(turns), 4) if turns else 0,
        "total_turns": len(turns),
        "total_accept_turns": len(accept_turns),
        "total_reject_turns": len(reject_turns),
        "acceptance_source": {
            "pre_llm_gate": pre_llm_gate,
            "post_llm_override": post_llm_override,
            "llm_accept": llm_accept,
            "fallback_accept": len(fallback_accepts),
            "other_accept": other_accept - len(fallback_accepts),
        },
    }


def print_comparison(gate_on: dict, gate_off: dict) -> None:
    """Print a formatted comparison table."""
    print("\n" + "=" * 72)
    print("GATE ABLATION RESULTS")
    print("=" * 72)

    rows = [
        ("Total sessions", "total_sessions"),
        ("Deals made", "deals_made"),
        ("Agreement rate", "agreement_rate"),
        ("Timeout count", "timeout_count"),
        ("Timeout rate", "timeout_rate"),
        ("Reject count", "reject_count"),
        ("Reject rate", "reject_rate"),
        ("Avg rounds to agreement", "avg_rounds_to_agreement"),
        ("Avg deal price", "avg_deal_price"),
        ("Std deal price", "std_deal_price"),
        ("Avg buyer surplus", "avg_buyer_surplus"),
        ("Avg seller surplus", "avg_seller_surplus"),
        ("First-offer settlements", "first_offer_settlements"),
        ("First-offer rate", "first_offer_rate"),
        ("Invalid action count", "invalid_action_count"),
        ("Invalid action rate", "invalid_action_rate"),
        ("Total turns", "total_turns"),
    ]

    print(f"\n{'Metric':<30} {'Gate ON':>12} {'Gate OFF':>12} {'Δ':>10}")
    print("-" * 64)
    for label, key in rows:
        von = gate_on.get(key, 0)
        voff = gate_off.get(key, 0)
        if isinstance(von, float):
            delta = voff - von
            print(f"{label:<30} {von:>12.4f} {voff:>12.4f} {delta:>+10.4f}")
        else:
            delta = voff - von
            print(f"{label:<30} {von:>12} {voff:>12} {delta:>+10}")

    print(f"\n{'Acceptance source breakdown':}")
    print(f"{'Source':<25} {'Gate ON':>12} {'Gate OFF':>12}")
    print("-" * 49)
    for src in ["pre_llm_gate", "post_llm_override", "llm_accept", "fallback_accept", "other_accept"]:
        von = gate_on.get("acceptance_source", {}).get(src, 0)
        voff = gate_off.get("acceptance_source", {}).get(src, 0)
        print(f"{src:<25} {von:>12} {voff:>12}")

    print("=" * 72)


def main():
    seeds = [42, 123, 456]
    output_base = "outputs/experiments/gate_ablation"
    ts = time.strftime("%Y%m%d_%H%M%S")
    run_base = os.path.join(output_base, f"run_{ts}")
    os.makedirs(run_base, exist_ok=True)

    config_dir = os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "configs"
    )

    print("=" * 60)
    print("GATE ABLATION EXPERIMENT")
    print(f"Seeds: {seeds}")
    print(f"Output: {run_base}")
    print("=" * 60)

    # Run gate_on condition
    print("\n--- Condition: gate_on (gate_enabled=True) ---")
    t0 = time.time()
    on_dirs = run_condition(
        os.path.join(config_dir, "gate_ablation_on.yaml"),
        seeds, run_base, "gate_on",
    )
    on_time = time.time() - t0
    print(f"gate_on total time: {on_time:.1f}s")

    # Run gate_off condition
    print("\n--- Condition: gate_off (gate_enabled=False) ---")
    t0 = time.time()
    off_dirs = run_condition(
        os.path.join(config_dir, "gate_ablation_off.yaml"),
        seeds, run_base, "gate_off",
    )
    off_time = time.time() - t0
    print(f"gate_off total time: {off_time:.1f}s")

    # Parse and compare
    gate_on_metrics = parse_events(on_dirs)
    gate_off_metrics = parse_events(off_dirs)

    print_comparison(gate_on_metrics, gate_off_metrics)

    # Save raw metrics
    output = {
        "experiment": "gate_ablation",
        "seeds": seeds,
        "config_on": "gate_ablation_on.yaml",
        "config_off": "gate_ablation_off.yaml",
        "gate_on_run_dirs": on_dirs,
        "gate_off_run_dirs": off_dirs,
        "gate_on_time_sec": round(on_time, 1),
        "gate_off_time_sec": round(off_time, 1),
        "gate_on": gate_on_metrics,
        "gate_off": gate_off_metrics,
    }
    out_path = os.path.join(run_base, "gate_ablation_results.json")
    with open(out_path, "w") as f:
        json.dump(output, f, indent=2)
    print(f"\nRaw results saved to: {out_path}")


if __name__ == "__main__":
    main()
