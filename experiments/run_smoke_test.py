#!/usr/bin/env python3
"""Phase B smoke test: verify free-language pipeline end-to-end.

B2: Inspect events.jsonl for prompt_sent, raw_llm_output, parsed action
B3: Run minimal concession experiment (1 seed, 2 steps, 2 pairs)
B4: Verify concession_curves.csv has offer_price data
B5: Run minimal market-mode experiment (3 ticks, 5 pairs)
B6: Run parse diagnostics on smoke test output

Usage:
    CUDA_VISIBLE_DEVICES=0,1 python experiments/run_smoke_test.py
"""
from __future__ import annotations

import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src.core.config import load_config
from src.core.rng import SeededRNG
from src.market.simulator import MarketSimulator
from experiments.experiments import run_concession, run_market_dynamics
from src.evaluation.parse_diagnostics import (
    compute_parse_diagnostics,
    compute_diagnostics_for_experiment,
    write_parse_diagnostics,
)

OUTPUT_BASE = "outputs/smoke_test"


def step_b2_inspect_jsonl(jsonl_path: str) -> bool:
    """B2: Verify events.jsonl has prompt_sent and raw_llm_output."""
    print(f"\n{'='*60}")
    print("  B2: Inspect events.jsonl for prompt/response fields")
    print(f"{'='*60}")

    if not os.path.exists(jsonl_path):
        print(f"  SKIP: {jsonl_path} not found (run hf_test first)")
        return False

    turns_with_prompt = 0
    turns_with_raw = 0
    total_turns = 0
    sample_prompt = None
    sample_response = None

    with open(jsonl_path) as f:
        for line in f:
            event = json.loads(line.strip())
            if event.get("event") != "turn":
                continue
            total_turns += 1
            if event.get("prompt_sent"):
                turns_with_prompt += 1
                if sample_prompt is None:
                    sample_prompt = event["prompt_sent"]
            if event.get("raw_llm_output"):
                turns_with_raw += 1
                if sample_response is None:
                    sample_response = event["raw_llm_output"]

    print(f"  Total turns: {total_turns}")
    print(f"  With prompt_sent: {turns_with_prompt}")
    print(f"  With raw_llm_output: {turns_with_raw}")

    if sample_prompt:
        print(f"\n  --- Sample prompt (first 500 chars) ---")
        print(f"  {sample_prompt[:500]}")
    if sample_response:
        print(f"\n  --- Sample LLM response (first 500 chars) ---")
        print(f"  {sample_response[:500]}")

    ok = turns_with_prompt > 0 and turns_with_raw > 0
    print(f"\n  B2 {'PASS' if ok else 'FAIL'}: "
          f"prompt_sent={turns_with_prompt}/{total_turns}, "
          f"raw_llm_output={turns_with_raw}/{total_turns}")
    return ok


def step_b3_b4_concession() -> str | None:
    """B3-B4: Run minimal concession experiment, verify CSV output."""
    print(f"\n{'='*60}")
    print("  B3-B4: Minimal concession experiment")
    print(f"{'='*60}")

    cfg = load_config("experiments/configs/exp_concession.yaml")
    # Shrink to minimal size
    cfg.steps = 2
    cfg.buyers_per_step = 2
    cfg.sellers_per_step = 2

    conditions = {
        "rule_based": {"agent_type": "rule_based"},
        "llm_free_language": {"agent_type": "llm_free_language"},
    }

    def on_session(result):
        status = "DEAL" if result.deal_made else "NO DEAL"
        price = f"${result.deal_price:.2f}" if result.deal_price else "N/A"
        print(f"    {result.buyer_id} vs {result.seller_id}: "
              f"{status} @ {price} (round {result.rounds_taken})")

    print("  Running concession: 2 conditions × 1 seed × 2 steps × 2 pairs = 8 sessions")
    run_dir = run_concession(
        cfg,
        output_base=OUTPUT_BASE,
        seeds=[42],
        conditions=conditions,
        on_session=on_session,
    )
    print(f"  Output: {run_dir}")

    # B4: Check CSV
    csv_path = os.path.join(run_dir, "concession_curves.csv")
    if os.path.exists(csv_path):
        with open(csv_path) as f:
            lines = f.readlines()
        print(f"\n  B4: concession_curves.csv has {len(lines)-1} data rows")
        # Check for llm_free_language offer_price
        llm_rows = [l for l in lines[1:] if "llm_free_language" in l]
        print(f"  LLM free-language rows: {len(llm_rows)}")
        if llm_rows:
            print(f"  Sample: {llm_rows[0].strip()}")
            print(f"  B4 PASS: offer_price data present for free-language")
        else:
            print(f"  B4 FAIL: no free-language offer_price rows")
    else:
        print(f"  B4 FAIL: {csv_path} not found")

    return run_dir


