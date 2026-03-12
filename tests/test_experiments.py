"""Tests for experiment suite (Upgrade B).

Each test runs with backend=mock (rule_based agents only) to ensure
experiments complete, write expected files, and produce valid outputs.
"""
import csv
import json
import os
import shutil
import unittest

from src.core.config import FixedScenarioConfig, SimulationConfig
from src.core.types import MarketTickStats
from src.evaluation.reports import (
    write_anchoring_csv,
    write_concession_csv,
    write_deadline_csv,
    write_experiment_summary,
    write_tick_stats_csv,
)


class TestReportWriters(unittest.TestCase):
    """Test that experiment report writers produce correct output."""

    def setUp(self):
        self.run_dir = os.path.join("outputs", "_test_reports")
        os.makedirs(self.run_dir, exist_ok=True)

    def tearDown(self):
        if os.path.exists(self.run_dir):
            shutil.rmtree(self.run_dir)

    def test_tick_stats_csv(self):
        stats = [
            MarketTickStats(
                tick=0, num_sessions=10, deals_made=6, fail_rate=0.4,
                mean_price=95.0, price_std=5.0, liquidity=0.6,
                buyer_surplus_mean=10.0, seller_surplus_mean=8.0,
            ),
            MarketTickStats(
                tick=1, num_sessions=10, deals_made=7, fail_rate=0.3,
                mean_price=97.0, price_std=4.0, liquidity=0.7,
                buyer_surplus_mean=9.0, seller_surplus_mean=9.0,
            ),
        ]
        path = write_tick_stats_csv(stats, self.run_dir)
        self.assertTrue(os.path.exists(path))

        with open(path) as f:
            reader = csv.DictReader(f)
            rows = list(reader)

        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["tick"], "0")
        self.assertEqual(rows[1]["mean_price"], "97.0")

    def test_concession_csv(self):
        rows = [
            {"condition": "rule_based", "session_id": 1, "role": "buyer",
             "round": 0, "offer_price": 60.0},
            {"condition": "rule_based", "session_id": 1, "role": "seller",
             "round": 1, "offer_price": 95.0},
        ]
        path = write_concession_csv(rows, self.run_dir)
        self.assertTrue(os.path.exists(path))

        with open(path) as f:
            reader = csv.DictReader(f)
            csv_rows = list(reader)
        self.assertEqual(len(csv_rows), 2)
        self.assertIn("condition", csv_rows[0])
        self.assertIn("offer_price", csv_rows[0])

    def test_anchoring_csv(self):
        rows = [
            {"condition": "low", "session_id": 1, "first_offer": 50.0,
             "final_price": 85.0, "deal_made": True},
        ]
        path = write_anchoring_csv(rows, self.run_dir)
        self.assertTrue(os.path.exists(path))

        with open(path) as f:
            reader = csv.DictReader(f)
            csv_rows = list(reader)
        self.assertEqual(len(csv_rows), 1)
        self.assertEqual(csv_rows[0]["first_offer"], "50.0")

    def test_deadline_csv(self):
        rows = [
            {"condition": 4, "session_id": 1, "deal_made": True,
             "rounds_taken": 3},
        ]
        path = write_deadline_csv(rows, self.run_dir)
        self.assertTrue(os.path.exists(path))

    def test_experiment_summary(self):
        data = {"experiment": "test", "metric": 42, "git_hash": "abc123"}
        path = write_experiment_summary(data, self.run_dir)
        self.assertTrue(os.path.exists(path))

        with open(path) as f:
            loaded = json.load(f)
        self.assertEqual(loaded["experiment"], "test")
        self.assertEqual(loaded["metric"], 42)


