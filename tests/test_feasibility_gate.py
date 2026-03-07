"""Tests for the deterministic acceptance pipeline (Req 5).

Tests:
  a) valid ACCEPT JSON is parsed correctly by call_llm_and_parse
  b) invalid JSON → repair → valid ACCEPT JSON returned
  c) invalid JSON twice → fallback; fallback ACCEPTs when offer is feasible
  d) feasibility override: agent returns REJECT but simulator settles (ACCEPT)
  e) settlement gate: agent.decide() is NOT called when gate fires
"""
from __future__ import annotations

import unittest
from typing import Optional

from src.agents.base import BaseAgent
from src.agents.llm_utils import call_llm_and_parse, fallback_action
from src.core.types import (
    ActionType,
    AgentContext,
    AgentRole,
    BuyerState,
    Item,
    NegotiationAction,
    SellerState,
)
from src.negotiation.feasibility import compute_utility, is_offer_feasible
from src.negotiation.session import NegotiationSession


# ── helpers ──────────────────────────────────────────────────────────────────

def _item():
    return Item("i1", "Widget", 100.0)


def _buyer(value=120.0, budget=130.0):
    return BuyerState("b1", value=value, budget=budget, patience=5)


def _seller(cost=80.0, margin=0.15):
    return SellerState("s1", cost=cost, target_margin=margin, patience=5)


def _buyer_ctx(last_offer=None, round_number=2, value=120.0, budget=130.0):
    return AgentContext(
        item=_item(),
        role=AgentRole.BUYER,
        round_number=round_number,
        max_rounds=10,
        history=[],
        last_offer=last_offer,
        reservation_price=value,
        budget=budget,
    )


class _MockBackend:
    """Fake LLM backend that returns pre-set responses in order."""

    def __init__(self, responses: list[str]):
        self._responses = list(responses)
        self._idx = 0
        self.call_count = 0

    def generate(self, prompt: str, **_) -> str:
        self.call_count += 1
        if self._idx < len(self._responses):
            resp = self._responses[self._idx]
            self._idx += 1
            return resp
        return ""  # blank after responses exhausted


class _MockAgent(BaseAgent):
    """Agent that always returns a fixed action; counts decide() calls."""

    def __init__(self, action: NegotiationAction):
        self._action = action
        self.decide_count = 0

    @property
    def agent_type(self) -> str:
        return "mock"

    def decide(self, ctx: AgentContext) -> NegotiationAction:
        self.decide_count += 1
        return self._action


def _counter_action(price: float) -> NegotiationAction:
    return NegotiationAction(ActionType.COUNTER, price, "Counter.", "r")


def _offer_action(price: float) -> NegotiationAction:
    return NegotiationAction(ActionType.OFFER, price, "Offer.", "r")


def _reject_action() -> NegotiationAction:
    return NegotiationAction(ActionType.REJECT, None, "Reject.", "r")


# ── Test a: valid ACCEPT JSON parsed correctly ────────────────────────────────

class TestValidAcceptJSON(unittest.TestCase):
    """(a) A well-formed ACCEPT JSON goes through call_llm_and_parse cleanly."""

    def test_valid_accept_parsed(self):
        valid_accept = (
            '{"action": "accept", "offer_price": null, '
            '"message_public": "Deal!", "rationale_private": "within limits"}'
        )
        backend = _MockBackend([valid_accept])
        ctx = _buyer_ctx(last_offer=90.0)
        result = call_llm_and_parse(backend, "prompt", ctx)
        self.assertEqual(result.action, ActionType.ACCEPT)
        self.assertIsNone(result.offer_price)
        self.assertEqual(backend.call_count, 1)


# ── Test b: invalid JSON → repair → valid ACCEPT ──────────────────────────────

class TestInvalidJSONRepair(unittest.TestCase):
    """(b) First response is garbage; retry returns a valid ACCEPT."""

    def test_repair_retry_yields_accept(self):
        garbage = "I think I should accept the offer."
        valid_accept = (
            '{"action": "accept", "offer_price": null, '
            '"message_public": "OK", "rationale_private": "repaired"}'
        )
        backend = _MockBackend([garbage, valid_accept])
        ctx = _buyer_ctx(last_offer=90.0)
        result = call_llm_and_parse(backend, "prompt", ctx)
        self.assertEqual(result.action, ActionType.ACCEPT)
        # Both first attempt and retry were made
        self.assertEqual(backend.call_count, 2)


