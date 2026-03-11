#!/usr/bin/env python3
"""Pilot runner: execute experiments A, B, C, D, E, H, I with reduced scale.

Runs all 7 experiments sequentially with a small number of sessions per
experiment, reporting per-session progress with tqdm and estimated ETA.

Usage:
    python experiments/run_pilot.py
    python experiments/run_pilot.py --scale full     # full-scale (production)
    python experiments/run_pilot.py --experiments A C H
    python experiments/run_pilot.py --dry-run         # show plan without running
"""
from __future__ import annotations

import argparse
import copy
import json
import os
import sys
import time

# Ensure project root is importable
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.core.config import load_config, SimulationConfig  # noqa: E402
from experiments.experiments import run_experiment  # noqa: E402

try:
    from tqdm import tqdm
    HAS_TQDM = True
except ImportError:
    HAS_TQDM = False


# ═══════════════════════════════════════════════════════════════════════
#  Experiment definitions: pilot vs full scale
# ═══════════════════════════════════════════════════════════════════════

EXPERIMENT_SPECS = {
    "A": {
        "name": "concession",
        "config": "experiments/configs/exp_concession.yaml",
        "pilot": {
            "seeds": [42],
            "overrides": {"steps": 2, "buyers_per_step": 5, "sellers_per_step": 5},
            # 3 conditions × 1 seed × 2 steps × 5 pairs = 30 sessions
            "est_sessions": 30,
        },
        "full": {
            "seeds": [42, 123, 456],
            "overrides": {},
            "est_sessions": 450,
        },
    },
    "B": {
        "name": "anchoring",
        "config": "experiments/configs/exp_anchoring.yaml",
        "pilot": {
            "seeds": [42],
            "overrides": {"steps": 2, "buyers_per_step": 5, "sellers_per_step": 5},
            "est_sessions": 30,
        },
        "full": {
            "seeds": [42, 123, 456],
            "overrides": {},
            "est_sessions": 450,
        },
    },
    "C": {
        "name": "deadline",
        "config": "experiments/configs/exp_deadline.yaml",
        "pilot": {
            "seeds": [42],
            "overrides": {"steps": 2, "buyers_per_step": 5, "sellers_per_step": 5},
            "est_sessions": 30,
        },
        "full": {
            "seeds": [42, 123, 456],
            "overrides": {},
            "est_sessions": 450,
        },
    },
    "D": {
        "name": "market_dynamics",
        "config": "experiments/configs/exp_market_dynamics.yaml",
        "pilot": {
            "seeds": [42],
            "overrides": {"steps": 5, "buyers_per_step": 5, "sellers_per_step": 5},
            "est_sessions": 25,
        },
        "full": {
            "seeds": [42],
            "overrides": {},
            "est_sessions": 450,
        },
    },
    "E": {
        "name": "shock_response",
        "config": "experiments/configs/exp_shock_response.yaml",
        "pilot": {
            "seeds": [42],
            "overrides": {"steps": 5, "buyers_per_step": 5, "sellers_per_step": 5},
            "est_sessions": 50,
        },
        "full": {
            "seeds": [42],
            "overrides": {},
            "est_sessions": 900,
        },
    },
    "H": {
        "name": "mechanism",
        "config": "experiments/configs/exp_mechanism.yaml",
        "pilot": {
            "seeds": [42],
            "overrides": {"steps": 5, "buyers_per_step": 5, "sellers_per_step": 5},
            "est_sessions": 50,
        },
        "full": {
            "seeds": [42, 123, 456],
            "overrides": {},
            "est_sessions": 2700,
        },
    },
    "I": {
        "name": "supply_demand",
        "config": "experiments/configs/exp_supply_demand.yaml",
        "pilot": {
            "seeds": [42],
            "overrides": {"steps": 3, "buyers_per_step": 5, "sellers_per_step": 5},
            "est_sessions": 45,
        },
        "full": {
            "seeds": [42],
            "overrides": {},
            "est_sessions": 300,
        },
    },
}


# ═══════════════════════════════════════════════════════════════════════
#  Progress tracking
# ═══════════════════════════════════════════════════════════════════════

