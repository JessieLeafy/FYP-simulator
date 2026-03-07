"""Tests for the upgraded prompt engineering system (Upgrade A)."""
import unittest

from src.core.config import PromptConfig
from src.core.types import (
    ActionType,
    AgentContext,
    AgentRole,
    Item,
    NegotiationAction,
    NegotiationTurn,
)
from src.llm.prompts import (
    SYSTEM_PROMPT,
    _deadline_salience,
    build_deliberative_prompt,
    build_reactive_prompt,
    summarise_history,
)


def _make_ctx(
    role=AgentRole.BUYER,
    round_number=0,
    max_rounds=10,
    last_offer=None,
    history=None,
    value=120.0,
    budget=130.0,
    target_margin=None,
):
    return AgentContext(
        item=Item("i1", "Widget A", 100.0),
        role=role,
        round_number=round_number,
        max_rounds=max_rounds,
        history=history or [],
        last_offer=last_offer,
        reservation_price=value,
        budget=budget if role == AgentRole.BUYER else None,
        target_margin=target_margin if role == AgentRole.SELLER else None,
    )


def _make_turn(round_num, role, action_type, price=None):
    return NegotiationTurn(
        round_number=round_num,
        agent_role=role,
        action=NegotiationAction(
            action=action_type,
            offer_price=price,
            message_public="test",
            rationale_private="test",
        ),
    )


class TestSummariseHistory(unittest.TestCase):

    def test_empty_history(self):
        result = summarise_history([])
        self.assertEqual(result, "(no moves yet)")

    def test_single_turn(self):
        history = [_make_turn(0, AgentRole.BUYER, ActionType.OFFER, 60.0)]
        result = summarise_history(history)
        self.assertIn("R0", result)
        self.assertIn("buyer", result)
        self.assertIn("OFFER", result)
        self.assertIn("$60.00", result)

    def test_truncation(self):
        history = [
            _make_turn(i, AgentRole.BUYER if i % 2 == 0 else AgentRole.SELLER,
                       ActionType.OFFER if i == 0 else ActionType.COUNTER, 50.0 + i)
            for i in range(10)
        ]
        result = summarise_history(history, k=3)
        self.assertIn("omitted", result)
        # should contain the last 3 turns
        self.assertIn("R7", result)
        self.assertIn("R8", result)
        self.assertIn("R9", result)
        # should NOT contain early turns
        self.assertNotIn("R0 ", result)

    def test_no_price_turn(self):
        history = [_make_turn(0, AgentRole.BUYER, ActionType.REJECT, None)]
        result = summarise_history(history)
        self.assertIn("REJECT", result)
        self.assertNotIn("$", result)

    def test_deterministic(self):
        history = [
            _make_turn(0, AgentRole.BUYER, ActionType.OFFER, 60.0),
            _make_turn(1, AgentRole.SELLER, ActionType.COUNTER, 95.0),
        ]
        r1 = summarise_history(history, k=6)
        r2 = summarise_history(history, k=6)
        self.assertEqual(r1, r2)