# ── Test c: invalid JSON twice → fallback ─────────────────────────────────────

class TestInvalidJSONTwiceFallback(unittest.TestCase):
    """(c) Both attempts produce garbage; fallback fires and ACCEPTs when feasible."""

    def test_double_invalid_fallback_accepts_feasible_offer(self):
        garbage = "Let me think about it..."
        backend = _MockBackend([garbage, garbage])
        # Buyer: value=120, budget=130, last_offer=90 → clearly feasible
        ctx = _buyer_ctx(last_offer=90.0, value=120.0, budget=130.0)
        result = call_llm_and_parse(backend, "prompt", ctx)
        # fallback_action sees last_offer=90 <= cap=120 → returns ACCEPT
        self.assertEqual(result.action, ActionType.ACCEPT)
        self.assertEqual(backend.call_count, 2)

    def test_double_invalid_fallback_counters_when_infeasible(self):
        garbage = "No deal."
        backend = _MockBackend([garbage, garbage])
        # Buyer: value=80, budget=85, last_offer=95 → infeasible (95 > 80)
        ctx = _buyer_ctx(last_offer=95.0, value=80.0, budget=85.0)
        result = call_llm_and_parse(backend, "prompt", ctx)
        # fallback_action: 95 > cap=80 → counter with a price
        self.assertIn(result.action, (ActionType.COUNTER, ActionType.OFFER))
        self.assertIsNotNone(result.offer_price)


# ── Test d: feasibility override when agent rejects ──────────────────────────

class TestFeasibilityOverride(unittest.TestCase):
    """(d) Agent returns REJECT for a feasible offer → session produces ACCEPT."""

    def _run_session(self, seller_offer: float, buyer_value: float, buyer_budget: float):
        """Run a 2-round session: seller opens, buyer gate/override fires.

        Seller cost is intentionally set above the buyer's corrected opening
        offer (buyer_value * 0.5) so the gate does not fire on the seller's
        round 1 turn — only on the buyer's round 2 turn.
        """
        buyer = _buyer(value=buyer_value, budget=buyer_budget)
        # seller.cost = 80 > buyer opening offer (120*0.5=60) so gate
        # doesn't fire when it's the seller's turn to evaluate the buyer's offer.
        seller = _seller(cost=80.0)
        item = _item()

        # Seller agent opens at seller_offer; buyer agent always rejects
        seller_agent = _MockAgent(_offer_action(seller_offer))
        # After the seller's opening offer, it's buyer's turn.
        # Buyer agent would reject, but feasibility gate/override should override.
        buyer_agent = _MockAgent(_reject_action())

        session = NegotiationSession(
            buyer_agent, seller_agent, item, buyer, seller, max_rounds=10,
        )
        return session.run()

    def test_reject_overridden_to_accept_when_feasible(self):
        # Seller opens at $100; buyer value=$120 budget=$130 → feasible
        result = self._run_session(
            seller_offer=100.0, buyer_value=120.0, buyer_budget=130.0,
        )
        self.assertTrue(result.deal_made)
        self.assertEqual(result.termination_reason.value, "accepted")
        self.assertAlmostEqual(result.deal_price, 100.0)

    def test_no_override_when_offer_infeasible(self):
        # Seller opens at $150; buyer value=$120 → infeasible, reject stands
        result = self._run_session(
            seller_offer=150.0, buyer_value=120.0, buyer_budget=130.0,
        )
        # Buyer rejects → no deal
        self.assertFalse(result.deal_made)

    def test_correct_surplus_after_override(self):
        result = self._run_session(
            seller_offer=100.0, buyer_value=120.0, buyer_budget=130.0,
        )
        self.assertAlmostEqual(result.buyer_surplus, 20.0)   # 120 - 100
        self.assertAlmostEqual(result.seller_surplus, 20.0)  # 100 - 80 (seller.cost=80)


# ── Test e: settlement gate skips agent.decide() ─────────────────────────────

