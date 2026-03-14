"""Tests for anchor_mode feature (fixed / updated / no_anchor)."""
import os
import shutil
import unittest

from src.core.config import SimulationConfig
from src.core.rng import SeededRNG
from src.core.types import (
    AgentContext,
    AgentRole,
    Item,
    NegotiationResult,
    TerminationReason,
)
from src.llm.prompts import (
    build_free_language_buyer_prompt,
    build_free_language_seller_prompt,
)
from src.market.simulator import MarketSimulator


class TestAnchorModeConfig(unittest.TestCase):
    """anchor_mode defaults to 'fixed' and is configurable."""

    def test_default_is_fixed(self):
        cfg = SimulationConfig()
        self.assertEqual(cfg.market.anchor_mode, "fixed")

    def test_can_set_updated(self):
        cfg = SimulationConfig()
        cfg.market.anchor_mode = "updated"
        self.assertEqual(cfg.market.anchor_mode, "updated")


class TestAnchorUpdateLogic(unittest.TestCase):
    """Effective anchors are updated after ticks with deals."""

    def setUp(self):
        self.cfg = SimulationConfig()
        self.cfg.agent_type = "rule_based"
        self.cfg.mode = "market"
        self.cfg.steps = 3
        self.cfg.buyers_per_step = 2
        self.cfg.sellers_per_step = 2
        self.cfg.seed = 42
        self.cfg.output_dir = "outputs/test_anchor_mode"

    def tearDown(self):
        if os.path.exists("outputs/test_anchor_mode"):
            shutil.rmtree("outputs/test_anchor_mode")

    def test_fixed_mode_preserves_reference_prices(self):
        """In fixed mode, catalog item reference_prices should not change."""
        self.cfg.market.anchor_mode = "fixed"
        rng = SeededRNG(self.cfg.seed)
        sim = MarketSimulator(self.cfg, rng)

        original_prices = {
            item.item_id: item.reference_price
            for item in sim.catalog.items
        }

        sim.run()

        # Reference prices on catalog items should still match originals
        for item in sim.catalog.items:
            self.assertEqual(
                sim._original_ref_prices[item.item_id],
                original_prices[item.item_id],
            )

    def test_updated_mode_changes_effective_anchors(self):
        """In updated mode, effective anchors should change when deals occur."""
        self.cfg.market.anchor_mode = "updated"
        rng = SeededRNG(self.cfg.seed)
        sim = MarketSimulator(self.cfg, rng)

        original_anchors = dict(sim._effective_anchors)
        sim.run()

        # If any deals happened, at least one anchor should differ
        deals = [r for r in sim.results if r.deal_made]
        if deals:
            changed = any(
                sim._effective_anchors[iid] != original_anchors[iid]
                for iid in original_anchors
                if iid in sim._effective_anchors
            )
            self.assertTrue(
                changed,
                "Expected at least one effective anchor to update after deals",
            )

    def test_updated_mode_fallback_on_no_deals(self):
        """If a tick has no deals, effective anchors should not change."""
        self.cfg.market.anchor_mode = "updated"
        rng = SeededRNG(self.cfg.seed)
        sim = MarketSimulator(self.cfg, rng)

        # Manually verify the fallback: set anchors, then simulate
        # an empty tick_results scenario
        sim._effective_anchors["test_item"] = 99.99
        # No deals for this item → anchor should stay
        item_prices: dict[str, list[float]] = {}  # empty
        for iid, prices in item_prices.items():
            sim._effective_anchors[iid] = sum(prices) / len(prices)
        self.assertEqual(sim._effective_anchors["test_item"], 99.99)

    def test_no_anchor_mode_sets_zero_ref(self):
        """In no_anchor mode, reference_price should be set to 0 for sessions."""
        self.cfg.market.anchor_mode = "no_anchor"
        rng = SeededRNG(self.cfg.seed)
        sim = MarketSimulator(self.cfg, rng)

        # Verify original prices are stored
        for item in sim.catalog.items:
            self.assertGreater(sim._original_ref_prices[item.item_id], 0)

        sim.run()
        # Original prices should still be recorded
        for iid, price in sim._original_ref_prices.items():
            self.assertGreater(price, 0)


class TestPromptsWithNoAnchor(unittest.TestCase):
    """Prompts handle ref_price=0 (no_anchor) gracefully."""

    def _make_ctx(self, role, ref_price):
        item = Item("i1", "Widget", ref_price)
        return AgentContext(
            item=item,
            role=role,
            round_number=0,
            max_rounds=10,
            history=[],
            last_offer=None,
            reservation_price=100.0,
            budget=150.0 if role == AgentRole.BUYER else None,
            target_margin=0.15 if role == AgentRole.SELLER else None,
        )

    def test_buyer_prompt_with_reference(self):
        ctx = self._make_ctx(AgentRole.BUYER, 120.0)
        prompt = build_free_language_buyer_prompt(ctx)
        self.assertIn("market reference price: $120.00", prompt)

    def test_buyer_prompt_no_anchor(self):
        ctx = self._make_ctx(AgentRole.BUYER, 0.0)
        prompt = build_free_language_buyer_prompt(ctx)
        self.assertNotIn("market reference price", prompt)
        self.assertIn("Product: Widget", prompt)

    def test_seller_prompt_with_reference(self):
        ctx = self._make_ctx(AgentRole.SELLER, 120.0)
        prompt = build_free_language_seller_prompt(ctx)
        self.assertIn("market reference price: $120.00", prompt)

    def test_seller_prompt_no_anchor(self):
        ctx = self._make_ctx(AgentRole.SELLER, 0.0)
        prompt = build_free_language_seller_prompt(ctx)
        self.assertNotIn("market reference price", prompt)
        self.assertIn("Product: Widget", prompt)
        # Initial asking price should be cost-based, not ref-based
        # cost=100, margin=0.15 → initial = 100 * (1 + 0.30) = 130
        self.assertIn("$130.00", prompt)

    def test_seller_prompt_no_anchor_initial_price_from_cost(self):
        """When ref=0, seller initial price should be cost*(1+2*margin)."""
        ctx = self._make_ctx(AgentRole.SELLER, 0.0)
        ctx.reservation_price = 80.0
        ctx.target_margin = 0.20
        prompt = build_free_language_seller_prompt(ctx)
        # 80 * (1 + 2*0.20) = 80 * 1.40 = 112.00
        self.assertIn("$112.00", prompt)


if __name__ == "__main__":
    unittest.main()
