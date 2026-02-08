"""LLM-powered reactive negotiation agent."""
from __future__ import annotations

import logging
from typing import Optional

from src.agents.base import BaseAgent
from src.core.types import (
    ActionType,
    AgentContext,
    AgentRole,
    NegotiationAction,
)
from src.llm.backend import OllamaLLMBackend
from src.llm.prompts import build_reactive_prompt
from src.llm.schemas import FORMAT_ERROR_PROMPT
from src.negotiation.parser import extract_json, validate_action_json

logger = logging.getLogger(__name__)


class LLMReactiveAgent(BaseAgent):
    """Single-shot LLM agent: prompt → JSON action."""

    def __init__(self, backend: OllamaLLMBackend):
        self._backend = backend

    @property
    def agent_type(self) -> str:
        return "llm_reactive"

    def decide(self, ctx: AgentContext) -> NegotiationAction:
        prompt = build_reactive_prompt(ctx)
        return self._call_and_parse(prompt, ctx)

    def _call_and_parse(
        self, prompt: str, ctx: AgentContext
    ) -> NegotiationAction:
        # ── first attempt ────────────────────────────────────────────────
        raw = self._backend.generate(prompt)
        parsed = extract_json(raw)

        if parsed is not None:
            valid, reason = validate_action_json(parsed)
            if valid:
                return _to_action(parsed)
            logger.warning("JSON validation failed: %s", reason)
        else:
            logger.warning("Failed to extract JSON from LLM response")

        # ── retry with format-error nudge ────────────────────────────────
        retry_prompt = prompt + "\n\n" + FORMAT_ERROR_PROMPT
        raw = self._backend.generate(retry_prompt)
        parsed = extract_json(raw)

        if parsed is not None:
            valid, reason = validate_action_json(parsed)
            if valid:
                return _to_action(parsed)

        # ── fallback ─────────────────────────────────────────────────────
        logger.error(
            "LLM failed to produce valid JSON after retry – using fallback"
        )
        return _fallback_action(ctx)


# ── helpers ──────────────────────────────────────────────────────────────────

def _to_action(obj: dict) -> NegotiationAction:
    return NegotiationAction(
        action=ActionType(obj["action"]),
        offer_price=obj.get("offer_price"),
        message_public=obj.get("message_public", ""),
        rationale_private=obj.get("rationale_private", ""),
    )


def _fallback_action(ctx: AgentContext) -> NegotiationAction:
    """Produce a safe default when the LLM cannot be parsed."""
    if ctx.round_number == 0:
        if ctx.role == AgentRole.BUYER:
            price = ctx.reservation_price * 0.6
            if ctx.budget is not None:
                price = min(price, ctx.budget)
        else:
            price = ctx.reservation_price * 1.3
        return NegotiationAction(
            ActionType.OFFER,
            round(price, 2),
            "Here's my opening offer.",
            "Fallback: LLM parsing failure.",
        )
    return NegotiationAction(
        ActionType.REJECT, None,
        "I'll have to pass.",
        "Fallback: LLM parsing failure.",
    )
