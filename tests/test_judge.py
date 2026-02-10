"""Tests for the ActionJudge validation and enforcement layer."""
import unittest

from src.core.types import (
    ActionType,
    AgentRole,
    BuyerState,
    Item,
    NegotiationAction,
    SellerState,
)
from src.negotiation.judge import ActionJudge


class TestActionJudge(unittest.TestCase):

    def setUp(self):
        self.judge = ActionJudge(min_price=1.0, max_price=500.0)
        self.item = Item("i1", "Widget A", 100.0)
        self.buyer = BuyerState("b1", value=120.0, budget=110.0, patience=5)
        self.seller = SellerState("s1", cost=80.0, target_margin=0.15, patience=5)

    def _action(self, action, price=None, msg="ok", reason="r"):
        return NegotiationAction(ActionType(action), price, msg, reason)

    # ── first-round corrections ───────────────────────────────────────────

    def test_first_round_counter_corrected_to_offer(self):
        action = self._action("counter", 90.0)
        corrected = self.judge.correct_first_round(
            action, AgentRole.BUYER, self.buyer, self.seller,
        )
        self.assertEqual(corrected.action, ActionType.OFFER)
        self.assertEqual(corrected.offer_price, 90.0)

    def test_first_round_accept_corrected_to_offer(self):
        action = self._action("accept")
        corrected = self.judge.correct_first_round(
            action, AgentRole.BUYER, self.buyer, self.seller,
        )
        self.assertEqual(corrected.action, ActionType.OFFER)
        self.assertIsNotNone(corrected.offer_price)

    def test_first_round_reject_corrected_to_offer_seller(self):
        action = self._action("reject")
        corrected = self.judge.correct_first_round(
            action, AgentRole.SELLER, self.buyer, self.seller,
        )
        self.assertEqual(corrected.action, ActionType.OFFER)
        # seller fallback price is cost * 1.5
        self.assertEqual(corrected.offer_price, round(80.0 * 1.5, 2))

    def test_first_round_offer_unchanged(self):
        action = self._action("offer", 90.0)
        corrected = self.judge.correct_first_round(
            action, AgentRole.BUYER, self.buyer, self.seller,
        )
        self.assertEqual(corrected.action, ActionType.OFFER)
        self.assertEqual(corrected.offer_price, 90.0)

    # ── enforce: valid action passes ──────────────────────────────────────

    def test_valid_action_passes(self):
        action = self._action("offer", 90.0)
        result, risk = self.judge.enforce(
            AgentRole.BUYER, action, self.buyer, self.seller,
            None, self.item, 1,
        )
        self.assertEqual(result.action, ActionType.OFFER)
        self.assertIsNone(risk)

    # ── enforce: budget violation → REJECT ────────────────────────────────

    def test_budget_violation_enforcement(self):
        action = self._action("offer", 115.0)  # exceeds budget=110
        result, risk = self.judge.enforce(
            AgentRole.BUYER, action, self.buyer, self.seller,
            None, self.item, 1,
        )
        self.assertEqual(result.action, ActionType.REJECT)
        self.assertIsNotNone(risk)
        self.assertEqual(risk["violation_type"], "budget")

    # ── enforce: cost violation → REJECT ──────────────────────────────────

    def test_cost_violation_enforcement(self):
        action = self._action("offer", 75.0)  # below cost=80
        result, risk = self.judge.enforce(
            AgentRole.SELLER, action, self.buyer, self.seller,
            None, self.item, 1,
        )
        self.assertEqual(result.action, ActionType.REJECT)
        self.assertIsNotNone(risk)
        self.assertEqual(risk["violation_type"], "cost")

    # ── enforce: accept without prior offer → REJECT ──────────────────────

    def test_accept_without_offer_enforcement(self):
        action = self._action("accept")
        result, risk = self.judge.enforce(
            AgentRole.BUYER, action, self.buyer, self.seller,
            None, self.item, 2,  # round > 0 so first-round correction skipped
        )
        self.assertEqual(result.action, ActionType.REJECT)
        self.assertIsNotNone(risk)
        self.assertEqual(risk["violation_type"], "logic")

    # ── enforce integrates first-round correction ─────────────────────────

    def test_enforce_corrects_first_round_then_validates(self):
        """COUNTER on round 0 should be corrected to OFFER, then validated."""
        action = self._action("counter", 90.0)
        result, risk = self.judge.enforce(
            AgentRole.BUYER, action, self.buyer, self.seller,
            None, self.item, 0,
        )
        self.assertEqual(result.action, ActionType.OFFER)
        self.assertIsNone(risk)  # 90.0 is within budget

    # ── enforce: bounds violation ─────────────────────────────────────────

    def test_price_above_max_bound(self):
        action = self._action("offer", 600.0)
        result, risk = self.judge.enforce(
            AgentRole.SELLER, action, self.buyer, self.seller,
            None, self.item, 1,
        )
        self.assertEqual(result.action, ActionType.REJECT)
        self.assertEqual(risk["violation_type"], "bounds")


if __name__ == "__main__":
    unittest.main()