def step_b5_market_mode() -> str | None:
    """B5: Run minimal market-mode experiment, verify tick_stats."""
    print(f"\n{'='*60}")
    print("  B5: Minimal market-mode experiment")
    print(f"{'='*60}")

    cfg = load_config("experiments/configs/exp_market_dynamics.yaml")
    # Shrink to minimal size
    cfg.steps = 3
    cfg.buyers_per_step = 5
    cfg.sellers_per_step = 5

    def on_session(result):
        status = "DEAL" if result.deal_made else "NO DEAL"
        price = f"${result.deal_price:.2f}" if result.deal_price else "N/A"
        print(f"    {status} @ {price} (round {result.rounds_taken})")

    print("  Running market dynamics: 3 ticks × 5 pairs = 15 sessions")
    run_dir = run_market_dynamics(
        cfg,
        output_base=OUTPUT_BASE,
        seeds=[42],
        on_session=on_session,
    )
    print(f"  Output: {run_dir}")

    # Check tick stats
    tick_csv = os.path.join(run_dir, "tick_stats.csv")
    if os.path.exists(tick_csv):
        with open(tick_csv) as f:
            lines = f.readlines()
        print(f"  tick_stats.csv: {len(lines)-1} ticks")
        print(f"  B5 PASS: tick_stats generated")
    else:
        print(f"  B5 WARN: tick_stats.csv not found (may be in subdirectory)")

    return run_dir


def step_b6_diagnostics(run_dirs: list[str]):
    """B6: Run parse diagnostics on smoke test outputs."""
    print(f"\n{'='*60}")
    print("  B6: Parse diagnostics")
    print(f"{'='*60}")

    for run_dir in run_dirs:
        if run_dir is None:
            continue
        print(f"\n  Analyzing: {run_dir}")
        diag = compute_diagnostics_for_experiment(run_dir)
        write_parse_diagnostics(diag, run_dir)

        print(f"  Files processed: {diag.get('files_processed', 0)}")
        print(f"  Total turns: {diag.get('total_turns', 0)}")
        print(f"  Total LLM turns: {diag.get('total_llm_turns', 0)}")
        print(f"  Total sessions: {diag.get('total_sessions', 0)}")
        print(f"  Parse success rate: {diag.get('parse_success_rate', 0):.1%}")
        print(f"  Retry rate: {diag.get('retry_rate', 0):.1%}")
        print(f"  Reject from parse: {diag.get('reject_from_parse_count', 0)}")
        print(f"  Deal rate: {diag.get('deal_rate', 0):.1%}")
        print(f"  Timeout rate: {diag.get('timeout_rate', 0):.1%}")
        print(f"  Mean response length: {diag.get('mean_response_length', 0):.0f} chars")
        print(f"  Accept+price conflicts: {diag.get('accept_price_conflict_count', 0)}")
        print(f"  Diagnostics written to: {run_dir}/parse_diagnostics.json")


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Phase B smoke test")
    parser.add_argument("--skip-b2", action="store_true",
                        help="Skip B2 (inspect existing JSONL)")
    parser.add_argument("--jsonl", default=None,
                        help="Path to events.jsonl for B2 (auto-detected if omitted)")
    args = parser.parse_args()

    os.makedirs(OUTPUT_BASE, exist_ok=True)

    print(f"\n{'='*60}")
    print("  PHASE B SMOKE TEST")
    print(f"{'='*60}")

    # B2: Inspect existing JSONL
    if not args.skip_b2:
        jsonl = args.jsonl
        if jsonl is None:
            # Try to find most recent hf_test output
            hf_dir = "outputs/hf_test"
            if os.path.isdir(hf_dir):
                subdirs = sorted(os.listdir(hf_dir))
                if subdirs:
                    jsonl = os.path.join(hf_dir, subdirs[-1], "events.jsonl")
        if jsonl:
            step_b2_inspect_jsonl(jsonl)
        else:
            print("\n  B2: SKIP (no JSONL found, run hf_test first)")

    # B3-B4: Concession
    concession_dir = step_b3_b4_concession()

    # B5: Market mode
    market_dir = step_b5_market_mode()

    # B6: Parse diagnostics
    step_b6_diagnostics([concession_dir, market_dir])

    print(f"\n{'='*60}")
    print("  PHASE B COMPLETE")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    main()
