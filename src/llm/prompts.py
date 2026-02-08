"""Prompt templates for LLM negotiation agents."""
from __future__ import annotations

from src.core.types import AgentContext, AgentRole, NegotiationTurn
from src.llm.schemas import SCHEMA_DESCRIPTION


def _format_history(history: list[NegotiationTurn]) -> str:
    if not history:
        return "  (none yet)"
    lines: list[str] = []
    for turn in history:
        role = turn.agent_role.value
        act = turn.action.action.value
        price = turn.action.offer_price
        msg = turn.action.message_public
        if price is not None:
            lines.append(
                f"  Round {turn.round_number}: {role} {act} "
                f"at ${price:.2f} – \"{msg}\""
            )
        else:
            lines.append(f"  Round {turn.round_number}: {role} {act} – \"{msg}\"")
    return "\n".join(lines)


def _buyer_constraints(ctx: AgentContext) -> str:
    cap = min(ctx.reservation_price, ctx.budget or ctx.reservation_price)
    return (
        f"Your maximum willingness-to-pay (value): ${ctx.reservation_price:.2f}\n"
        f"Your budget limit: ${ctx.budget:.2f}\n"
        f"Hard ceiling (min of value, budget): ${cap:.2f}\n"
        f"Goal: buy as CHEAPLY as possible. Never offer above ${cap:.2f}."
    )


def _seller_constraints(ctx: AgentContext) -> str:
    return (
        f"Your minimum acceptable price (cost): ${ctx.reservation_price:.2f}\n"
        f"Your target profit margin: {(ctx.target_margin or 0) * 100:.0f}%\n"
        f"Goal: sell as EXPENSIVELY as possible. Never offer or accept below "
        f"${ctx.reservation_price:.2f}."
    )


# ── reactive prompt ─────────────────────────────────────────────────────────

def build_reactive_prompt(ctx: AgentContext) -> str:
    role = ctx.role.value
    constraints = (
        _buyer_constraints(ctx)
        if ctx.role == AgentRole.BUYER
        else _seller_constraints(ctx)
    )
    last = (
        f"${ctx.last_offer:.2f}"
        if ctx.last_offer is not None
        else "None (you go first)"
    )

    return (
        f"You are a {role} negotiating over \"{ctx.item.name}\" "
        f"(reference price ${ctx.item.reference_price:.2f}).\n\n"
        f"{constraints}\n\n"
        f"Round {ctx.round_number + 1} of {ctx.max_rounds}.\n"
        f"Opponent's last offer: {last}\n\n"
        f"History:\n{_format_history(ctx.history)}\n\n"
        f"{SCHEMA_DESCRIPTION}\n\n"
        "Decide your next action. Respond with ONLY the JSON object."
    )


# ── deliberative prompt ─────────────────────────────────────────────────────

def build_deliberative_prompt(ctx: AgentContext) -> str:
    role = ctx.role.value
    constraints = (
        _buyer_constraints(ctx)
        if ctx.role == AgentRole.BUYER
        else _seller_constraints(ctx)
    )
    last = (
        f"${ctx.last_offer:.2f}"
        if ctx.last_offer is not None
        else "None (you go first)"
    )
    remaining = ctx.max_rounds - ctx.round_number - 1

    return (
        f"You are a {role} negotiating for \"{ctx.item.name}\" "
        f"(ref price ${ctx.item.reference_price:.2f}).\n\n"
        f"{constraints}\n\n"
        f"Round {ctx.round_number + 1}/{ctx.max_rounds} "
        f"({remaining} rounds remaining after this).\n"
        f"Opponent's last offer: {last}\n\n"
        f"History:\n{_format_history(ctx.history)}\n\n"
        "Before deciding, reason through these steps INSIDE your "
        "rationale_private field:\n"
        "1. BELIEFS – What is the opponent's likely reservation price?\n"
        "2. TARGET  – What price would be ideal given remaining rounds?\n"
        "3. STRATEGY – Concede, hold firm, accept, or reject?\n"
        "4. ACTION  – Specific action and price.\n\n"
        f"{SCHEMA_DESCRIPTION}\n\n"
        "Respond with ONLY the JSON object. "
        "Put ALL reasoning inside rationale_private."
    )


# ── memory context ──────────────────────────────────────────────────────────

def build_memory_context(memories: list[dict]) -> str:
    """Format past negotiation memories for prompt injection."""
    if not memories:
        return ""
    lines = ["Your past negotiation experiences (most relevant first):"]
    for i, mem in enumerate(memories, 1):
        outcome = "DEAL" if mem.get("deal_made") else "NO DEAL"
        price_str = f" at ${mem['deal_price']:.2f}" if mem.get("deal_price") else ""
        lines.append(
            f"  {i}. Item: {mem.get('item_name', '?')} | "
            f"Outcome: {outcome}{price_str} | "
            f"Rounds: {mem.get('rounds', '?')} | "
            f"Opponent style: {mem.get('opponent_style', 'unknown')}"
        )
    lines.append("")
    return "\n".join(lines)
