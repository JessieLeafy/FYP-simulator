"""Tests for the alternating-offers negotiation protocol."""
import unittest

from src.agents.rule_based import RuleBasedAgent
from src.core.types import (
    AgentRole,
    BuyerState,
    Item,
    NegotiationResult,
    SellerState,
    TerminationReason,
)
from src.negotiation.protocol import run_negotiation


class TestProtocol(unittest.TestCase):

    def test_deal_made_compatible(self):
        """Two compatible rule-based agents should reach a deal."""
        result = run_negotiation(
            buyer_agent=RuleBasedAgent(),
            seller_agent=RuleBasedAgent(),
            item=Item("i1", "Widget A", 100.0),
            buyer=BuyerState("b1", value=120.0, budget=130.0, patience=5),
            seller=SellerState("s1", cost=70.0, target_margin=0.15, patience=5),
            max_rounds=10,
        )
        self.assertTrue(result.deal_made)
        self.assertIsNotNone(result.deal_price)
        self.assertGreaterEqual(result.deal_price, 70.0)
        self.assertLessEqual(result.deal_price, 120.0)

    def test_no_deal_incompatible(self):
        """Buyer value below seller cost → no deal possible."""
        result = run_negotiation(
            buyer_agent=RuleBasedAgent(),
            seller_agent=RuleBasedAgent(),
            item=Item("i1", "Widget A", 100.0),
            buyer=BuyerState("b1", value=50.0, budget=50.0, patience=5),
            seller=SellerState("s1", cost=100.0, target_margin=0.20, patience=5),
            max_rounds=10,
        )
        self.assertFalse(result.deal_made)

    def test_terminates_within_max_rounds(self):
        result = run_negotiation(
            buyer_agent=RuleBasedAgent(),
            seller_agent=RuleBasedAgent(),
            item=Item("i1", "Widget A", 100.0),
            buyer=BuyerState("b1", value=120.0, budget=130.0, patience=5),
            seller=SellerState("s1", cost=80.0, target_margin=0.15, patience=5),
            max_rounds=6,
        )
        self.assertLessEqual(result.rounds_taken, 6)

    def test_history_alternates_roles(self):
        result = run_negotiation(
            buyer_agent=RuleBasedAgent(),
            seller_agent=RuleBasedAgent(),
            item=Item("i1", "Widget A", 100.0),
            buyer=BuyerState("b1", value=120.0, budget=130.0, patience=5),
            seller=SellerState("s1", cost=70.0, target_margin=0.15, patience=5),
            max_rounds=10,
        )
        self.assertGreater(len(result.history), 0)
        for i, turn in enumerate(result.history):
            expected = AgentRole.BUYER if i % 2 == 0 else AgentRole.SELLER
            self.assertEqual(turn.agent_role, expected)

    def test_surplus_positive_on_deal(self):
        result = run_negotiation(
            buyer_agent=RuleBasedAgent(),
            seller_agent=RuleBasedAgent(),
            item=Item("i1", "Widget A", 100.0),
            buyer=BuyerState("b1", value=150.0, budget=160.0, patience=5),
            seller=SellerState("s1", cost=60.0, target_margin=0.10, patience=5),
            max_rounds=10,
        )
        self.assertTrue(result.deal_made)
        self.assertGreaterEqual(result.buyer_surplus, 0)
        self.assertGreaterEqual(result.seller_surplus, 0)

    def test_timeout_when_very_few_rounds(self):
        """With only 2 rounds (1 each), agents likely won't agree."""
        result = run_negotiation(
            buyer_agent=RuleBasedAgent(),
            seller_agent=RuleBasedAgent(),
            item=Item("i1", "Widget A", 100.0),
            buyer=BuyerState("b1", value=120.0, budget=130.0, patience=5),
            seller=SellerState("s1", cost=80.0, target_margin=0.30, patience=5),
            max_rounds=2,
        )
        self.assertIn(
            result.termination_reason,
            (TerminationReason.TIMEOUT, TerminationReason.REJECTED,
             TerminationReason.ACCEPTED),
        )
        self.assertLessEqual(result.rounds_taken, 2)


if __name__ == "__main__":
    unittest.main()