class ProgressTracker:
    """Wraps tqdm for per-experiment and overall progress."""

    def __init__(self, total_sessions: int, experiment_label: str = ""):
        self.total = total_sessions
        self.completed = 0
        self.deals = 0
        self.start_time = time.time()

        if HAS_TQDM:
            self.bar = tqdm(
                total=total_sessions,
                desc=experiment_label,
                unit="sess",
                bar_format=(
                    "{l_bar}{bar}| {n_fmt}/{total_fmt} "
                    "[{elapsed}<{remaining}, {rate_fmt}] "
                    "{postfix}"
                ),
                dynamic_ncols=True,
            )
        else:
            self.bar = None
            print(f"  {experiment_label}: 0/{total_sessions} sessions", end="", flush=True)

    def update(self, result=None):
        self.completed += 1
        if result is not None and result.deal_made:
            self.deals += 1

        if self.bar:
            deal_rate = self.deals / self.completed if self.completed else 0
            self.bar.set_postfix_str(f"deals={self.deals} ({deal_rate:.0%})", refresh=False)
            self.bar.update(1)
        else:
            elapsed = time.time() - self.start_time
            avg = elapsed / self.completed
            remaining = avg * (self.total - self.completed)
            print(
                f"\r  {self.completed}/{self.total} sessions "
                f"[{elapsed:.0f}s elapsed, ~{remaining:.0f}s remaining, "
                f"deals={self.deals}]",
                end="", flush=True,
            )

    def close(self):
        elapsed = time.time() - self.start_time
        if self.bar:
            self.bar.close()
        else:
            print()  # newline after \r output
        return elapsed


class OverallTracker:
    """Track progress across all experiments."""

    def __init__(self, total_sessions: int):
        self.total = total_sessions
        self.completed = 0
        self.start_time = time.time()

        if HAS_TQDM:
            self.bar = tqdm(
                total=total_sessions,
                desc="Overall",
                unit="sess",
                bar_format=(
                    "{l_bar}{bar}| {n_fmt}/{total_fmt} "
                    "[{elapsed}<{remaining}, {rate_fmt}]"
                ),
                position=0,
                dynamic_ncols=True,
                colour="green",
            )
        else:
            self.bar = None

    def update(self, result=None):
        self.completed += 1
        if self.bar:
            self.bar.update(1)

    def close(self):
        if self.bar:
            self.bar.close()


