"""Integration test: run a small rule-based simulation end-to-end."""
import json
import os
import shutil
import unittest

from src.core.config import SimulationConfig
from src.core.rng import SeededRNG
from src.market.simulator import MarketSimulator


class TestSmallRun(unittest.TestCase):

    def setUp(self):
        self.output_dir = os.path.join("outputs", "_test_small_run")
        os.makedirs(self.output_dir, exist_ok=True)

    def tearDown(self):
        if os.path.exists(self.output_dir):
            shutil.rmtree(self.output_dir)

    def test_small_rule_based_run(self):
        cfg = SimulationConfig(
            agent_type="rule_based",
            steps=3,
            buyers_per_step=5,
            sellers_per_step=5,
            seed=42,
            output_dir=self.output_dir,
        )
        rng = SeededRNG(cfg.seed)
        sim = MarketSimulator(cfg, rng)
        results = sim.run()

        # at least some negotiations happened
        self.assertGreater(len(results), 0)

        # output files exist
        run_dir = sim.run_dir
        events_path = os.path.join(run_dir, "events.jsonl")
        summary_path = os.path.join(run_dir, "summary.json")
        deals_path = os.path.join(run_dir, "deals.csv")

        self.assertTrue(os.path.exists(events_path), "events.jsonl missing")
        self.assertTrue(os.path.exists(summary_path), "summary.json missing")
        self.assertTrue(os.path.exists(deals_path), "deals.csv missing")

        # summary has all expected keys
        with open(summary_path) as f:
            summary = json.load(f)

        expected_keys = [
            "deal_success_rate",
            "avg_price",
            "median_price",
            "buyer_surplus_mean",
            "seller_surplus_mean",
            "avg_rounds_to_close",
            "deadlock_rate",
            "budget_violation_attempts",
            "cost_violation_attempts",
            "total_negotiations",
        ]
        for key in expected_keys:
            self.assertIn(key, summary, f"Missing metric: {key}")

        # events.jsonl is valid JSONL
        with open(events_path) as f:
            for lineno, line in enumerate(f, 1):
                line = line.strip()
                if line:
                    try:
                        json.loads(line)
                    except json.JSONDecodeError:
                        self.fail(f"Invalid JSON on line {lineno}")

        # deals.csv has a header + rows
        with open(deals_path) as f:
            lines = f.readlines()
        self.assertGreater(len(lines), 1, "deals.csv should have header + rows")

    def test_deterministic_across_runs(self):
        """Same seed → same results."""
        def _run(seed):
            cfg = SimulationConfig(
                agent_type="rule_based",
                steps=2,
                buyers_per_step=3,
                sellers_per_step=3,
                seed=seed,
                output_dir=self.output_dir,
            )
            rng = SeededRNG(cfg.seed)
            sim = MarketSimulator(cfg, rng)
            results = sim.run()
            return [
                (r.deal_made, r.deal_price, r.rounds_taken)
                for r in results
            ]

        run_a = _run(99)
        run_b = _run(99)
        self.assertEqual(run_a, run_b)


if __name__ == "__main__":
    unittest.main()
