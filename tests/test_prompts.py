"""Tests for the redesigned prompt system (prompt-redesign branch)."""
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
    _deadline_hint,
    _decision_hint,
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
        self.assertIn("R7", result)
        self.assertIn("R8", result)
        self.assertIn("R9", result)
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


class TestDecisionHint(unittest.TestCase):

    def test_no_offer_yet(self):
        ctx = _make_ctx(last_offer=None)
        hint = _decision_hint(ctx)
        self.assertIn("opening offer", hint.lower())

    def test_buyer_acceptable_offer(self):
        ctx = _make_ctx(role=AgentRole.BUYER, last_offer=90.0, value=120.0, budget=130.0)
        hint = _decision_hint(ctx)
        self.assertIn("$90.00", hint)
        self.assertIn("$120.00", hint)
        self.assertIn("accept", hint.lower())
        self.assertIn("never counter above", hint.lower())

    def test_buyer_unacceptable_offer(self):
        ctx = _make_ctx(role=AgentRole.BUYER, last_offer=150.0, value=120.0, budget=130.0)
        hint = _decision_hint(ctx)
        self.assertIn("$150.00", hint)
        self.assertIn("$120.00", hint)
        self.assertIn("exceeds", hint.lower())

    def test_seller_acceptable_offer(self):
        ctx = _make_ctx(role=AgentRole.SELLER, last_offer=90.0, value=80.0, target_margin=0.15)
        hint = _decision_hint(ctx)
        self.assertIn("$90.00", hint)
        self.assertIn("$80.00", hint)
        self.assertIn("accept", hint.lower())
        self.assertIn("never counter below", hint.lower())

    def test_seller_unacceptable_offer(self):
        ctx = _make_ctx(role=AgentRole.SELLER, last_offer=70.0, value=80.0, target_margin=0.15)
        hint = _decision_hint(ctx)
        self.assertIn("$70.00", hint)
        self.assertIn("$80.00", hint)
        self.assertIn("below your minimum", hint.lower())


class TestReactivePrompt(unittest.TestCase):

    def test_contains_required_fields(self):
        ctx = _make_ctx()
        prompt = build_reactive_prompt(ctx)
        self.assertIn("Round 1 of 10", prompt)
        self.assertIn("Widget A", prompt)
        self.assertIn("$120.00", prompt)  # buyer's max price
        self.assertIn(SYSTEM_PROMPT, prompt)
        self.assertIn("JSON", prompt)

    def test_buyer_constraint_shown(self):
        ctx = _make_ctx(role=AgentRole.BUYER, value=120.0, budget=130.0)
        prompt = build_reactive_prompt(ctx)
        self.assertIn("BUYER", prompt)
        self.assertIn("maximum price", prompt.lower())
        self.assertIn("$120.00", prompt)

    def test_seller_constraint_shown(self):
        ctx = _make_ctx(role=AgentRole.SELLER, value=80.0, target_margin=0.15)
        prompt = build_reactive_prompt(ctx)
        self.assertIn("SELLER", prompt)
        self.assertIn("minimum price", prompt.lower())
        self.assertIn("$80.00", prompt)

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
        self.assertIn("History:", prompt)
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

    def test_hint_shows_offer_and_limit(self):
        ctx = _make_ctx(role=AgentRole.BUYER, last_offer=90.0, value=120.0, budget=130.0)
        prompt = build_reactive_prompt(ctx)
        self.assertIn("$90.00", prompt)
        self.assertIn("$120.00", prompt)
        self.assertIn("accept", prompt.lower())

    def test_hint_directional_guidance(self):
        """Decision hint should guide counter direction to prevent irrational offers."""
        ctx = _make_ctx(role=AgentRole.BUYER, last_offer=90.0, value=120.0, budget=130.0)
        prompt = build_reactive_prompt(ctx)
        hint_area = prompt.split("History:")[0]
        self.assertIn("NEVER counter above", hint_area)
        self.assertIn("counter BELOW", hint_area)

    def test_communication_strategy(self):
        ctx = _make_ctx()
        pcfg = PromptConfig(communication_strategy="assertive")
        prompt = build_reactive_prompt(ctx, prompt_cfg=pcfg)
        self.assertIn("COMMUNICATION STRATEGY", prompt)

    def test_no_hardcoded_concession_schedule(self):
        """Prompt should NOT contain hard-coded concession amounts."""
        ctx = _make_ctx()
        prompt = build_reactive_prompt(ctx)
        self.assertNotIn("increase your price by", prompt)
        self.assertNotIn("decrease your price by", prompt)


class TestDeliberativePrompt(unittest.TestCase):

    def test_contains_reasoning_scaffold(self):
        ctx = _make_ctx()
        prompt = build_deliberative_prompt(ctx)
        self.assertIn("rationale_private", prompt)
        self.assertIn("acceptable", prompt.lower())

    def test_contains_required_fields(self):
        ctx = _make_ctx()
        prompt = build_deliberative_prompt(ctx)
        self.assertIn("Round 1 of 10", prompt)
        self.assertIn(SYSTEM_PROMPT, prompt)
        self.assertIn("JSON", prompt)

    def test_prompt_cfg_passthrough(self):
        ctx = _make_ctx()
        pcfg = PromptConfig(include_deadline_salience=False)
        prompt = build_deliberative_prompt(ctx, prompt_cfg=pcfg)
        # Should still have reasoning scaffold
        self.assertIn("rationale_private", prompt)


