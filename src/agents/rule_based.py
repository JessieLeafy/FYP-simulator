"""Rule-based concession agent (no LLM required)."""
from __future__ import annotations

from src.agents.base import BaseAgent
from src.core.types import (
    ActionType,
    AgentContext,
    AgentRole,
    NegotiationAction,
)


class RuleBasedAgent(BaseAgent):
    """Linear-concession strategy: starts aggressively, concedes toward
    reservation price over the course of the negotiation."""

    @property
    def agent_type(self) -> str:
        return "rule_based"

    def decide(self, ctx: AgentContext) -> NegotiationAction:
        if ctx.role == AgentRole.BUYER:
            return self._decide_buyer(ctx)
        return self._decide_seller(ctx)

    # ── buyer logic ──────────────────────────────────────────────────────

    def _decide_buyer(self, ctx: AgentContext) -> NegotiationAction:
        cap = min(ctx.reservation_price, ctx.budget or ctx.reservation_price)

        # linear concession from 50 % of cap toward cap
        initial = cap * 0.5
        progress = ctx.round_number / max(ctx.max_rounds - 1, 1)
        target = initial + (cap - initial) * progress

        # accept if opponent's offer is at or below target
        if ctx.last_offer is not None and ctx.last_offer <= target:
            return NegotiationAction(
                ActionType.ACCEPT, None,
                "I accept your offer.",
                f"Offer ${ctx.last_offer:.2f} <= target ${target:.2f}",
            )

        # last round – accept if feasible, else reject
        if ctx.round_number >= ctx.max_rounds - 1:
            if ctx.last_offer is not None and ctx.last_offer <= cap:
                return NegotiationAction(
                    ActionType.ACCEPT, None,
                    "Fine, I'll take it.",
                    "Last round – accepting within constraints.",
                )
            return NegotiationAction(
                ActionType.REJECT, None,
                "We couldn't reach an agreement.",
                "Last round – offer exceeds constraints.",
            )

        # make offer / counter
        offer_price = round(min(target, cap), 2)
        action_type = (
            ActionType.OFFER if ctx.round_number == 0
            else ActionType.COUNTER
        )
        return NegotiationAction(
            action_type, offer_price,
            f"I propose ${offer_price:.2f}.",
            f"target={target:.2f} cap={cap:.2f} progress={progress:.2f}",
        )

    # ── seller logic ─────────────────────────────────────────────────────

    def _decide_seller(self, ctx: AgentContext) -> NegotiationAction:
        cost = ctx.reservation_price
        margin = ctx.target_margin or 0.15

        # start high, concede toward cost
        initial = cost * (1 + 2 * margin)
        progress = ctx.round_number / max(ctx.max_rounds - 1, 1)
        target = initial - (initial - cost) * progress

        # accept if buyer's offer meets or exceeds target
        if ctx.last_offer is not None and ctx.last_offer >= target:
            return NegotiationAction(
                ActionType.ACCEPT, None,
                "Deal!",
                f"Offer ${ctx.last_offer:.2f} >= target ${target:.2f}",
            )

        # last round
        if ctx.round_number >= ctx.max_rounds - 1:
            if ctx.last_offer is not None and ctx.last_offer >= cost:
                return NegotiationAction(
                    ActionType.ACCEPT, None,
                    "Alright, let's close this deal.",
                    "Last round – accepting above cost.",
                )
            return NegotiationAction(
                ActionType.REJECT, None,
                "Sorry, we can't agree on a price.",
                "Last round – offer below cost.",
            )

        offer_price = round(max(target, cost), 2)
        action_type = (
            ActionType.OFFER if ctx.round_number == 0
            else ActionType.COUNTER
        )
        return NegotiationAction(
            action_type, offer_price,
            f"How about ${offer_price:.2f}?",
            f"target={target:.2f} cost={cost:.2f} progress={progress:.2f}",
        )
