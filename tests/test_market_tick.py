"""Tests for market-mode tick stats and deterministic market simulation."""
import json
import os
import shutil
import unittest

from src.core.config import SimulationConfig
from src.core.rng import SeededRNG
from src.core.types import (
    Item,
    MarketTickStats,
    NegotiationResult,
    TerminationReason,
)
from src.evaluation.metrics import compute_tick_stats
from src.market.simulator import MarketSimulator


class TestComputeTickStats(unittest.TestCase):

    def _make_result(self, deal_made, price=None, buyer_value=120.0, seller_cost=70.0):
        return NegotiationResult(
            item=Item("i1", "Widget A", 100.0),
            buyer_id="b1",
            seller_id="s1",
            deal_made=deal_made,
            deal_price=price,
            termination_reason=(
                TerminationReason.ACCEPTED if deal_made
                else TerminationReason.REJECTED
            ),
            rounds_taken=3,
            buyer_value=buyer_value,
            seller_cost=seller_cost,
            buyer_surplus=(buyer_value - price) if price and deal_made else 0,
            seller_surplus=(price - seller_cost) if price and deal_made else 0,
        )

    def test_basic_stats(self):
        results = [
            self._make_result(True, 90.0),
            self._make_result(True, 100.0),
            self._make_result(False),
        ]
        stats = compute_tick_stats(0, results)
        self.assertEqual(stats.tick, 0)
        self.assertEqual(stats.num_sessions, 3)
        self.assertEqual(stats.deals_made, 2)
        self.assertAlmostEqual(stats.fail_rate, 1 / 3, places=3)
        self.assertAlmostEqual(stats.mean_price, 95.0, places=2)
        self.assertGreater(stats.price_std, 0)
        self.assertAlmostEqual(stats.liquidity, 2 / 3, places=3)

    def test_no_deals(self):
        results = [self._make_result(False), self._make_result(False)]
        stats = compute_tick_stats(1, results)
        self.assertEqual(stats.deals_made, 0)
        self.assertEqual(stats.mean_price, 0)
        self.assertEqual(stats.liquidity, 0)
        self.assertEqual(stats.fail_rate, 1.0)

    def test_empty_results(self):
        stats = compute_tick_stats(0, [])
        self.assertEqual(stats.num_sessions, 0)
        self.assertEqual(stats.deals_made, 0)

    def test_single_deal_no_std(self):
        results = [self._make_result(True, 95.0)]
        stats = compute_tick_stats(0, results)
        self.assertEqual(stats.price_std, 0)  # stdev needs >1

    def test_returns_market_tick_stats_type(self):
        results = [self._make_result(True, 90.0)]
        stats = compute_tick_stats(0, results)
        self.assertIsInstance(stats, MarketTickStats)


class TestMarketModeDeterminism(unittest.TestCase):

    def setUp(self):
        self.output_dir = os.path.join("outputs", "_test_market_tick")
        os.makedirs(self.output_dir, exist_ok=True)

    def tearDown(self):
        if os.path.exists(self.output_dir):
            shutil.rmtree(self.output_dir)

    def _run_market(self, seed):
        cfg = SimulationConfig(
            agent_type="rule_based",
            mode="market",
            steps=3,
            buyers_per_step=5,
            sellers_per_step=5,
            seed=seed,
            output_dir=self.output_dir,
        )
        rng = SeededRNG(cfg.seed)
        sim = MarketSimulator(cfg, rng)
        sim.run()
        return sim

    def test_market_mode_produces_tick_stats(self):
        sim = self._run_market(42)
        self.assertEqual(len(sim.tick_stats), 3)
        for i, ts in enumerate(sim.tick_stats):
            self.assertEqual(ts.tick, i)
            self.assertGreater(ts.num_sessions, 0)

    def test_market_mode_deterministic(self):
        """Same seed → same tick stats."""
        sim_a = self._run_market(99)
        sim_b = self._run_market(99)
        self.assertEqual(len(sim_a.tick_stats), len(sim_b.tick_stats))
        for a, b in zip(sim_a.tick_stats, sim_b.tick_stats):
            self.assertEqual(a.deals_made, b.deals_made)
            self.assertEqual(a.mean_price, b.mean_price)
            self.assertEqual(a.liquidity, b.liquidity)

    def test_tick_end_events_in_log(self):
        """Market mode should write tick_end events to events.jsonl."""
        sim = self._run_market(42)
        events_path = os.path.join(sim.run_dir, "events.jsonl")
        tick_events = []
        with open(events_path) as f:
            for line in f:
                line = line.strip()
                if line:
                    obj = json.loads(line)
                    if obj.get("event") == "tick_end":
                        tick_events.append(obj)
        self.assertEqual(len(tick_events), 3)
        for i, ev in enumerate(tick_events):
            self.assertEqual(ev["tick"], i)
            self.assertIn("mean_price", ev)
            self.assertIn("liquidity", ev)

    def test_session_mode_no_tick_stats(self):
        """Session mode should NOT produce tick stats."""
        cfg = SimulationConfig(
            agent_type="rule_based",
            mode="session",
            steps=2,
            buyers_per_step=3,
            sellers_per_step=3,
            seed=42,
            output_dir=self.output_dir,
        )
        rng = SeededRNG(cfg.seed)
        sim = MarketSimulator(cfg, rng)
        sim.run()
        self.assertEqual(len(sim.tick_stats), 0)

    def test_summary_includes_mode(self):
        sim = self._run_market(42)
        summary_path = os.path.join(sim.run_dir, "summary.json")
        with open(summary_path) as f:
            summary = json.load(f)
        self.assertEqual(summary["mode"], "market")
        self.assertEqual(summary["num_ticks"], 3)


if __name__ == "__main__":
    unittest.main()