class TestReactivePrompt(unittest.TestCase):

    def test_contains_required_fields(self):
        ctx = _make_ctx()
        prompt = build_reactive_prompt(ctx)
        self.assertIn("Round 1 of 10", prompt)
        self.assertIn("Widget A", prompt)
        self.assertIn("$120.00", prompt)
        self.assertIn("$60.00", prompt)  # opening offer (50% of cap)
        self.assertIn(SYSTEM_PROMPT, prompt)
        self.assertIn("JSON", prompt)

    def test_contains_objective_by_default(self):
        ctx = _make_ctx()
        prompt = build_reactive_prompt(ctx)
        self.assertIn("buyer_surplus", prompt)
        self.assertIn("maximise", prompt)

    def test_objective_disabled(self):
        ctx = _make_ctx()
        pcfg = PromptConfig(include_objective_equations=False)
        prompt = build_reactive_prompt(ctx, prompt_cfg=pcfg)
        self.assertNotIn("Objective:", prompt)

    def test_seller_prompt(self):
        ctx = _make_ctx(
            role=AgentRole.SELLER, value=80.0, budget=None,
            target_margin=0.15,
        )
        prompt = build_reactive_prompt(ctx)
        self.assertIn("SELLER", prompt)
        self.assertIn("$80.00", prompt)
        self.assertIn("seller_surplus", prompt)

    def test_deadline_salience_final_round(self):
        ctx = _make_ctx(round_number=9, max_rounds=10)
        prompt = build_reactive_prompt(ctx)
        self.assertIn("FINAL ROUND", prompt)

    def test_deadline_salience_near_end(self):
        ctx = _make_ctx(round_number=7, max_rounds=10)
        prompt = build_reactive_prompt(ctx)
        self.assertIn("WARNING", prompt)

    def test_deadline_salience_disabled(self):
        ctx = _make_ctx(round_number=9, max_rounds=10)
        pcfg = PromptConfig(include_deadline_salience=False)
        prompt = build_reactive_prompt(ctx, prompt_cfg=pcfg)
        self.assertNotIn("FINAL ROUND", prompt)

    def test_history_summary_mode(self):
        history = [_make_turn(0, AgentRole.BUYER, ActionType.OFFER, 60.0)]
        ctx = _make_ctx(round_number=1, history=history, last_offer=60.0)
        prompt = build_reactive_prompt(ctx)
        self.assertIn("Transcript (recent):", prompt)
        self.assertIn("R0", prompt)

    def test_history_legacy_mode(self):
        history = [_make_turn(0, AgentRole.BUYER, ActionType.OFFER, 60.0)]
        ctx = _make_ctx(round_number=1, history=history, last_offer=60.0)
        pcfg = PromptConfig(include_history_summary=False)
        prompt = build_reactive_prompt(ctx, prompt_cfg=pcfg)
        self.assertIn("History:", prompt)
        self.assertIn("Round 0:", prompt)

    def test_tone_firm(self):
        ctx = _make_ctx()
        pcfg = PromptConfig(message_tone="firm")
        prompt = build_reactive_prompt(ctx, prompt_cfg=pcfg)
        self.assertIn("assertive", prompt)

    def test_prompt_determinism(self):
        history = [
            _make_turn(0, AgentRole.BUYER, ActionType.OFFER, 60.0),
            _make_turn(1, AgentRole.SELLER, ActionType.COUNTER, 95.0),
        ]
        ctx = _make_ctx(round_number=2, history=history, last_offer=95.0)
        p1 = build_reactive_prompt(ctx)
        p2 = build_reactive_prompt(ctx)
        self.assertEqual(p1, p2)


class TestDeliberativePrompt(unittest.TestCase):

    def test_contains_reasoning_steps(self):
        ctx = _make_ctx()
        prompt = build_deliberative_prompt(ctx)
        self.assertIn("BELIEFS", prompt)
        self.assertIn("TARGET", prompt)
        self.assertIn("STRATEGY", prompt)
        self.assertIn("ACTION", prompt)
        self.assertIn("rationale_private", prompt)

    def test_contains_required_fields(self):
        ctx = _make_ctx()
        prompt = build_deliberative_prompt(ctx)
        self.assertIn("Round 1 of 10", prompt)
        self.assertIn(SYSTEM_PROMPT, prompt)
        self.assertIn("JSON", prompt)

    def test_prompt_cfg_passthrough(self):
        ctx = _make_ctx()
        pcfg = PromptConfig(
            include_objective_equations=False,
            include_deadline_salience=False,
        )
        prompt = build_deliberative_prompt(ctx, prompt_cfg=pcfg)
        self.assertNotIn("Objective:", prompt)
        # Should still have reasoning steps
        self.assertIn("BELIEFS", prompt)


class TestDeadlineSalience(unittest.TestCase):

    def test_final_round(self):
        ctx = _make_ctx(round_number=9, max_rounds=10)
        result = _deadline_salience(ctx)
        self.assertIn("FINAL ROUND", result)

    def test_near_end(self):
        ctx = _make_ctx(round_number=8, max_rounds=10)
        result = _deadline_salience(ctx)
        self.assertIn("WARNING", result)

    def test_approaching(self):
        ctx = _make_ctx(round_number=7, max_rounds=12)
        result = _deadline_salience(ctx)
        self.assertIn("larger concessions", result)

    def test_early_round(self):
        ctx = _make_ctx(round_number=0, max_rounds=10)
        result = _deadline_salience(ctx)
        self.assertEqual(result, "")


if __name__ == "__main__":
    unittest.main()
