"""Shared utilities for LLM-based negotiation agents.

Provides the parse-validate-rethink pipeline used by all LLM agent types.

Pipeline:
  1. Call LLM → parse JSON → validate schema
  2. If valid, check economic feasibility (constraint violations)
  3. If anything fails → ONE rethink attempt with a specific error message
  4. If rethink also fails → no rescue; return REJECT (unparseable)
     or pass through the parsed-but-infeasible action (let judge handle)
"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Optional

from src.core.types import (
    ActionType,
    AgentContext,
    AgentRole,
    NegotiationAction,
)
from src.llm.schemas import FORMAT_ERROR_PROMPT, build_rethink_prompt
from src.negotiation.parser import (
    extract_json,
    validate_action_json,
    extract_price_from_text,
    detect_accept_intent,
)

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


# ── feasibility check (constraint violations only) ────────────────────────

def _check_feasibility(action: NegotiationAction, ctx: AgentContext) -> Optional[str]:
    """Check if the action violates the agent's private constraints.

    Returns an error string if infeasible, or None if OK.
    This does NOT check whether the agent *should* accept — only whether
    the action is economically legal given the agent's constraints.
    """
    price = action.offer_price
    is_buyer = ctx.role == AgentRole.BUYER

    if action.action in (ActionType.OFFER, ActionType.COUNTER):
        if price is None:
            return "offer/counter requires a price"
        if is_buyer:
            cap = min(ctx.reservation_price, ctx.budget or ctx.reservation_price)
            if price > cap:
                return f"Price ${price:.2f} exceeds your maximum of ${cap:.2f}"
            if price <= 0:
                return "Price must be positive"
        else:
            cost = ctx.reservation_price
            if price < cost:
                return f"Price ${price:.2f} is below your minimum of ${cost:.2f}"
            if price <= 0:
                return "Price must be positive"

    if action.action == ActionType.ACCEPT:
        if ctx.last_offer is None:
            return "Cannot accept without a prior offer"
        if is_buyer:
            cap = min(ctx.reservation_price, ctx.budget or ctx.reservation_price)
            if ctx.last_offer > cap:
                return (
                    f"Cannot accept ${ctx.last_offer:.2f}: "
                    f"exceeds your maximum ${cap:.2f}"
                )
        else:
            cost = ctx.reservation_price
            if ctx.last_offer < cost:
                return (
                    f"Cannot accept ${ctx.last_offer:.2f}: "
                    f"below your minimum ${cost:.2f}"
                )

    return None  # feasible


# ── fallback (kept for backward compat but not used in main pipeline) ─────

def fallback_action(ctx: AgentContext) -> NegotiationAction:
    """Produce a safe default when the LLM output cannot be parsed.

    Uses a linear-concession strategy so negotiations make progress
    even when the LLM fails to produce valid JSON.

    .. deprecated::
        No longer used by the main pipeline. Kept for backward
        compatibility with tests and external callers.
    """
    if ctx.role == AgentRole.BUYER:
        cap = min(ctx.reservation_price, ctx.budget or ctx.reservation_price)
        initial = cap * 0.5
        progress = ctx.round_number / max(ctx.max_rounds - 1, 1)
        price = round(min(initial + (cap - initial) * progress, cap), 2)
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


# ── main pipeline ─────────────────────────────────────────────────────────

def _try_parse(raw: str) -> tuple[Optional[NegotiationAction], Optional[dict], Optional[str]]:
    """Parse and validate LLM output.

    Returns:
        (action, parsed_dict, error_reason)
        - On success: (action, dict, None)
        - On failure: (None, parsed_dict_or_None, error_string)
    """
    parsed = extract_json(raw)
    if parsed is None:
        return None, None, "Response is not valid JSON"

    valid, reason = validate_action_json(parsed)
    if not valid:
        return None, parsed, f"Invalid JSON: {reason}"

    return to_action(parsed), parsed, None


def call_llm_and_parse(
    backend: OllamaLLMBackend,
    prompt: str,
    ctx: AgentContext,
) -> NegotiationAction:
    """Call LLM, parse JSON, rethink once on failure, no rescue fallback.

    Pipeline:
      1. Call LLM → parse + validate schema
      2. If valid → check economic feasibility
      3. If anything wrong → ONE rethink call with specific error
      4. If rethink succeeds → return it
      5. If rethink fails → return REJECT (unparseable) or pass through
         the action as-is (let the session judge handle it)
    """
    # ── first attempt ─────────────────────────────────────────────────
    try:
        raw = backend.generate(prompt)
    except (ConnectionError, OSError, RuntimeError) as exc:
        logger.error("LLM backend error: %s – returning REJECT", exc)
        return NegotiationAction(
            ActionType.REJECT, None,
            "I cannot continue.",
            f"LLM backend error: {exc}",
        )

    action, parsed, parse_error = _try_parse(raw)

    # Determine if we need a rethink
    rethink_reason: Optional[str] = None

    if parse_error is not None:
        rethink_reason = parse_error
    elif action is not None:
        # Schema is valid; check economic feasibility
        feasibility_error = _check_feasibility(action, ctx)
        if feasibility_error is not None:
            rethink_reason = feasibility_error

    if rethink_reason is None and action is not None:
        # Everything is fine — return the action
        return action

    # ── rethink attempt ───────────────────────────────────────────────
    logger.warning("Rethink triggered: %s", rethink_reason)

    rethink_msg = build_rethink_prompt(rethink_reason or "Invalid response")
    retry_prompt = prompt + "\n\n" + rethink_msg

    try:
        raw = backend.generate(retry_prompt)
    except (ConnectionError, OSError, RuntimeError) as exc:
        logger.error("LLM backend error on rethink: %s", exc)
        # Return whatever we had from the first attempt
        if action is not None:
            return action
        return NegotiationAction(
            ActionType.REJECT, None,
            "I cannot continue.",
            f"LLM rethink error: {exc}",
        )

    action2, parsed2, parse_error2 = _try_parse(raw)

    if parse_error2 is not None:
        # Rethink also failed to parse
        logger.error("Rethink failed to parse: %s", parse_error2)
        # If first attempt had a valid action (just infeasible), return it
        # and let the judge handle it
        if action is not None:
            return action
        # Completely unparseable — return REJECT
        return NegotiationAction(
            ActionType.REJECT, None,
            "I cannot continue.",
            f"LLM produced unparseable output after rethink: {parse_error2}",
        )

    # Rethink parsed OK — check feasibility but don't rethink again
    if action2 is not None:
        feasibility_error2 = _check_feasibility(action2, ctx)
        if feasibility_error2 is not None:
            logger.warning(
                "Rethink still infeasible: %s – passing through to judge",
                feasibility_error2,
            )
        return action2

    # Shouldn't reach here, but be safe
    if action is not None:
        return action
    return NegotiationAction(
        ActionType.REJECT, None,
        "I cannot continue.",
        "LLM failed after rethink.",
    )


# ── free-language pipeline ─────────────────────────────────────────────────

def _parse_free_language(raw: str, ctx: AgentContext) -> NegotiationAction:
    """Parse free-language LLM output into a NegotiationAction.

    Extraction rules:
      1. Check for ACCEPT_DEAL keyword → ActionType.ACCEPT
      2. Extract price via ### PRICE($X) ### tag (or bare $X fallback)
      3. If price found → OFFER (round 0) or COUNTER (later rounds)
      4. If nothing extractable → REJECT
    """
    import re as _re
    # Strip <think>...</think> tags (common with reasoning models)
    cleaned = _re.sub(r'<think>.*?</think>', '', raw, flags=_re.DOTALL | _re.IGNORECASE).strip()

    has_accept = detect_accept_intent(cleaned)
    price = extract_price_from_text(cleaned)

    if has_accept:
        return NegotiationAction(
            ActionType.ACCEPT,
            None,
            cleaned,
            "Free-language: agent signalled ACCEPT_DEAL.",
        )

    if price is not None:
        action_type = ActionType.OFFER if ctx.round_number == 0 else ActionType.COUNTER
        return NegotiationAction(
            action_type,
            price,
            cleaned,
            f"Free-language: extracted price ${price:.2f}.",
        )

    # Nothing extractable
    return NegotiationAction(
        ActionType.REJECT,
        None,
        cleaned or "...",
        "Free-language: no price tag or accept keyword found.",
    )


def call_llm_free_language(
    backend: OllamaLLMBackend,
    prompt: str,
    ctx: AgentContext,
) -> NegotiationAction:
    """Call LLM in free-language mode and extract action from natural text.

    Pipeline:
      1. Call LLM → get raw natural-language response
      2. Parse: extract price tag + accept intent → NegotiationAction
      3. Check economic feasibility of extracted price
      4. If infeasible or unparseable → ONE retry with error hint appended
      5. If retry also fails → pass through to judge
    """
    # ── first attempt ─────────────────────────────────────────────────
    try:
        raw = backend.generate(prompt)
    except (ConnectionError, OSError, RuntimeError) as exc:
        logger.error("LLM backend error: %s – returning REJECT", exc)
        return NegotiationAction(
            ActionType.REJECT, None,
            "I cannot continue.",
            f"LLM backend error: {exc}",
        )

    action = _parse_free_language(raw, ctx)

    # Check if we got something usable
    if action.action == ActionType.REJECT:
        # Nothing extracted — retry with hint
        is_buyer = ctx.role == AgentRole.BUYER
        tag = "BUYER_PRICE" if is_buyer else "SELLER_PRICE"
        retry_hint = (
            "\n\nYour previous response did not include a valid price offer. "
            f"You MUST include exactly one price in the format: ### {tag}($X) ###\n"
            "If you want to accept, include the word MAKE_DEAL.\n"
            "Please respond again:"
        )
        try:
            raw = backend.generate(prompt + retry_hint)
        except (ConnectionError, OSError, RuntimeError) as exc:
            logger.error("LLM retry error: %s", exc)
            return action
        action = _parse_free_language(raw, ctx)
        if action.action == ActionType.REJECT:
            logger.error("Free-language retry still unparseable")
            return action

    # Check feasibility (same logic as structured pipeline)
    if action.action in (ActionType.OFFER, ActionType.COUNTER):
        feasibility_error = _check_feasibility(action, ctx)
        if feasibility_error is not None:
            logger.warning("Free-language infeasible: %s – passing to judge", feasibility_error)
            # Don't retry for feasibility — let the judge handle it

    return action
