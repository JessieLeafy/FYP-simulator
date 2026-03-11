"""Tests for the LLM pipeline and session behavior (prompt-redesign branch).

Tests:
  a) valid ACCEPT JSON is parsed correctly by call_llm_and_parse
  b) invalid JSON → rethink → valid JSON returned
  c) invalid JSON twice → no rescue; REJECT returned
  d) infeasible action → rethink → corrected action returned
  e) gate disabled by default: LLM decisions are not overridden
  f) feasibility module direct tests (unchanged)
"""
from __future__ import annotations

import unittest

from src.agents.base import BaseAgent
from src.agents.llm_utils import call_llm_and_parse, _check_feasibility
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


def _seller_ctx(last_offer=None, round_number=1, cost=80.0):
    return AgentContext(
        item=_item(),
        role=AgentRole.SELLER,
        round_number=round_number,
        max_rounds=10,
        history=[],
        last_offer=last_offer,
        reservation_price=cost,
        target_margin=0.15,
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
        return ""


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


def _offer_action(price: float) -> NegotiationAction:
    return NegotiationAction(ActionType.OFFER, price, "Offer.", "r")


def _counter_action(price: float) -> NegotiationAction:
    return NegotiationAction(ActionType.COUNTER, price, "Counter.", "r")


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


# ── Test b: invalid JSON → rethink → valid output ────────────────────────────

class TestInvalidJSONRethink(unittest.TestCase):
    """(b) First response is garbage; rethink returns valid JSON."""

    def test_rethink_yields_accept(self):
        garbage = "I think I should accept the offer."
        valid_accept = (
            '{"action": "accept", "offer_price": null, '
            '"message_public": "OK", "rationale_private": "repaired"}'
        )
        backend = _MockBackend([garbage, valid_accept])
        ctx = _buyer_ctx(last_offer=90.0)
        result = call_llm_and_parse(backend, "prompt", ctx)
        self.assertEqual(result.action, ActionType.ACCEPT)
        self.assertEqual(backend.call_count, 2)


# ── Test c: invalid JSON twice → REJECT (no rescue) ──────────────────────────

class TestInvalidJSONTwiceNoRescue(unittest.TestCase):
    """(c) Both attempts produce garbage; pipeline returns REJECT, no rescue."""

    def test_double_invalid_returns_reject(self):
        garbage = "Let me think about it..."
        backend = _MockBackend([garbage, garbage])
        ctx = _buyer_ctx(last_offer=90.0, value=120.0, budget=130.0)
        result = call_llm_and_parse(backend, "prompt", ctx)
        # No fallback rescue — should be REJECT
        self.assertEqual(result.action, ActionType.REJECT)
        self.assertEqual(backend.call_count, 2)

    def test_double_invalid_no_deal_price(self):
        garbage = "No way"
        backend = _MockBackend([garbage, garbage])
        ctx = _buyer_ctx(last_offer=90.0, value=120.0, budget=130.0)
        result = call_llm_and_parse(backend, "prompt", ctx)
        self.assertIsNone(result.offer_price)


# ── Test d: infeasible action → rethink → corrected ──────────────────────────

class TestInfeasibleActionRethink(unittest.TestCase):
    """(d) Valid JSON but constraint-violating → rethink → corrected."""

    def test_buyer_over_budget_triggers_rethink(self):
        # Buyer offers $150 but cap is $120 → infeasible → rethink
        over_budget = (
            '{"action": "counter", "offer_price": 150, '
            '"message_public": "hi", "rationale_private": "r"}'
        )
        corrected = (
            '{"action": "counter", "offer_price": 110, '
            '"message_public": "ok", "rationale_private": "fixed"}'
        )
        backend = _MockBackend([over_budget, corrected])
        ctx = _buyer_ctx(last_offer=130.0, value=120.0, budget=130.0)
        result = call_llm_and_parse(backend, "prompt", ctx)
        self.assertEqual(result.action, ActionType.COUNTER)
        self.assertEqual(result.offer_price, 110)
        self.assertEqual(backend.call_count, 2)

    def test_seller_below_cost_triggers_rethink(self):
        # Seller offers $70 but cost is $80 → infeasible → rethink
        below_cost = (
            '{"action": "counter", "offer_price": 70, '
            '"message_public": "low", "rationale_private": "r"}'
        )
        corrected = (
            '{"action": "counter", "offer_price": 90, '
            '"message_public": "ok", "rationale_private": "fixed"}'
        )
        backend = _MockBackend([below_cost, corrected])
        ctx = _seller_ctx(last_offer=60.0, cost=80.0)
        result = call_llm_and_parse(backend, "prompt", ctx)
        self.assertEqual(result.action, ActionType.COUNTER)
        self.assertEqual(result.offer_price, 90)
        self.assertEqual(backend.call_count, 2)

    def test_infeasible_twice_passes_through(self):
        """If rethink is also infeasible, pass through to judge."""
        below_cost = (
            '{"action": "counter", "offer_price": 70, '
            '"message_public": "low", "rationale_private": "r"}'
        )
        still_below = (
            '{"action": "counter", "offer_price": 75, '
            '"message_public": "still low", "rationale_private": "r"}'
        )
        backend = _MockBackend([below_cost, still_below])
        ctx = _seller_ctx(last_offer=60.0, cost=80.0)
        result = call_llm_and_parse(backend, "prompt", ctx)
        # Passed through — judge will reject this later
        self.assertEqual(result.action, ActionType.COUNTER)
        self.assertEqual(result.offer_price, 75)
        self.assertEqual(backend.call_count, 2)


# ── Test e: gate disabled by default ─────────────────────────────────────────

class TestGateDisabledByDefault(unittest.TestCase):
    """(e) Session does not override LLM decisions when gate is off."""

    def test_reject_not_overridden_when_gate_off(self):
        """Agent REJECTs a feasible offer → session respects the REJECT."""
        buyer = _buyer(value=120.0, budget=130.0)
        seller = _seller(cost=80.0)
        item = _item()

        # Seller opens at $100 (feasible for buyer); buyer rejects
        seller_agent = _MockAgent(_offer_action(100.0))
        buyer_agent = _MockAgent(_reject_action())

        session = NegotiationSession(
            buyer_agent, seller_agent, item, buyer, seller,
            max_rounds=10,
            gate_enabled=False,  # explicit, matches new default
        )
        result = session.run()

        # Buyer rejected → no deal (not overridden)
        self.assertFalse(result.deal_made)
        self.assertEqual(result.termination_reason.value, "rejected")

    def test_agent_always_called_when_gate_off(self):
        """Both agents are always called (no pre-LLM gate skip)."""
        buyer = _buyer(value=120.0, budget=130.0)
        seller = _seller(cost=80.0)
        item = _item()

        buyer_agent = _MockAgent(_offer_action(70.0))
        seller_agent = _MockAgent(_offer_action(100.0))

        session = NegotiationSession(
            buyer_agent, seller_agent, item, buyer, seller,
            max_rounds=4,
            gate_enabled=False,
        )
        result = session.run()

        # With gate off, agents are called every round
        # Round 0: buyer (offer 70), Round 1: seller (offer 100),
        # Round 2: buyer (offer 70 again), Round 3: seller (offer 100 again)
        # → timeout (neither accepts)
        self.assertFalse(result.deal_made)
        self.assertEqual(result.termination_reason.value, "timeout")
        self.assertEqual(buyer_agent.decide_count, 2)
        self.assertEqual(seller_agent.decide_count, 2)


# ── Test: feasibility check utility ──────────────────────────────────────────

class TestCheckFeasibility(unittest.TestCase):
    """Unit tests for the _check_feasibility function in llm_utils."""

    def test_buyer_valid_offer(self):
        ctx = _buyer_ctx(last_offer=None, value=120.0, budget=130.0)
        action = NegotiationAction(ActionType.OFFER, 100.0, "", "")
        self.assertIsNone(_check_feasibility(action, ctx))

    def test_buyer_over_cap(self):
        ctx = _buyer_ctx(last_offer=None, value=120.0, budget=130.0)
        action = NegotiationAction(ActionType.COUNTER, 150.0, "", "")
        error = _check_feasibility(action, ctx)
        self.assertIsNotNone(error)
        self.assertIn("150.00", error)

    def test_seller_below_cost(self):
        ctx = _seller_ctx(last_offer=None, cost=80.0)
        action = NegotiationAction(ActionType.COUNTER, 70.0, "", "")
        error = _check_feasibility(action, ctx)
        self.assertIsNotNone(error)
        self.assertIn("70.00", error)

    def test_accept_without_prior_offer(self):
        ctx = _buyer_ctx(last_offer=None)
        action = NegotiationAction(ActionType.ACCEPT, None, "", "")
        error = _check_feasibility(action, ctx)
        self.assertIsNotNone(error)

    def test_accept_within_limits(self):
        ctx = _buyer_ctx(last_offer=90.0, value=120.0, budget=130.0)
        action = NegotiationAction(ActionType.ACCEPT, None, "", "")
        self.assertIsNone(_check_feasibility(action, ctx))


# ── Test: feasibility module directly (unchanged) ────────────────────────────

class TestFeasibilityModule(unittest.TestCase):
    """Direct unit tests for compute_utility and is_offer_feasible."""

    def setUp(self):
        self.buyer = _buyer(value=120.0, budget=130.0)
        self.seller = _seller(cost=80.0)

    def test_buyer_utility_positive(self):
        u = compute_utility(AgentRole.BUYER, 90.0, self.buyer, self.seller)
        self.assertAlmostEqual(u, 30.0)

    def test_seller_utility_positive(self):
        u = compute_utility(AgentRole.SELLER, 100.0, self.buyer, self.seller)
        self.assertAlmostEqual(u, 20.0)

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
        ok, _ = is_offer_feasible(AgentRole.BUYER, 120.0, self.buyer, self.seller)
        self.assertTrue(ok)

    def test_boundary_exactly_at_cost(self):
        ok, _ = is_offer_feasible(AgentRole.SELLER, 80.0, self.buyer, self.seller)
        self.assertTrue(ok)


if __name__ == "__main__":
    unittest.main()
