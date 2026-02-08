"""Hard constraint validation for negotiation actions."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from src.core.types import (
    ActionType,
    AgentRole,
    BuyerState,
    Item,
    NegotiationAction,
    SellerState,
)


@dataclass
class ValidationResult:
    valid: bool
    reason: str = ""
    violation_type: Optional[str] = None   # "budget" | "cost" | "bounds" | "logic"


def validate_action(
    role: AgentRole,
    action: NegotiationAction,
    buyer: BuyerState,
    seller: SellerState,
    last_offer: Optional[float],
    item: Item,
    round_number: int,
    min_price: float = 1.0,
    max_price: float = 500.0,
) -> ValidationResult:
    """Validate a negotiation action against hard constraints.

    Returns a ``ValidationResult`` with *valid=True* when all checks pass.
    """
    # ── offers / counters ────────────────────────────────────────────────
    if action.action in (ActionType.OFFER, ActionType.COUNTER):
        if action.offer_price is None:
            return ValidationResult(
                False, "offer/counter must include a price", "logic"
            )

        price = action.offer_price

        # global bounds
        if price < min_price or price > max_price:
            return ValidationResult(
                False,
                f"Price ${price:.2f} outside bounds "
                f"[${min_price:.2f}, ${max_price:.2f}]",
                "bounds",
            )

        # buyer-specific
        if role == AgentRole.BUYER:
            if price > buyer.budget:
                return ValidationResult(
                    False,
                    f"Buyer offer ${price:.2f} exceeds budget ${buyer.budget:.2f}",
                    "budget",
                )
            if price > buyer.value:
                return ValidationResult(
                    False,
                    f"Buyer offer ${price:.2f} exceeds value ${buyer.value:.2f}",
                    "budget",
                )

        # seller-specific
        if role == AgentRole.SELLER:
            if price < seller.cost:
                return ValidationResult(
                    False,
                    f"Seller offer ${price:.2f} below cost ${seller.cost:.2f}",
                    "cost",
                )

    # ── accept ───────────────────────────────────────────────────────────
    if action.action == ActionType.ACCEPT:
        if last_offer is None:
            return ValidationResult(
                False, "Cannot accept without a prior offer", "logic"
            )
        if role == AgentRole.BUYER:
            if last_offer > buyer.budget:
                return ValidationResult(
                    False,
                    f"Cannot accept ${last_offer:.2f}: exceeds budget "
                    f"${buyer.budget:.2f}",
                    "budget",
                )
            if last_offer > buyer.value:
                return ValidationResult(
                    False,
                    f"Cannot accept ${last_offer:.2f}: exceeds value "
                    f"${buyer.value:.2f}",
                    "budget",
                )
        if role == AgentRole.SELLER:
            if last_offer < seller.cost:
                return ValidationResult(
                    False,
                    f"Cannot accept ${last_offer:.2f}: below cost "
                    f"${seller.cost:.2f}",
                    "cost",
                )

    return ValidationResult(True)