class TestSettlementGateSkipsLLM(unittest.TestCase):
    """(e) Settlement gate fires before agent.decide() when offer is feasible."""

    def test_buyer_agent_not_called_when_gate_fires(self):
        buyer = _buyer(value=120.0, budget=130.0)
        # cost=80 > buyer's opening offer ($70) so gate doesn't fire on
        # seller's round-1 turn, only on buyer's round-2 turn.
        seller = _seller(cost=80.0)
        item = _item()

        # Buyer opens at $70 (round 0); seller counters at $100 (round 1).
        # On round 2 the buyer's gate fires: $100 <= cap $120 → ACCEPT.
        buyer_agent = _MockAgent(_offer_action(70.0))
        seller_agent = _MockAgent(_offer_action(100.0))

        session = NegotiationSession(
            buyer_agent, seller_agent, item, buyer, seller, max_rounds=10,
        )
        result = session.run()

        # Deal was made (gate fired on round 2)
        self.assertTrue(result.deal_made)
        # buyer_agent.decide() called once (round 0 opening offer only),
        # NOT a second time because the gate fires on round 2.
        self.assertEqual(buyer_agent.decide_count, 1)
        # seller_agent.decide() called once (round 1)
        self.assertEqual(seller_agent.decide_count, 1)

    def test_gate_does_not_fire_when_offer_infeasible(self):
        buyer = _buyer(value=100.0, budget=105.0)
        seller = _seller(cost=60.0)
        item = _item()

        # Seller opens at $120 — above buyer's cap of $100
        seller_agent = _MockAgent(_offer_action(120.0))
        # Buyer rejects (nothing feasible to accept)
        buyer_agent = _MockAgent(_reject_action())

        session = NegotiationSession(
            buyer_agent, seller_agent, item, buyer, seller, max_rounds=10,
        )
        result = session.run()

        # Gate did not fire; buyer agent was called on round 0 (opens) and
        # round 2 (rejects).
        self.assertFalse(result.deal_made)
        # Round 0: buyer.decide() called to open
        # Round 2: buyer.decide() called, returns REJECT → no deal
        self.assertGreaterEqual(buyer_agent.decide_count, 1)


# ── Test for feasibility module directly ─────────────────────────────────────

class TestFeasibilityModule(unittest.TestCase):
    """Direct unit tests for compute_utility and is_offer_feasible."""

    def setUp(self):
        self.buyer = _buyer(value=120.0, budget=130.0)
        self.seller = _seller(cost=80.0)

    def test_buyer_utility_positive(self):
        u = compute_utility(AgentRole.BUYER, 90.0, self.buyer, self.seller)
        self.assertAlmostEqual(u, 30.0)  # 120 - 90

    def test_seller_utility_positive(self):
        u = compute_utility(AgentRole.SELLER, 100.0, self.buyer, self.seller)
        self.assertAlmostEqual(u, 20.0)  # 100 - 80

    def test_buyer_feasible_within_cap(self):
        ok, reason = is_offer_feasible(AgentRole.BUYER, 110.0, self.buyer, self.seller)
        self.assertTrue(ok)
        self.assertIn("utility=", reason)

    def test_buyer_infeasible_above_cap(self):
        ok, _ = is_offer_feasible(AgentRole.BUYER, 135.0, self.buyer, self.seller)
        self.assertFalse(ok)

    def test_seller_feasible_above_cost(self):
        ok, reason = is_offer_feasible(AgentRole.SELLER, 85.0, self.buyer, self.seller)
        self.assertTrue(ok)
        self.assertIn("utility=", reason)

    def test_seller_infeasible_below_cost(self):
        ok, _ = is_offer_feasible(AgentRole.SELLER, 75.0, self.buyer, self.seller)
        self.assertFalse(ok)

    def test_boundary_exactly_at_cap(self):
        # buyer cap = min(120, 130) = 120; offer at exactly 120 → feasible
        ok, _ = is_offer_feasible(AgentRole.BUYER, 120.0, self.buyer, self.seller)
        self.assertTrue(ok)

    def test_boundary_exactly_at_cost(self):
        # seller cost = 80; offer at exactly 80 → feasible (utility=0)
        ok, _ = is_offer_feasible(AgentRole.SELLER, 80.0, self.buyer, self.seller)
        self.assertTrue(ok)


if __name__ == "__main__":
    unittest.main()
