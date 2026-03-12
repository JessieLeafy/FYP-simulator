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
        "held": True,  # ZOPA confound — needs redesign before rerun
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


def _apply_pilot_overrides(cfg):
    """Reduce scale for pilot runs.

    Session-mode (A, B, C): 2 steps × 3 pairs = 6 sessions/condition/seed
    Market-mode  (D, E, H, I): 3 ticks × 5 pairs = 15 sessions/condition/seed
    """
    if getattr(cfg, "mode", "session") == "market":
        cfg.steps = 3
        cfg.buyers_per_step = 5
        cfg.sellers_per_step = 5
    else:
        cfg.steps = 2
        cfg.buyers_per_step = 3
        cfg.sellers_per_step = 3


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

def run_exp_a(cfg, output_base, seeds, on_session, backend=None):
    """A: Concession — rule_based baseline + llm_free_language treatment."""
    conditions = {
        "rule_based": {"agent_type": "rule_based"},
        "llm_free_language": {"agent_type": "llm_free_language"},
    }
    return run_concession(cfg, output_base=output_base, seeds=seeds,
                          conditions=conditions, on_session=on_session,
                          backend=backend)


def run_exp_b(cfg, output_base, seeds, on_session, backend=None):
    """B: Anchoring — 3 buyer-value conditions (set in experiments.py)."""
    return run_anchoring(cfg, output_base=output_base, seeds=seeds,
                         on_session=on_session, backend=backend)


def run_exp_c(cfg, output_base, seeds, on_session, backend=None):
    """C: Deadline — 3 max_rounds conditions (experiment design)."""
    max_rounds = [6, 12, 20]
    return run_deadline(cfg, output_base=output_base, seeds=seeds,
                        max_rounds_list=max_rounds, on_session=on_session,
                        backend=backend)


def run_exp_d(cfg, output_base, seeds, on_session, backend=None):
    """D: Market Dynamics — uses config as-is."""
    return run_market_dynamics(cfg, output_base=output_base, seeds=seeds,
                               on_session=on_session, backend=backend)


def run_exp_e(cfg, output_base, seeds, on_session, backend=None):
    """E: Shock Response — uses config as-is."""
    return run_shock_response(cfg, output_base=output_base, seeds=seeds,
                               on_session=on_session, backend=backend)


def run_exp_h(cfg, output_base, seeds, on_session, backend=None):
    """H: Mechanism Comparison — uses config as-is."""
    return run_mechanism(cfg, output_base=output_base, seeds=seeds,
                         on_session=on_session, backend=backend)


def run_exp_i(cfg, output_base, seeds, on_session, backend=None):
    """I: Supply-Demand — uses config as-is."""
    return run_supply_demand(cfg, output_base=output_base, seeds=seeds,
                              on_session=on_session, backend=backend)


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

    if cfg is not None:
        steps = cfg.steps
        pairs = cfg.buyers_per_step
        n_conds = {"A": 2, "B": 3, "C": 3, "D": 1, "E": 2, "H": 2, "I": 3}
        return n_conds.get(key, 1) * n_seeds * steps * pairs

    # Defaults match production YAML configs (Phase D, revised 2026-03-12)
    estimates = {
        "A": 2 * n_seeds * 3 * 8,        #  144  (2 conds x seeds x 3 steps x 8 pairs)
        "B": 3 * n_seeds * 3 * 8,        #  216  (3 anchor conds)
        "C": 3 * n_seeds * 3 * 8,        #  216  (3 max_rounds conds)
        "D": 1 * n_seeds * 10 * 10,      #  300  (1 cond x 10 ticks x 10 pairs)
        "E": 2 * n_seeds * 10 * 10,      #  600  (2 shock conds)
        "H": 2 * n_seeds * 8 * 8,        #  384  (2 matchers x 8 ticks x 8 pairs)
        "I": 3 * n_seeds * 8 * 8,        #  576  (3 supply/demand conds)
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
    parser.add_argument("--pilot", action="store_true",
                        help="Pilot mode: 1 seed, reduced steps/pairs for quick validation")
    parser.add_argument("--output-base", type=str,
                        default="outputs/experiments_free_language")
    args = parser.parse_args()

    if args.pilot:
        args.seeds = "42"
        if args.output_base == "outputs/experiments_free_language":
            args.output_base = "outputs/pilot_free_language"

    seeds = [int(s.strip()) for s in args.seeds.split(",")]

    # Determine which experiments to run
    if args.only:
        keys = [k.strip().upper() for k in args.only.split(",")]
        for k in keys:
            if k not in EXPERIMENT_DEFS:
                print(f"Unknown experiment: {k}. Available: {list(EXPERIMENT_DEFS.keys())}")
                sys.exit(1)
    else:
        keys = sorted(
            [k for k, v in EXPERIMENT_DEFS.items() if not v.get("held")],
            key=lambda k: EXPERIMENT_DEFS[k]["priority"],
        )

    # Estimate total sessions
    if args.pilot:
        # Pre-compute from pilot overrides
        n_conds = {"A": 2, "B": 3, "C": 3, "D": 1, "E": 2, "H": 2, "I": 3}
        total_est = 0
        for k in keys:
            spec = EXPERIMENT_DEFS[k]
            _cfg = load_config(spec["config"])
            _apply_pilot_overrides(_cfg)
            total_est += n_conds.get(k, 1) * len(seeds) * _cfg.steps * _cfg.buyers_per_step
    else:
        total_est = sum(estimate_sessions(k, seeds) for k in keys)

    mode_label = "PILOT" if args.pilot else "FULL"
    print(f"\n{'='*65}")
    print(f"  FREE-LANGUAGE EXPERIMENTS [{mode_label}]")
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
    shared_backend = None  # reuse single model across all experiments

    for key in keys:
        spec = EXPERIMENT_DEFS[key]
        cfg = load_config(spec["config"])
        _apply_model_overrides(cfg, args)
        if args.pilot:
            _apply_pilot_overrides(cfg)

        est = estimate_sessions(key, seeds, cfg) if args.pilot else estimate_sessions(key, seeds)
        label = f"Exp {key}: {spec['name']}"
        tracker = ProgressTracker(est, label)

        def on_session(result, _t=tracker):
            _t.update(result)

        runner = EXP_RUNNERS[key]

        exp_t0 = time.time()
        try:
            run_dir, shared_backend = runner(
                cfg=cfg, output_base=args.output_base,
                seeds=seeds, on_session=on_session,
                backend=shared_backend)
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
            "pilot": args.pilot,
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
