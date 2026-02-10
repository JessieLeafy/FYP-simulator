"""Integration test: run a small rule-based simulation end-to-end."""
import json
import os
import shutil
import unittest

from src.core.config import FixedScenarioConfig, SimulationConfig
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

    def test_fixed_single_run(self):
        """Fixed single-value scenario completes and summary includes metadata."""
        fixed = FixedScenarioConfig(
            buyer_value=120.0, buyer_budget=130.0, buyer_patience=5,
            seller_cost=80.0, seller_target_margin=0.15, seller_patience=5,
            item_reference_price=100.0,
        )
        cfg = SimulationConfig(
            agent_type="rule_based",
            scenario_mode="fixed",
            steps=2,
            buyers_per_step=3,
            sellers_per_step=3,
            seed=42,
            output_dir=self.output_dir,
            fixed=fixed,
        )
        rng = SeededRNG(cfg.seed)
        sim = MarketSimulator(cfg, rng)
        results = sim.run()

        self.assertGreater(len(results), 0)

        # all buyers should have the fixed value
        for r in results:
            self.assertEqual(r.buyer_value, 120.0)
            self.assertEqual(r.seller_cost, 80.0)

        # summary.json should contain scenario metadata
        summary_path = os.path.join(sim.run_dir, "summary.json")
        with open(summary_path) as f:
            summary = json.load(f)

        self.assertEqual(summary["scenario_mode"], "fixed")
        self.assertIn("fixed_params", summary)
        self.assertEqual(summary["fixed_params"]["buyer_value"], 120.0)
        self.assertEqual(summary["fixed_params"]["seller_cost"], 80.0)

    def test_fixed_enumerated_run(self):
        """Enumerated fixed scenario cycles through values correctly."""
        fixed = FixedScenarioConfig(
            buyer_value=[90, 100, 110],
            buyer_budget=140.0,
            seller_cost=[60, 70],
            seller_target_margin=0.15,
            item_reference_price=100.0,
            selection="cycle",
        )
        cfg = SimulationConfig(
            agent_type="rule_based",
            scenario_mode="fixed",
            steps=1,
            buyers_per_step=6,
            sellers_per_step=6,
            seed=42,
            output_dir=self.output_dir,
            fixed=fixed,
        )
        rng = SeededRNG(cfg.seed)
        sim = MarketSimulator(cfg, rng)
        results = sim.run()

        self.assertEqual(len(results), 6)

        summary_path = os.path.join(sim.run_dir, "summary.json")
        with open(summary_path) as f:
            summary = json.load(f)

        self.assertEqual(summary["scenario_mode"], "fixed")
        self.assertEqual(summary["fixed_params"]["buyer_value"], [90, 100, 110])
        self.assertEqual(summary["fixed_params"]["seller_cost"], [60, 70])

    def test_distribution_mode_backward_compat(self):
        """Existing distribution configs still work and include scenario_mode."""
        cfg = SimulationConfig(
            agent_type="rule_based",
            steps=1,
            buyers_per_step=3,
            sellers_per_step=3,
            seed=42,
            output_dir=self.output_dir,
        )
        rng = SeededRNG(cfg.seed)
        sim = MarketSimulator(cfg, rng)
        sim.run()

        with open(os.path.join(sim.run_dir, "summary.json")) as f:
            summary = json.load(f)

        self.assertEqual(summary["scenario_mode"], "distribution")
        self.assertNotIn("fixed_params", summary)


if __name__ == "__main__":
    unittest.main()