class TestExperimentRunners(unittest.TestCase):
    """Integration tests: each experiment completes and writes files."""

    def setUp(self):
        self.output_base = os.path.join("outputs", "_test_experiments")
        os.makedirs(self.output_base, exist_ok=True)

    def tearDown(self):
        if os.path.exists(self.output_base):
            shutil.rmtree(self.output_base)

    def _base_cfg(self) -> SimulationConfig:
        return SimulationConfig(
            agent_type="rule_based",
            steps=2,
            buyers_per_step=5,
            sellers_per_step=5,
            seed=42,
            scenario_mode="fixed",
            fixed=FixedScenarioConfig(
                buyer_value=120.0, buyer_budget=130.0, buyer_patience=5,
                seller_cost=80.0, seller_target_margin=0.15,
                seller_patience=5, item_reference_price=100.0,
            ),
        )

    def test_concession_experiment(self):
        from experiments.experiments import run_concession

        run_dir, _ = run_concession(
            self._base_cfg(),
            output_base=self.output_base,
            seeds=[42],
            conditions={"rule_based": {"agent_type": "rule_based"}},
        )
        self.assertTrue(os.path.exists(run_dir))
        self.assertTrue(os.path.exists(os.path.join(run_dir, "concession_curves.csv")))
        self.assertTrue(os.path.exists(os.path.join(run_dir, "experiment_summary.json")))

        # check CSV has correct columns
        with open(os.path.join(run_dir, "concession_curves.csv")) as f:
            reader = csv.DictReader(f)
            rows = list(reader)
        self.assertGreater(len(rows), 0)
        self.assertIn("condition", rows[0])
        self.assertIn("offer_price", rows[0])

    def test_anchoring_experiment(self):
        from experiments.experiments import run_anchoring

        run_dir, _ = run_anchoring(
            self._base_cfg(),
            output_base=self.output_base,
            seeds=[42],
        )
        self.assertTrue(os.path.exists(os.path.join(run_dir, "anchoring.csv")))
        self.assertTrue(os.path.exists(os.path.join(run_dir, "experiment_summary.json")))

        with open(os.path.join(run_dir, "experiment_summary.json")) as f:
            summary = json.load(f)
        self.assertIn("first_offer_final_price_correlation", summary)

    def test_deadline_experiment(self):
        from experiments.experiments import run_deadline

        run_dir, _ = run_deadline(
            self._base_cfg(),
            output_base=self.output_base,
            seeds=[42],
            max_rounds_list=[4, 8],
        )
        self.assertTrue(os.path.exists(os.path.join(run_dir, "deadline.csv")))
        self.assertTrue(os.path.exists(os.path.join(run_dir, "experiment_summary.json")))

        with open(os.path.join(run_dir, "experiment_summary.json")) as f:
            summary = json.load(f)
        self.assertIn("condition_stats", summary)
        self.assertIn("4", summary["condition_stats"])
        self.assertIn("8", summary["condition_stats"])

    def test_market_dynamics_experiment(self):
        from experiments.experiments import run_market_dynamics

        cfg = SimulationConfig(
            agent_type="rule_based",
            mode="market",
            steps=5,
            buyers_per_step=5,
            sellers_per_step=5,
            seed=42,
        )
        run_dir, _ = run_market_dynamics(
            cfg,
            output_base=self.output_base,
            seeds=[42],
        )
        self.assertTrue(os.path.exists(os.path.join(run_dir, "tick_stats.csv")))
        self.assertTrue(os.path.exists(os.path.join(run_dir, "experiment_summary.json")))

        with open(os.path.join(run_dir, "experiment_summary.json")) as f:
            summary = json.load(f)
        self.assertIn("price_trend_slope", summary)

    def test_shock_response_experiment(self):
        from experiments.experiments import run_shock_response

        cfg = SimulationConfig(
            agent_type="rule_based",
            mode="market",
            steps=5,
            buyers_per_step=5,
            sellers_per_step=5,
            seed=42,
        )
        run_dir, _ = run_shock_response(
            cfg,
            output_base=self.output_base,
            seeds=[42],
        )
        self.assertTrue(os.path.exists(os.path.join(run_dir, "experiment_summary.json")))

        with open(os.path.join(run_dir, "experiment_summary.json")) as f:
            summary = json.load(f)
        self.assertEqual(summary["experiment"], "shock_response")

    def test_dispatcher(self):
        from experiments.experiments import run_experiment

        run_dir, _ = run_experiment(
            "concession",
            self._base_cfg(),
            output_base=self.output_base,
            seeds=[42],
            conditions={"rb": {"agent_type": "rule_based"}},
        )
        self.assertTrue(os.path.exists(run_dir))

    def test_dispatcher_unknown(self):
        from experiments.experiments import run_experiment

        with self.assertRaises(ValueError):
            run_experiment("nonexistent", self._base_cfg())


if __name__ == "__main__":
    unittest.main()
