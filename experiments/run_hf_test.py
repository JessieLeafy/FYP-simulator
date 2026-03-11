#!/usr/bin/env python3
"""Run a single free-language negotiation session using the real simulator pipeline.

Uses HuggingFace backend instead of Ollama — everything else (prompts, parsing,
session logic, settlement, logging) is identical to the real experiments.

Usage:
    CUDA_VISIBLE_DEVICES=0,1 python experiments/run_hf_test.py \
        --config experiments/configs/free_language_hf_test.yaml \
        --model Qwen/Qwen2.5-7B-Instruct \
        --device cuda:0

    # Defaults to the config values if --model / --device are omitted.
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

# ensure project root is on sys.path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.core.config import load_config
from src.core.rng import SeededRNG
from src.market.simulator import MarketSimulator


def main():
    parser = argparse.ArgumentParser(
        description="Single-session free-language HF test (real simulator pipeline)",
    )
    parser.add_argument(
        "--config", required=True,
        help="Path to YAML config file",
    )
    parser.add_argument(
        "--model", default=None,
        help="Override HuggingFace model ID (e.g. Qwen/Qwen2.5-7B-Instruct)",
    )
    parser.add_argument(
        "--device", default=None,
        help="Override device (e.g. cuda:0, cuda:1, auto)",
    )
    parser.add_argument(
        "--temperature", type=float, default=None,
        help="Override temperature",
    )
    parser.add_argument(
        "--max-rounds", type=int, default=None,
        help="Override max negotiation rounds",
    )
    parser.add_argument(
        "--seed", type=int, default=None,
        help="Override random seed",
    )
    parser.add_argument(
        "--verbose", "-v", action="store_true",
        help="Enable debug logging",
    )
    args = parser.parse_args()

    # Logging
    level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(name)s %(levelname)s: %(message)s",
        datefmt="%H:%M:%S",
    )

    # Load config
    cfg = load_config(args.config)

    # CLI overrides
    if args.model:
        cfg.llm.model = args.model
    if args.device:
        cfg.llm.device = args.device
    if args.temperature is not None:
        cfg.llm.temperature = args.temperature
    if args.max_rounds is not None:
        cfg.negotiation.max_rounds = args.max_rounds
    if args.seed is not None:
        cfg.seed = args.seed

    # Force HuggingFace backend
    cfg.llm.backend = "huggingface"

    # Print session info
    print(f"\n{'='*70}")
    print(f"  FREE-LANGUAGE SESSION (real simulator pipeline)")
    print(f"  Model:  {cfg.llm.model}")
    print(f"  Device: {cfg.llm.device}")
    print(f"  Temp:   {cfg.llm.temperature}")
    print(f"  Rounds: {cfg.negotiation.max_rounds}")
    print(f"  Gate:   {'ON' if cfg.negotiation.gate_enabled else 'OFF'}")
    print(f"  Seed:   {cfg.seed}")
    print(f"  Mode:   {cfg.prompt.negotiation_mode}")
    print(f"{'='*70}\n")

    # Run
    rng = SeededRNG(cfg.seed)
    sim = MarketSimulator(cfg, rng)

    def on_session(result):
        status = "DEAL" if result.deal_made else "NO DEAL"
        price = f"${result.deal_price:.2f}" if result.deal_price else "N/A"
        print(f"\n  Result: {status} | Price: {price} | Rounds: {result.rounds_taken}")
        if result.deal_made and result.deal_price:
            print(f"  Buyer surplus:  ${result.buyer_surplus:.2f}")
            print(f"  Seller surplus: ${result.seller_surplus:.2f}")

    results = sim.run(on_session=on_session)

    # Print output location
    print(f"\n  Output dir: {sim.run_dir}")
    print(f"  Log file:   {sim.run_dir}/events.jsonl")
    print(f"{'='*70}\n")


if __name__ == "__main__":
    main()
