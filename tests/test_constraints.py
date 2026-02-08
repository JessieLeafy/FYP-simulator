"""Tests for the constraint validation layer."""
import unittest

from src.core.types import (
    ActionType,
    AgentRole,
    BuyerState,
    Item,
    NegotiationAction,
    SellerState,
)
from src.negotiation.constraints import validate_action


class TestConstraints(unittest.TestCase):

    def setUp(self):
        self.item = Item("i1", "Widget A", 100.0)
        self.buyer = BuyerState("b1", value=120.0, budget=110.0, patience=5)
        self.seller = SellerState("s1", cost=80.0, target_margin=0.15, patience=5)

    def _action(self, action, price=None, msg="ok", reason="r"):
        return NegotiationAction(ActionType(action), price, msg, reason)

    # ── valid cases ──────────────────────────────────────────────────────

    def test_valid_buyer_offer(self):
        r = validate_action(
            AgentRole.BUYER, self._action("offer", 90.0),
            self.buyer, self.seller, None, self.item, 0,
        )
        self.assertTrue(r.valid)

    def test_valid_seller_offer(self):
        r = validate_action(
            AgentRole.SELLER, self._action("offer", 95.0),
            self.buyer, self.seller, None, self.item, 0,
        )
        self.assertTrue(r.valid)

    def test_valid_buyer_accept(self):
        r = validate_action(
            AgentRole.BUYER, self._action("accept"),
            self.buyer, self.seller, 100.0, self.item, 1,
        )
        self.assertTrue(r.valid)

    def test_valid_seller_accept(self):
        r = validate_action(
            AgentRole.SELLER, self._action("accept"),
            self.buyer, self.seller, 90.0, self.item, 1,
        )
        self.assertTrue(r.valid)

    # ── budget / value violations ────────────────────────────────────────

    def test_buyer_exceeds_budget(self):
        r = validate_action(
            AgentRole.BUYER, self._action("offer", 115.0),
            self.buyer, self.seller, None, self.item, 0,
        )
        self.assertFalse(r.valid)
        self.assertEqual(r.violation_type, "budget")

    def test_buyer_exceeds_value(self):
        buyer = BuyerState("b1", value=100.0, budget=200.0, patience=5)
        r = validate_action(
            AgentRole.BUYER, self._action("offer", 105.0),
            buyer, self.seller, None, self.item, 0,
        )
        self.assertFalse(r.valid)
        self.assertEqual(r.violation_type, "budget")

    # ── cost violations ──────────────────────────────────────────────────

    def test_seller_below_cost(self):
        r = validate_action(
            AgentRole.SELLER, self._action("offer", 75.0),
            self.buyer, self.seller, None, self.item, 0,
        )
        self.assertFalse(r.valid)
        self.assertEqual(r.violation_type, "cost")

    # ── bounds ───────────────────────────────────────────────────────────

    def test_price_below_min(self):
        r = validate_action(
            AgentRole.BUYER, self._action("offer", 0.5),
            self.buyer, self.seller, None, self.item, 0,
        )
        self.assertFalse(r.valid)
        self.assertEqual(r.violation_type, "bounds")

    def test_price_above_max(self):
        r = validate_action(
            AgentRole.SELLER, self._action("offer", 600.0),
            self.buyer, self.seller, None, self.item, 0,
        )
        self.assertFalse(r.valid)
        self.assertEqual(r.violation_type, "bounds")

    # ── logic violations ─────────────────────────────────────────────────

    def test_accept_without_prior_offer(self):
        r = validate_action(
            AgentRole.BUYER, self._action("accept"),
            self.buyer, self.seller, None, self.item, 0,
        )
        self.assertFalse(r.valid)
        self.assertEqual(r.violation_type, "logic")

    def test_buyer_accept_over_budget(self):
        r = validate_action(
            AgentRole.BUYER, self._action("accept"),
            self.buyer, self.seller, 115.0, self.item, 1,
        )
        self.assertFalse(r.valid)
        self.assertEqual(r.violation_type, "budget")

    def test_seller_accept_below_cost(self):
        r = validate_action(
            AgentRole.SELLER, self._action("accept"),
            self.buyer, self.seller, 70.0, self.item, 1,
        )
        self.assertFalse(r.valid)
        self.assertEqual(r.violation_type, "cost")


if __name__ == "__main__":
    unittest.main()
