#!/usr/bin/env python3
"""Run ALL experiments with free-language agent + gate-off.

All experiment parameters (agent type, steps, pairs, model, gate) are
set in the YAML configs under experiments/configs/.  This runner just
loads the config, applies optional CLI overrides, and calls the
experiment function.

Usage:
    # Full run (3 seeds, all experiments)
    python experiments/run_free_language_all.py

    # Single experiment
    python experiments/run_free_language_all.py --only A

    # Pilot with 1 seed
    python experiments/run_free_language_all.py --seeds 42

    # Override backend (model is already in YAML)
    python experiments/run_free_language_all.py --backend huggingface

    # Override model at runtime
    python experiments/run_free_language_all.py --model Qwen/Qwen2.5-14B-Instruct --backend huggingface
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.core.config import load_config  # noqa: E402
from experiments.experiments import (  # noqa: E402
    run_concession,
    run_anchoring,
    run_deadline,
    run_market_dynamics,
    run_shock_response,
    run_mechanism,
    run_supply_demand,
)
from src.evaluation.parse_diagnostics import (  # noqa: E402
    compute_diagnostics_for_experiment,
    write_parse_diagnostics,
)

try:
    from tqdm import tqdm
    HAS_TQDM = True
except ImportError:
    HAS_TQDM = False


# Experiment definitions
EXPERIMENT_DEFS = {
    "A": {
        "name": "Concession Curves",
        "config": "experiments/configs/exp_concession.yaml",
        "priority": 1,
    },
    "C": {
        "name": "Deadline Pressure",
        "config": "experiments/configs/exp_deadline.yaml",
        "priority": 2,
    },
    "B": {
        "name": "Anchoring Effect",
        "config": "experiments/configs/exp_anchoring.yaml",
        "priority": 3,
    },
    "H": {
        "name": "Mechanism Comparison",
        "config": "experiments/configs/exp_mechanism.yaml",
        "priority": 4,
    },
    "I": {
        "name": "Supply-Demand Structure",
        "config": "experiments/configs/exp_supply_demand.yaml",
        "priority": 5,
    },
    "D": {
        "name": "Market Dynamics",
        "config": "experiments/configs/exp_market_dynamics.yaml",
        "priority": 6,
    },
    "E": {
        "name": "Shock Response",
        "config": "experiments/configs/exp_shock_response.yaml",
        "priority": 7,
    },
}


def _apply_model_overrides(cfg, args):
    """Apply model/backend overrides from CLI args."""
    if args.model:
        cfg.llm.model = args.model
    if args.backend:
        cfg.llm.backend = args.backend
    if args.device:
        cfg.llm.device = args.device
    if args.temperature is not None:
        cfg.llm.temperature = args.temperature
    if args.max_tokens is not None:
        cfg.llm.max_tokens = args.max_tokens
    if args.quantize:
        cfg.llm.quantize = args.quantize


class ProgressTracker:
    def __init__(self, total_sessions: int, label: str = ""):
        self.total = total_sessions
        self.completed = 0
        self.deals = 0
        self.start_time = time.time()

        if HAS_TQDM:
            self.bar = tqdm(
                total=total_sessions, desc=label, unit="sess",
                bar_format=(
                    "{l_bar}{bar}| {n_fmt}/{total_fmt} "
                    "[{elapsed}<{remaining}, {rate_fmt}] {postfix}"
                ),
                dynamic_ncols=True,
            )
        else:
            self.bar = None
            print(f"  {label}: 0/{total_sessions} sessions", end="", flush=True)

    def update(self, result=None):
        self.completed += 1
        if result is not None and result.deal_made:
            self.deals += 1
        if self.bar:
            rate = self.deals / self.completed if self.completed else 0
            self.bar.set_postfix_str(f"deals={self.deals} ({rate:.0%})", refresh=False)
            self.bar.update(1)
        else:
            elapsed = time.time() - self.start_time
            avg = elapsed / self.completed
            remaining = avg * (self.total - self.completed)
            pct = self.completed / self.total * 100
            print(
                f"\r  [{pct:5.1f}%] {self.completed}/{self.total} "
                f"[{elapsed:.0f}s, ~{remaining:.0f}s left, deals={self.deals}]",
                end="", flush=True,
            )

    def close(self):
        elapsed = time.time() - self.start_time
        if self.bar:
            self.bar.close()
        else:
            print()
        return elapsed


# ── Experiment runners ────────────────────────────────────────────────────
# Each function only applies condition-level overrides that are part of
# the experiment design.  All base parameters (agent_type, steps, pairs,
# model, gate, etc.) come from the YAML config — no silent overrides.

def run_exp_a(cfg, output_base, seeds, on_session):
    """A: Concession — rule_based baseline + llm_free_language treatment."""
    # Conditions override agent_type per arm (experiment design)
    conditions = {
        "rule_based": {"agent_type": "rule_based"},
        "llm_free_language": {"agent_type": "llm_free_language"},
    }
    return run_concession(cfg, output_base=output_base, seeds=seeds,
                          conditions=conditions, on_session=on_session)


def run_exp_b(cfg, output_base, seeds, on_session):
    """B: Anchoring — 3 buyer-value conditions (set in experiments.py)."""
    return run_anchoring(cfg, output_base=output_base, seeds=seeds,
                         on_session=on_session)


def run_exp_c(cfg, output_base, seeds, on_session):
    """C: Deadline — 3 max_rounds conditions (experiment design)."""
    max_rounds = [6, 12, 20]
    return run_deadline(cfg, output_base=output_base, seeds=seeds,
                        max_rounds_list=max_rounds, on_session=on_session)


def run_exp_d(cfg, output_base, seeds, on_session):
    """D: Market Dynamics — uses config as-is."""
    return run_market_dynamics(cfg, output_base=output_base, seeds=seeds,
                               on_session=on_session)


def run_exp_e(cfg, output_base, seeds, on_session):
    """E: Shock Response — uses config as-is."""
    return run_shock_response(cfg, output_base=output_base, seeds=seeds,
                               on_session=on_session)


def run_exp_h(cfg, output_base, seeds, on_session):
    """H: Mechanism Comparison — uses config as-is."""
    return run_mechanism(cfg, output_base=output_base, seeds=seeds,
                         on_session=on_session)


def run_exp_i(cfg, output_base, seeds, on_session):
    """I: Supply-Demand — uses config as-is."""
    return run_supply_demand(cfg, output_base=output_base, seeds=seeds,
                              on_session=on_session)


EXP_RUNNERS = {
    "A": run_exp_a,
    "B": run_exp_b,
    "C": run_exp_c,
    "D": run_exp_d,
    "E": run_exp_e,
    "H": run_exp_h,
    "I": run_exp_i,
}


def estimate_sessions(key: str, seeds: list[int], cfg=None) -> int:
    """Rough session count estimate for progress tracking.

    Uses config values when available, otherwise falls back to defaults.
    """
    n_seeds = len(seeds)
    # These match the YAML configs for production (Phase D)
    estimates = {
        "A": 2 * n_seeds * 5 * 10,       #  300  (2 conds x seeds x 5 steps x 10 pairs)
        "B": 3 * n_seeds * 5 * 10,       #  450  (3 anchor conds)
        "C": 3 * n_seeds * 5 * 10,       #  450  (3 max_rounds conds)
        "D": 1 * n_seeds * 20 * 25,      # 1500  (1 cond x 20 ticks x 25 pairs)
        "E": 2 * n_seeds * 20 * 25,      # 3000  (2 shock conds)
        "H": 2 * n_seeds * 10 * 20,      # 1200  (2 matchers x 10 ticks x 20 pairs)
        "I": 3 * n_seeds * 10 * 20,      # 1800  (3 supply/demand conds)
    }
    return estimates.get(key, 100)


def main():
    parser = argparse.ArgumentParser(description="Run free-language experiments")
    parser.add_argument("--seeds", type=str, default="42,123,456",
                        help="Comma-separated seeds (default: 42,123,456)")
    parser.add_argument("--only", type=str, default=None,
                        help="Run only these experiments (e.g. A, A,C,H)")
    parser.add_argument("--model", type=str, default=None,
                        help="LLM model name override (default: from YAML)")
    parser.add_argument("--backend", type=str, default=None,
                        help="LLM backend override: ollama or huggingface")
    parser.add_argument("--device", type=str, default=None,
                        help="GPU device for HuggingFace backend")
    parser.add_argument("--temperature", type=float, default=None)
    parser.add_argument("--max-tokens", type=int, default=None)
    parser.add_argument("--quantize", type=str, default=None,
                        help="Quantization: 4bit, 8bit, or empty")
    parser.add_argument("--output-base", type=str,
                        default="outputs/experiments_free_language")
    args = parser.parse_args()

    seeds = [int(s.strip()) for s in args.seeds.split(",")]

    # Determine which experiments to run
    if args.only:
        keys = [k.strip().upper() for k in args.only.split(",")]
        for k in keys:
            if k not in EXPERIMENT_DEFS:
                print(f"Unknown experiment: {k}. Available: {list(EXPERIMENT_DEFS.keys())}")
                sys.exit(1)
    else:
        keys = sorted(EXPERIMENT_DEFS.keys(),
                       key=lambda k: EXPERIMENT_DEFS[k]["priority"])

    total_est = sum(estimate_sessions(k, seeds) for k in keys)

    print(f"\n{'='*65}")
    print(f"  FREE-LANGUAGE EXPERIMENTS")
    print(f"{'='*65}")
    print(f"  Output: {args.output_base}")
    print(f"  Seeds: {seeds}")
    if args.model:
        print(f"  Model override: {args.model}")
    if args.backend:
        print(f"  Backend override: {args.backend}")
    print(f"  Experiments: {', '.join(keys)}")
    print(f"  Est. sessions: ~{total_est}")
    print()

    os.makedirs(args.output_base, exist_ok=True)
    t0_all = time.time()
    results_summary = {}

    for key in keys:
        spec = EXPERIMENT_DEFS[key]
        cfg = load_config(spec["config"])
        _apply_model_overrides(cfg, args)

        est = estimate_sessions(key, seeds)
        label = f"Exp {key}: {spec['name']}"
        tracker = ProgressTracker(est, label)

        def on_session(result, _t=tracker):
            _t.update(result)

        runner = EXP_RUNNERS[key]

        exp_t0 = time.time()
        try:
            run_dir = runner(cfg=cfg, output_base=args.output_base,
                             seeds=seeds, on_session=on_session)
            exp_elapsed = tracker.close()

            # Run parse diagnostics
            diag = compute_diagnostics_for_experiment(run_dir)
            write_parse_diagnostics(diag, run_dir)

            results_summary[key] = {
                "status": "OK",
                "name": spec["name"],
                "run_dir": run_dir,
                "sessions": tracker.completed,
                "deals": tracker.deals,
                "deal_rate": round(tracker.deals / tracker.completed, 4) if tracker.completed else 0,
                "elapsed_sec": round(exp_elapsed, 1),
                "parse_diagnostics": {
                    "parse_success_rate": diag.get("parse_success_rate", 0),
                    "retry_rate": diag.get("retry_rate", 0),
                    "timeout_rate": diag.get("timeout_rate", 0),
                },
            }
            print(f"  -> {run_dir}")
            print(f"     Parse success: {diag.get('parse_success_rate', 0):.1%}, "
                  f"Retry: {diag.get('retry_rate', 0):.1%}, "
                  f"Deal rate: {diag.get('deal_rate', 0):.1%}")
            print()

        except Exception as e:
            tracker.close()
            results_summary[key] = {
                "status": "FAILED",
                "name": spec["name"],
                "error": str(e),
            }
            import traceback
            traceback.print_exc()
            print()

    total_elapsed = time.time() - t0_all

    # Final summary
    print(f"\n{'='*65}")
    print(f"  FREE-LANGUAGE RUN COMPLETE — {total_elapsed:.0f}s ({total_elapsed/60:.1f} min)")
    print(f"{'='*65}")
    print(f"  {'Exp':<4} {'Status':<8} {'Sessions':>9} {'Deals':>7} "
          f"{'Rate':>7} {'Parse%':>7} {'Time':>8}")
    print(f"  {'─'*4} {'─'*8} {'─'*9} {'─'*7} {'─'*7} {'─'*7} {'─'*8}")

    for k in keys:
        r = results_summary.get(k, {})
        status = r.get("status", "?")
        sessions = r.get("sessions", 0)
        deals = r.get("deals", 0)
        rate = r.get("deal_rate", 0)
        parse_pct = r.get("parse_diagnostics", {}).get("parse_success_rate", 0)
        elapsed = r.get("elapsed_sec", 0)
        print(f"  {k:<4} {status:<8} {sessions:>9} {deals:>7} "
              f"{rate:>6.1%} {parse_pct:>6.1%} {elapsed:>7.1f}s")

    total_done = sum(r.get("sessions", 0) for r in results_summary.values())
    total_deals = sum(r.get("deals", 0) for r in results_summary.values())
    print(f"\n  Total: {total_done} sessions, {total_deals} deals")

    # Save master summary
    summary_path = os.path.join(
        args.output_base,
        f"free_language_run_{time.strftime('%Y%m%d_%H%M%S')}.json",
    )
    with open(summary_path, "w") as f:
        json.dump({
            "gate_enabled": False,
            "agent_type": "llm_free_language",
            "seeds": seeds,
            "model_override": args.model,
            "backend_override": args.backend,
            "total_elapsed_sec": round(total_elapsed, 1),
            "total_sessions": total_done,
            "total_deals": total_deals,
            "experiments": results_summary,
        }, f, indent=2)
    print(f"  Summary: {summary_path}\n")


if __name__ == "__main__":
    main()
