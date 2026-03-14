#!/usr/bin/env python3
"""Run shock-response × anchor-mode ablation experiment.

Tests whether weak price response to supply/demand shocks is caused by
the fixed prompt-level reference price anchor.

Usage:
    # Full run (fixed + updated anchor modes, 3 seeds)
    python experiments/run_shock_anchor_ablation.py

    # Pilot (1 seed, reduced scale)
    python experiments/run_shock_anchor_ablation.py --pilot

    # Include no_anchor condition
    python experiments/run_shock_anchor_ablation.py --anchor-modes fixed,updated,no_anchor

    # Single seed
    python experiments/run_shock_anchor_ablation.py --seeds 42
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.core.config import load_config  # noqa: E402
from experiments.experiments import run_shock_anchor_ablation  # noqa: E402

try:
    from tqdm import tqdm
    HAS_TQDM = True
except ImportError:
    HAS_TQDM = False


def main():
    parser = argparse.ArgumentParser(
        description="Shock-response × anchor-mode ablation",
    )
    parser.add_argument("--seeds", type=str, default="42,123,456",
                        help="Comma-separated seeds")
    parser.add_argument("--anchor-modes", type=str, default="updated",
                        help="Comma-separated anchor modes: fixed,updated,no_anchor")
    parser.add_argument("--config", type=str,
                        default="experiments/configs/exp_shock_response.yaml",
                        help="Base config YAML")
    parser.add_argument("--model", type=str, default=None)
    parser.add_argument("--backend", type=str, default=None)
    parser.add_argument("--device", type=str, default=None)
    parser.add_argument("--quantize", type=str, default=None)
    parser.add_argument("--pilot", action="store_true",
                        help="Pilot mode: 1 seed, reduced scale")
    parser.add_argument("--output-base", type=str,
                        default="outputs/experiments_free_language")
    args = parser.parse_args()

    if args.pilot:
        args.seeds = "42"

    seeds = [int(s.strip()) for s in args.seeds.split(",")]
    anchor_modes = [m.strip() for m in args.anchor_modes.split(",")]

    cfg = load_config(args.config)

    # Apply overrides
    if args.model:
        cfg.llm.model = args.model
    if args.backend:
        cfg.llm.backend = args.backend
    if args.device:
        cfg.llm.device = args.device
    if args.quantize:
        cfg.llm.quantize = args.quantize

    if args.pilot:
        cfg.steps = 3
        cfg.buyers_per_step = 5
        cfg.sellers_per_step = 5

    # Estimate sessions: anchor_modes × 2 shock conditions × seeds × steps × pairs
    n_conditions = len(anchor_modes) * 2  # shock + no_shock
    est_sessions = n_conditions * len(seeds) * cfg.steps * cfg.buyers_per_step

    mode_label = "PILOT" if args.pilot else "FULL"
    print(f"\n{'='*65}")
    print(f"  SHOCK × ANCHOR ABLATION [{mode_label}]")
    print(f"{'='*65}")
    print(f"  Config: {args.config}")
    print(f"  Seeds: {seeds}")
    print(f"  Anchor modes: {anchor_modes}")
    print(f"  Est. sessions: ~{est_sessions}")
    print()

    # Progress tracking
    completed = 0
    deals = 0
    t0 = time.time()

    if HAS_TQDM:
        bar = tqdm(total=est_sessions, desc="Shock×Anchor", unit="sess")
    else:
        bar = None

    def on_session(result):
        nonlocal completed, deals
        completed += 1
        if result.deal_made:
            deals += 1
        if bar:
            bar.set_postfix_str(f"deals={deals}", refresh=False)
            bar.update(1)

    run_dir, _ = run_shock_anchor_ablation(
        base_cfg=cfg,
        output_base=args.output_base,
        seeds=seeds,
        anchor_modes=anchor_modes,
        on_session=on_session,
    )

    if bar:
        bar.close()

    elapsed = time.time() - t0
    deal_rate = deals / completed if completed else 0

    print(f"\n  Done in {elapsed:.0f}s ({elapsed/60:.1f} min)")
    print(f"  Sessions: {completed}, Deals: {deals} ({deal_rate:.1%})")
    print(f"  Output: {run_dir}")

    # Load and display summary
    summary_path = os.path.join(run_dir, "experiment_summary.json")
    if os.path.exists(summary_path):
        with open(summary_path) as f:
            summary = json.load(f)
        cond_summ = summary.get("condition_summaries", {})
        if cond_summ:
            print(f"\n  {'Condition':<30} {'MeanPrice':>10} {'PriceStd':>10} {'Liquidity':>10}")
            print(f"  {'─'*30} {'─'*10} {'─'*10} {'─'*10}")
            for k, v in cond_summ.items():
                print(f"  {k:<30} {v['mean_price']:>10.2f} {v['price_std']:>10.2f} "
                      f"{v['avg_liquidity']:>10.4f}")

    print()


if __name__ == "__main__":
    main()
