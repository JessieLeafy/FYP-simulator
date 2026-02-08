#!/usr/bin/env python3
"""Parameter sweep: run a grid of configs and aggregate results."""
from __future__ import annotations

import argparse
import copy
import csv
import json
import os
import sys
import time
from itertools import product

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.core.config import SimulationConfig, load_config  # noqa: E402
from src.core.rng import SeededRNG  # noqa: E402
from src.market.simulator import MarketSimulator  # noqa: E402


def main() -> None:
    p = argparse.ArgumentParser(description="Run a parameter sweep.")
    p.add_argument("--config", type=str, required=True,
                   help="Base YAML config file")
    p.add_argument("--seeds", type=int, nargs="+", default=[42, 123, 456])
    p.add_argument("--agent_types", type=str, nargs="+",
                   default=["rule_based"])
    p.add_argument("--max_rounds_list", type=int, nargs="+",
                   default=[5, 10, 15])
    p.add_argument("--steps", type=int, default=None,
                   help="Override steps (keep sweep fast)")
    p.add_argument("--output", type=str, default="outputs/sweep_results.csv")
    args = p.parse_args()

    base_cfg = load_config(args.config)

    grid = list(product(args.seeds, args.agent_types, args.max_rounds_list))
    all_summaries: list[dict] = []

    print(f"Sweep: {len(grid)} configurations")
    for i, (seed, agent_type, max_rounds) in enumerate(grid, 1):
        cfg = copy.deepcopy(base_cfg)
        cfg.seed = seed
        cfg.agent_type = agent_type
        cfg.negotiation.max_rounds = max_rounds
        if args.steps is not None:
            cfg.steps = args.steps

        print(
            f"  [{i}/{len(grid)}] seed={seed}  agent={agent_type}  "
            f"max_rounds={max_rounds} ...",
            end="",
            flush=True,
        )
        t0 = time.time()
        rng = SeededRNG(seed)
        sim = MarketSimulator(cfg, rng)
        sim.run()
        elapsed = time.time() - t0

        summary_path = os.path.join(sim.run_dir, "summary.json")
        with open(summary_path) as f:
            summary = json.load(f)
        summary["seed"] = seed
        summary["agent_type"] = agent_type
        summary["max_rounds"] = max_rounds
        all_summaries.append(summary)
        print(f"  {elapsed:.1f}s")

    # write aggregated CSV
    os.makedirs(os.path.dirname(os.path.abspath(args.output)), exist_ok=True)
    if all_summaries:
        with open(args.output, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=list(all_summaries[0].keys()))
            writer.writeheader()
            writer.writerows(all_summaries)

    print(f"\nSweep complete: {len(all_summaries)} runs → {args.output}")


if __name__ == "__main__":
    main()
