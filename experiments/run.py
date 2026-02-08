#!/usr/bin/env python3
"""CLI entry-point: run a single simulation from a YAML config + CLI overrides."""
from __future__ import annotations

import argparse
import json
import os
import sys
import time

# Ensure project root is importable
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.core.config import SimulationConfig, load_config  # noqa: E402
from src.core.rng import SeededRNG  # noqa: E402
from src.market.simulator import MarketSimulator  # noqa: E402


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Run a multi-agent negotiation simulation."
    )
    p.add_argument("--config", type=str, default=None,
                   help="Path to YAML config file")
    p.add_argument("--seed", type=int, default=None)
    p.add_argument("--steps", type=int, default=None)
    p.add_argument("--buyers_per_step", type=int, default=None)
    p.add_argument("--sellers_per_step", type=int, default=None)
    p.add_argument("--max_rounds", type=int, default=None)
    p.add_argument("--agent_type", type=str, default=None)
    p.add_argument("--buyer_agent_type", type=str, default=None)
    p.add_argument("--seller_agent_type", type=str, default=None)
    p.add_argument("--backend", type=str, default="ollama",
                   help="LLM backend (only 'ollama' supported)")
    p.add_argument("--ollama_model", type=str, default=None)
    p.add_argument("--temperature", type=float, default=None)
    p.add_argument("--max_tokens", type=int, default=None)
    p.add_argument("--timeout_sec", type=float, default=None)
    p.add_argument("--debug_llm", action="store_true")
    p.add_argument("--output_dir", type=str, default=None)
    return p


def _apply_overrides(cfg: SimulationConfig, args: argparse.Namespace) -> None:
    """Mutate *cfg* in-place with any non-None CLI overrides."""
    if args.seed is not None:
        cfg.seed = args.seed
    if args.steps is not None:
        cfg.steps = args.steps
    if args.buyers_per_step is not None:
        cfg.buyers_per_step = args.buyers_per_step
    if args.sellers_per_step is not None:
        cfg.sellers_per_step = args.sellers_per_step
    if args.max_rounds is not None:
        cfg.negotiation.max_rounds = args.max_rounds
    if args.agent_type is not None:
        cfg.agent_type = args.agent_type
    if args.buyer_agent_type is not None:
        cfg.buyer_agent_type = args.buyer_agent_type
    if args.seller_agent_type is not None:
        cfg.seller_agent_type = args.seller_agent_type
    if args.ollama_model is not None:
        cfg.llm.model = args.ollama_model
    if args.temperature is not None:
        cfg.llm.temperature = args.temperature
    if args.max_tokens is not None:
        cfg.llm.max_tokens = args.max_tokens
    if args.timeout_sec is not None:
        cfg.llm.timeout_sec = args.timeout_sec
    if args.debug_llm:
        cfg.llm.debug = True
    if args.output_dir is not None:
        cfg.output_dir = args.output_dir


def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()

    # load config
    if args.config:
        cfg = load_config(args.config)
    else:
        cfg = SimulationConfig()
    _apply_overrides(cfg, args)

    # run
    rng = SeededRNG(cfg.seed)
    sim = MarketSimulator(cfg, rng)

    print(
        f"Starting simulation: agent_type={cfg.agent_type}  "
        f"steps={cfg.steps}  pairs/step={min(cfg.buyers_per_step, cfg.sellers_per_step)}  "
        f"seed={cfg.seed}"
    )
    t0 = time.time()
    results = sim.run()
    elapsed = time.time() - t0

    # summary to stdout
    summary_path = os.path.join(sim.run_dir, "summary.json")
    with open(summary_path) as f:
        summary = json.load(f)

    deals = summary["deals_made"]
    total = summary["total_negotiations"]
    rate = summary["deal_success_rate"]
    avg_p = summary["avg_price"]
    print(
        f"Done in {elapsed:.1f}s  |  {total} negotiations  |  "
        f"{deals} deals ({rate:.1%})  |  avg price ${avg_p:.2f}"
    )
    print(f"Results → {sim.run_dir}")


if __name__ == "__main__":
    main()