# ═══════════════════════════════════════════════════════════════════════
#  Main
# ═══════════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(description="Run pilot experiments A-I (skip F, G)")
    parser.add_argument(
        "--scale", choices=["pilot", "full"], default="pilot",
        help="Scale: pilot (small, ~30min) or full (production, ~8h)",
    )
    parser.add_argument(
        "--experiments", nargs="+", default=None,
        help="Subset of experiments to run (e.g. A C H). Default: all 7",
    )
    parser.add_argument(
        "--output", default="outputs/experiments",
        help="Base output directory",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Show plan without running",
    )
    args = parser.parse_args()

    # Select experiments
    exp_keys = args.experiments or list(EXPERIMENT_SPECS.keys())
    exp_keys = [k.upper() for k in exp_keys]
    for k in exp_keys:
        if k not in EXPERIMENT_SPECS:
            print(f"Unknown experiment: {k}. Available: {list(EXPERIMENT_SPECS.keys())}")
            sys.exit(1)

    scale = args.scale

    # ── Print plan ──────────────────────────────────────────────────────
    print(f"\n{'='*65}")
    print(f"  PILOT RUN — {scale.upper()} scale")
    print(f"{'='*65}")
    print(f"  Experiments: {', '.join(exp_keys)}")
    print()

    total_sessions = 0
    plan_rows = []
    for k in exp_keys:
        spec = EXPERIMENT_SPECS[k]
        sc = spec[scale]
        seeds = sc["seeds"]
        overrides = sc["overrides"]
        est = sc["est_sessions"]
        total_sessions += est

        steps = overrides.get("steps", "default")
        pairs = overrides.get("buyers_per_step", "default")
        plan_rows.append((k, spec["name"], len(seeds), steps, pairs, est))

    print(f"  {'Exp':<4} {'Name':<18} {'Seeds':>5} {'Steps':>6} {'Pairs':>6} {'Sessions':>9}")
    print(f"  {'─'*4} {'─'*18} {'─'*5} {'─'*6} {'─'*6} {'─'*9}")
    for row in plan_rows:
        print(f"  {row[0]:<4} {row[1]:<18} {row[2]:>5} {str(row[3]):>6} {str(row[4]):>6} {row[5]:>9}")
    print(f"  {'─'*4} {'─'*18} {'─'*5} {'─'*6} {'─'*6} {'─'*9}")
    print(f"  {'':4} {'TOTAL':<18} {'':5} {'':6} {'':6} {total_sessions:>9}")

    # Estimate time (rule_based ~0.01s, LLM ~5s per session)
    # Exp A has 1/3 rule_based sessions
    llm_sessions = total_sessions
    if "A" in exp_keys:
        a_est = EXPERIMENT_SPECS["A"][scale]["est_sessions"]
        llm_sessions -= a_est // 3  # rule_based condition
    est_minutes = llm_sessions * 5 / 60  # ~5s per LLM session
    print(f"\n  Estimated time: ~{est_minutes:.0f} min ({llm_sessions} LLM sessions × ~5s)")
    print()

    if args.dry_run:
        print("  [DRY RUN — not executing]")
        return

    # ── Check Ollama ────────────────────────────────────────────────────
    import urllib.request
    import urllib.error
    try:
        urllib.request.urlopen("http://localhost:11434/api/tags", timeout=5)
    except Exception:
        print("  ERROR: Cannot connect to Ollama at http://localhost:11434")
        print("  Start Ollama first: ollama serve")
        sys.exit(1)
    print("  Ollama: connected")

    # ── Run experiments ─────────────────────────────────────────────────
    overall = OverallTracker(total_sessions)
    t0_all = time.time()
    results_summary = {}

    for k in exp_keys:
        spec = EXPERIMENT_SPECS[k]
        sc = spec[scale]
        est = sc["est_sessions"]

        # Load and override config
        cfg = load_config(spec["config"])
        for attr, val in sc["overrides"].items():
            setattr(cfg, attr, val)

        # Create per-experiment progress bar
        label = f"Exp {k} ({spec['name']})"
        exp_tracker = ProgressTracker(est, label)

        def on_session(result, _exp=exp_tracker, _overall=overall):
            _exp.update(result)
            _overall.update(result)

        exp_t0 = time.time()
        try:
            run_dir = run_experiment(
                name=spec["name"],
                base_cfg=cfg,
                output_base=args.output,
                seeds=sc["seeds"],
                on_session=on_session,
            )
            exp_elapsed = exp_tracker.close()
            results_summary[k] = {
                "status": "OK",
                "name": spec["name"],
                "run_dir": run_dir,
                "sessions": exp_tracker.completed,
                "deals": exp_tracker.deals,
                "elapsed_sec": round(exp_elapsed, 1),
            }
        except Exception as e:
            exp_tracker.close()
            results_summary[k] = {
                "status": "FAILED",
                "name": spec["name"],
                "error": str(e),
            }
            print(f"\n  ERROR in Exp {k}: {e}")

    overall.close()
    total_elapsed = time.time() - t0_all

    # ── Final summary ───────────────────────────────────────────────────
    print(f"\n{'='*65}")
    print(f"  PILOT COMPLETE — {total_elapsed:.0f}s total ({total_elapsed/60:.1f} min)")
    print(f"{'='*65}")
    print(f"  {'Exp':<4} {'Status':<8} {'Sessions':>9} {'Deals':>7} {'Time':>8} {'Output'}")
    print(f"  {'─'*4} {'─'*8} {'─'*9} {'─'*7} {'─'*8} {'─'*30}")
    for k in exp_keys:
        r = results_summary.get(k, {})
        status = r.get("status", "?")
        sessions = r.get("sessions", 0)
        deals = r.get("deals", 0)
        elapsed = r.get("elapsed_sec", 0)
        run_dir = r.get("run_dir", r.get("error", ""))
        print(f"  {k:<4} {status:<8} {sessions:>9} {deals:>7} {elapsed:>7.1f}s {run_dir}")

    total_sessions_done = sum(r.get("sessions", 0) for r in results_summary.values())
    total_deals = sum(r.get("deals", 0) for r in results_summary.values())
    failed = sum(1 for r in results_summary.values() if r.get("status") == "FAILED")
    print(f"\n  Total: {total_sessions_done} sessions, {total_deals} deals, "
          f"{failed} failed experiments")

    # Save pilot summary
    pilot_summary_path = os.path.join(
        args.output, f"pilot_summary_{time.strftime('%Y%m%d_%H%M%S')}.json"
    )
    os.makedirs(args.output, exist_ok=True)
    with open(pilot_summary_path, "w") as f:
        json.dump({
            "scale": scale,
            "experiments": exp_keys,
            "total_elapsed_sec": round(total_elapsed, 1),
            "total_sessions": total_sessions_done,
            "total_deals": total_deals,
            "results": results_summary,
        }, f, indent=2)
    print(f"  Pilot summary: {pilot_summary_path}")
    print()


if __name__ == "__main__":
    main()
