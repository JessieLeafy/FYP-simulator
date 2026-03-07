"""Shared utilities for LLM-based negotiation agents.

Provides the parse-validate-retry pipeline used by all LLM agent types.
These were previously private functions scattered across agent modules.
"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from src.core.types import (
    ActionType,
    AgentContext,
    AgentRole,
    NegotiationAction,
)
from src.llm.schemas import FORMAT_ERROR_PROMPT
from src.negotiation.parser import extract_json, validate_action_json

if TYPE_CHECKING:
    from src.llm.backend import OllamaLLMBackend

logger = logging.getLogger(__name__)


def to_action(obj: dict) -> NegotiationAction:
    """Convert a validated JSON dict to a NegotiationAction."""
    return NegotiationAction(
        action=ActionType(obj["action"]),
        offer_price=obj.get("offer_price"),
        message_public=obj.get("message_public", ""),
        rationale_private=obj.get("rationale_private", ""),
    )


def fallback_action(ctx: AgentContext) -> NegotiationAction:
    """Produce a safe default when the LLM output cannot be parsed.

    Uses a linear-concession strategy so negotiations make progress
    even when the LLM fails to produce valid JSON.
    """
    if ctx.role == AgentRole.BUYER:
        cap = min(ctx.reservation_price, ctx.budget or ctx.reservation_price)
        initial = cap * 0.5
        progress = ctx.round_number / max(ctx.max_rounds - 1, 1)
        price = round(min(initial + (cap - initial) * progress, cap), 2)
        # Accept if opponent's offer is within budget
        if ctx.last_offer is not None and ctx.last_offer <= cap:
            return NegotiationAction(
                ActionType.ACCEPT, None,
                "I accept your offer.",
                "Fallback: accepting within budget.",
            )
    else:
        cost = ctx.reservation_price
        margin = ctx.target_margin or 0.15
        initial = cost * (1 + 2 * margin)
        progress = ctx.round_number / max(ctx.max_rounds - 1, 1)
        price = round(max(initial - (initial - cost) * progress, cost), 2)
        # Accept if opponent's offer is above cost
        if ctx.last_offer is not None and ctx.last_offer >= cost:
            return NegotiationAction(
                ActionType.ACCEPT, None,
                "Deal!",
                "Fallback: accepting above cost.",
            )

    action_type = ActionType.OFFER if ctx.round_number == 0 else ActionType.COUNTER
    return NegotiationAction(
        action_type, price,
        f"I propose ${price:.2f}.",
        "Fallback: LLM parsing failure.",
    )


def call_llm_and_parse(
    backend: OllamaLLMBackend,
    prompt: str,
    ctx: AgentContext,
) -> NegotiationAction:
    """Call LLM, parse JSON, retry once on failure, fallback if still invalid.

    This is the canonical parse-validate-retry pipeline shared by all
    LLM agent types (reactive, deliberative, memory).
    """
    # ── first attempt ─────────────────────────────────────────────────────
    try:
        raw = backend.generate(prompt)
    except (ConnectionError, OSError, RuntimeError) as exc:
        logger.error("LLM backend error: %s – using fallback", exc)
        return fallback_action(ctx)

    parsed = extract_json(raw)

    if parsed is not None:
        valid, reason = validate_action_json(parsed)
        if valid:
            return to_action(parsed)
        logger.warning("JSON validation failed: %s", reason)
    else:
        logger.warning("Failed to extract JSON from LLM response")

    # ── retry with format-error nudge ─────────────────────────────────────
    try:
        retry_prompt = prompt + "\n\n" + FORMAT_ERROR_PROMPT
        raw = backend.generate(retry_prompt)
    except (ConnectionError, OSError, RuntimeError) as exc:
        logger.error("LLM backend error on retry: %s – using fallback", exc)
        return fallback_action(ctx)

    parsed = extract_json(raw)

    if parsed is not None:
        valid, reason = validate_action_json(parsed)
        if valid:
            return to_action(parsed)

    # ── fallback ──────────────────────────────────────────────────────────
    logger.error(
        "LLM failed to produce valid JSON after retry – using fallback"
    )
    return fallback_action(ctx)
