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

from src.core.config import SimulationConfig, load_config, resolve_fixed_params  # noqa: E402
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
    p.add_argument("--num_buyers", type=int, default=None,
                   help="Alias for --buyers_per_step")
    p.add_argument("--num_sellers", type=int, default=None,
                   help="Alias for --sellers_per_step")
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
    p.add_argument("--scenario_mode", type=str, default=None,
                   choices=["distribution", "fixed"],
                   help="Parameter generation mode")
    # ── new flags ─────────────────────────────────────────────────────────
    p.add_argument("--mode", type=str, default=None,
                   choices=["session", "market"],
                   help="Simulation mode (session=legacy, market=with tick stats)")
    p.add_argument("--ticks", type=int, default=None,
                   help="Number of market ticks (alias for --steps in market mode)")
    p.add_argument("--matching", type=str, default=None,
                   choices=["random"],
                   help="Matching strategy")
    p.add_argument("--log_path", type=str, default=None,
                   help="Custom JSONL log path (default: <run_dir>/events.jsonl)")
    return p


def _apply_overrides(cfg: SimulationConfig, args: argparse.Namespace) -> None:
    """Mutate *cfg* in-place with any non-None CLI overrides."""
    if args.seed is not None:
        cfg.seed = args.seed
    if args.steps is not None:
        cfg.steps = args.steps
    if args.ticks is not None:
        cfg.steps = args.ticks
    if args.buyers_per_step is not None:
        cfg.buyers_per_step = args.buyers_per_step
    if args.num_buyers is not None:
        cfg.buyers_per_step = args.num_buyers
    if args.sellers_per_step is not None:
        cfg.sellers_per_step = args.sellers_per_step
    if args.num_sellers is not None:
        cfg.sellers_per_step = args.num_sellers
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
    if args.scenario_mode is not None:
        cfg.scenario_mode = args.scenario_mode
    if args.mode is not None:
        cfg.mode = args.mode
    if args.matching is not None:
        cfg.matching = args.matching


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

    mode_label = f"mode={cfg.mode}" if cfg.mode == "market" else ""
    print(
        f"Starting simulation: agent_type={cfg.agent_type}  "
        f"steps={cfg.steps}  pairs/step={min(cfg.buyers_per_step, cfg.sellers_per_step)}  "
        f"seed={cfg.seed}  scenario_mode={cfg.scenario_mode}"
        + (f"  {mode_label}" if mode_label else "")
    )
    if cfg.scenario_mode == "fixed":
        fp = resolve_fixed_params(cfg)
        parts = [f"{k}={v}" for k, v in fp.items() if k != "selection"]
        print(f"Fixed params: {', '.join(parts)}  (selection={fp.get('selection', 'cycle')})")
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

    # market mode: print tick summary
    if cfg.mode == "market" and sim.tick_stats:
        print(f"Market ticks: {len(sim.tick_stats)}")
        for ts in sim.tick_stats:
            print(
                f"  tick {ts.tick}: {ts.deals_made}/{ts.num_sessions} deals  "
                f"avg=${ts.mean_price:.2f}  liquidity={ts.liquidity:.2f}"
            )

    print(f"Results → {sim.run_dir}")


if __name__ == "__main__":
    main()
