#!/usr/bin/env python3
"""Run FULL gate-off experiments for A (Concession) and C (Deadline).

Reuses existing experiment infrastructure with gate_enabled=false.
Outputs to outputs/experiments_gate_off/ to avoid overwriting gate-on results.

Usage:
    python experiments/run_gate_off_full_ac.py
"""
from __future__ import annotations

import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.core.config import load_config  # noqa: E402
from experiments.experiments import run_experiment  # noqa: E402

try:
    from tqdm import tqdm
    HAS_TQDM = True
except ImportError:
    HAS_TQDM = False

OUTPUT_BASE = "outputs/experiments_gate_off"

EXPERIMENTS = {
    "A": {
        "name": "concession",
        "config": "experiments/configs/exp_concession.yaml",
        "seeds": [42, 123, 456],
        # 3 conditions x 3 seeds x 5 steps x 10 pairs = 450 sessions
        "est_sessions": 450,
    },
    "C": {
        "name": "deadline",
        "config": "experiments/configs/exp_deadline.yaml",
        "seeds": [42, 123, 456],
        # 3 max_rounds conditions x 3 seeds x 5 steps x 10 pairs = 450 sessions
        "est_sessions": 450,
    },
}


class ProgressTracker:
    def __init__(self, total_sessions: int, label: str = ""):
        self.total = total_sessions
        self.completed = 0
        self.deals = 0
        self.start_time = time.time()

        if HAS_TQDM:
            self.bar = tqdm(
                total=total_sessions,
                desc=label,
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
            print(f"  {label}: 0/{total_sessions} sessions", end="", flush=True)

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
            pct = self.completed / self.total * 100
            print(
                f"\r  [{pct:5.1f}%] {self.completed}/{self.total} sessions "
                f"[{elapsed:.0f}s elapsed, ~{remaining:.0f}s remaining, "
                f"deals={self.deals}]",
                end="", flush=True,
            )

    def close(self):
        elapsed = time.time() - self.start_time
        if self.bar:
            self.bar.close()
        else:
            print()
        return elapsed


def main():
    total_est = sum(e["est_sessions"] for e in EXPERIMENTS.values())

    print(f"\n{'='*65}")
    print(f"  GATE-OFF FULL RUN — Experiments A & C")
    print(f"{'='*65}")
    print(f"  Output base: {OUTPUT_BASE}")
    print(f"  Gate enabled: FALSE")
    print(f"  Total estimated sessions: {total_est}")
    print()

    # Estimate: ~1/3 of Exp A is rule_based (~0.01s), rest is LLM (~5s)
    llm_sessions = total_est - (450 // 3)
    est_minutes = llm_sessions * 5 / 60
    print(f"  Estimated time: ~{est_minutes:.0f} min ({llm_sessions} LLM sessions x ~5s)")
    print()

    # Check Ollama
    import urllib.request
    try:
        urllib.request.urlopen("http://localhost:11434/api/tags", timeout=5)
    except Exception:
        print("  ERROR: Cannot connect to Ollama at http://localhost:11434")
        sys.exit(1)
    print("  Ollama: connected")
    print()

    os.makedirs(OUTPUT_BASE, exist_ok=True)
    t0_all = time.time()
    results_summary = {}

    overall_done = 0
    overall_total = total_est

    for key, spec in EXPERIMENTS.items():
        cfg = load_config(spec["config"])
        # CRITICAL: disable gate
        cfg.negotiation.gate_enabled = False

        label = f"Exp {key} ({spec['name']}) [GATE OFF]"
        tracker = ProgressTracker(spec["est_sessions"], label)

        def on_session(result, _t=tracker):
            nonlocal overall_done
            _t.update(result)
            overall_done += 1

        exp_t0 = time.time()
        try:
            run_dir = run_experiment(
                name=spec["name"],
                base_cfg=cfg,
                output_base=OUTPUT_BASE,
                seeds=spec["seeds"],
                on_session=on_session,
            )
            exp_elapsed = tracker.close()
            results_summary[key] = {
                "status": "OK",
                "name": spec["name"],
                "run_dir": run_dir,
                "sessions": tracker.completed,
                "deals": tracker.deals,
                "elapsed_sec": round(exp_elapsed, 1),
                "deal_rate": round(tracker.deals / tracker.completed, 4) if tracker.completed else 0,
            }
            print(f"  -> {run_dir}")
            elapsed_total = time.time() - t0_all
            print(f"  Overall: {overall_done}/{overall_total} ({overall_done/overall_total*100:.1f}%) "
                  f"[{elapsed_total:.0f}s elapsed]")
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

    total_elapsed = time.time() - t0_all

    # Final summary
    print(f"\n{'='*65}")
    print(f"  GATE-OFF FULL RUN COMPLETE — {total_elapsed:.0f}s ({total_elapsed/60:.1f} min)")
    print(f"{'='*65}")
    print(f"  {'Exp':<4} {'Status':<8} {'Sessions':>9} {'Deals':>7} {'Rate':>7} {'Time':>8} {'Output'}")
    print(f"  {'─'*4} {'─'*8} {'─'*9} {'─'*7} {'─'*7} {'─'*8} {'─'*30}")
    for k in EXPERIMENTS:
        r = results_summary.get(k, {})
        status = r.get("status", "?")
        sessions = r.get("sessions", 0)
        deals = r.get("deals", 0)
        rate = r.get("deal_rate", 0)
        elapsed = r.get("elapsed_sec", 0)
        run_dir = r.get("run_dir", r.get("error", ""))
        print(f"  {k:<4} {status:<8} {sessions:>9} {deals:>7} {rate:>6.1%} {elapsed:>7.1f}s {run_dir}")

    total_sessions_done = sum(r.get("sessions", 0) for r in results_summary.values())
    total_deals = sum(r.get("deals", 0) for r in results_summary.values())
    print(f"\n  Total: {total_sessions_done} sessions, {total_deals} deals")

    # Save summary JSON
    summary_path = os.path.join(
        OUTPUT_BASE, f"gate_off_full_ac_{time.strftime('%Y%m%d_%H%M%S')}.json"
    )
    with open(summary_path, "w") as f:
        json.dump({
            "gate_enabled": False,
            "scale": "full",
            "experiments": list(EXPERIMENTS.keys()),
            "total_elapsed_sec": round(total_elapsed, 1),
            "total_sessions": total_sessions_done,
            "total_deals": total_deals,
            "results": results_summary,
        }, f, indent=2)
    print(f"  Summary JSON: {summary_path}")
    print()


if __name__ == "__main__":
    main()