class TestDeadlineHint(unittest.TestCase):

    def test_final_round(self):
        ctx = _make_ctx(round_number=9, max_rounds=10)
        result = _deadline_hint(ctx)
        self.assertIn("FINAL ROUND", result)

    def test_near_end(self):
        ctx = _make_ctx(round_number=8, max_rounds=10)
        result = _deadline_hint(ctx)
        self.assertIn("WARNING", result)

    def test_approaching(self):
        ctx = _make_ctx(round_number=7, max_rounds=12)
        result = _deadline_hint(ctx)
        self.assertIn("conceding", result.lower())

    def test_early_round(self):
        ctx = _make_ctx(round_number=0, max_rounds=10)
        result = _deadline_hint(ctx)
        self.assertEqual(result, "")


# ═══════════════════════════════════════════════════════════════════════
#  Free-language mode tests
# ═══════════════════════════════════════════════════════════════════════

from src.llm.prompts import (
    build_free_language_prompt,
    _format_free_language_history,
)
from src.negotiation.parser import extract_price_from_text, detect_accept_intent


class TestFreeLanguageParser(unittest.TestCase):

    def test_extract_buyer_price_tag(self):
        text = "I can offer ### BUYER_PRICE($85.50) ### for this product."
        self.assertAlmostEqual(extract_price_from_text(text), 85.50)

    def test_extract_seller_price_tag(self):
        text = "How about ### SELLER_PRICE($140) ###?"
        self.assertAlmostEqual(extract_price_from_text(text), 140.0)

    def test_extract_tagged_price_no_space(self):
        text = "How about ###BUYER_PRICE($100)###?"
        self.assertAlmostEqual(extract_price_from_text(text), 100.0)

    def test_extract_tagged_price_with_spaces(self):
        text = "My offer: ### SELLER_PRICE( $ 72 ) ###"
        self.assertAlmostEqual(extract_price_from_text(text), 72.0)

    def test_extract_last_tagged_price(self):
        text = "I was thinking ### BUYER_PRICE($50) ### but actually ### BUYER_PRICE($60) ###"
        self.assertAlmostEqual(extract_price_from_text(text), 60.0)

    def test_fallback_bare_dollar(self):
        text = "I think $95 is a fair price."
        self.assertAlmostEqual(extract_price_from_text(text), 95.0)

    def test_no_price(self):
        text = "I need to think about it."
        self.assertIsNone(extract_price_from_text(text))

    def test_detect_make_deal(self):
        self.assertTrue(detect_accept_intent("I accept. MAKE_DEAL"))
        self.assertTrue(detect_accept_intent("MAKE_DEAL"))
        self.assertTrue(detect_accept_intent("Sounds good. make_deal"))

    def test_detect_accept_deal(self):
        self.assertTrue(detect_accept_intent("That works for me. ACCEPT_DEAL"))

    def test_detect_no_accept(self):
        self.assertFalse(detect_accept_intent("I need a better price."))
        self.assertFalse(detect_accept_intent("Let me make a deal-breaker point."))


class TestFreeLanguageBuyerPrompt(unittest.TestCase):

    def test_contains_buyer_elements(self):
        ctx = _make_ctx(role=AgentRole.BUYER)
        prompt = build_free_language_prompt(ctx)
        self.assertIn("Buyer", prompt)
        self.assertIn("$120.00", prompt)  # reservation price
        self.assertIn("### BUYER_PRICE($", prompt)
        self.assertIn("MAKE_DEAL", prompt)
        self.assertIn("Round 1 of 10", prompt)

    def test_no_json_schema(self):
        ctx = _make_ctx(role=AgentRole.BUYER)
        prompt = build_free_language_prompt(ctx)
        self.assertNotIn('"action":', prompt)
        self.assertNotIn("offer_price", prompt)

    def test_buyer_does_not_reveal_limit_instruction(self):
        ctx = _make_ctx(role=AgentRole.BUYER)
        prompt = build_free_language_prompt(ctx)
        self.assertIn("confidential", prompt.lower())
        self.assertIn("do not reveal", prompt.lower())


class TestFreeLanguageSellerPrompt(unittest.TestCase):

    def test_contains_seller_elements(self):
        ctx = _make_ctx(role=AgentRole.SELLER, value=80.0, target_margin=0.15)
        prompt = build_free_language_prompt(ctx)
        self.assertIn("Seller", prompt)
        self.assertIn("$80.00", prompt)  # min price
        self.assertIn("### SELLER_PRICE($", prompt)

    def test_includes_initial_asking_price(self):
        ctx = _make_ctx(role=AgentRole.SELLER, value=80.0, target_margin=0.15)
        prompt = build_free_language_prompt(ctx)
        # initial_price = 80 * (1 + 2*0.15) = 80 * 1.3 = 104
        self.assertIn("$104.00", prompt)

    def test_includes_conversation_history(self):
        history = [
            _make_turn(0, AgentRole.BUYER, ActionType.OFFER, 60.0),
        ]
        ctx = _make_ctx(
            role=AgentRole.SELLER, value=80.0, target_margin=0.15,
            round_number=1, history=history, last_offer=60.0,
        )
        prompt = build_free_language_prompt(ctx)
        self.assertIn("Conversation History:", prompt)
        self.assertIn("[Round 1] BUYER:", prompt)


class TestFreeLanguageHistoryFormat(unittest.TestCase):

    def test_empty_history(self):
        result = _format_free_language_history([])
        self.assertIn("no conversation yet", result)

    def test_formats_turns(self):
        history = [
            _make_turn(0, AgentRole.BUYER, ActionType.OFFER, 60.0),
            _make_turn(1, AgentRole.SELLER, ActionType.COUNTER, 95.0),
        ]
        result = _format_free_language_history(history)
        self.assertIn("[Round 1] BUYER:", result)
        self.assertIn("[Round 2] SELLER:", result)


if __name__ == "__main__":
    unittest.main()
