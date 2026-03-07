"""Deterministic deal feasibility checker.

Computes utility of a given offer for a role and determines whether
the agent should accept it based on private constraints.

Why this is necessary
---------------------
Weak LLMs (e.g. qwen2.5:3b) frequently fail to output ``"accept"``
even when an offer is clearly within the agent's private constraints
and yields positive surplus.  Without a deterministic override,
negotiations never settle, making research results meaningless.

The feasibility checker provides a safety net: if the simulator can
prove that acceptance is both legal and profitable, it overrides the
LLM's (incorrect) ``COUNTER``/``REJECT`` with an ``ACCEPT``.  Both
the LLM's intended action and the effective action are logged for
analysis (see :class:`~src.core.logging.EventLogger`).

Note on relationship to ``constraints.py``
------------------------------------------
``validate_action()`` in ``constraints.py`` answers: *"Is this ACCEPT
action legal given the hard constraints?"*  The feasibility checker
answers: *"Should the agent accept the opponent's current offer?"*
They check the same mathematical conditions, but from opposite
directions — action legality vs. decision optimality.
"""
from __future__ import annotations

from src.core.types import AgentRole, BuyerState, SellerState


def compute_utility(
    role: AgentRole,
    offer_price: float,
    buyer: BuyerState,
    seller: SellerState,
) -> float:
    """Compute the economic surplus of accepting *offer_price* for *role*.

    - Buyer surplus = ``value − offer_price``  (positive ↔ deal is good)
    - Seller surplus = ``offer_price − cost``   (positive ↔ deal is good)
    """
    if role == AgentRole.BUYER:
        return buyer.value - offer_price
    return offer_price - seller.cost


def is_offer_feasible(
    role: AgentRole,
    offer_price: float,
    buyer: BuyerState,
    seller: SellerState,
) -> tuple[bool, str]:
    """Determine whether accepting *offer_price* is feasible for *role*.

    Feasibility requires that the offer meets all hard constraints
    (budget / cost floor) and yields non-negative utility.

    Returns:
        ``(True, human-readable reason)`` if feasible.
        ``(False, "")`` otherwise.
    """
    if role == AgentRole.BUYER:
        cap = min(buyer.value, buyer.budget)
        if offer_price <= cap:
            utility = buyer.value - offer_price
            return (
                True,
                (
                    f"utility={utility:.2f} "
                    f"(offer ${offer_price:.2f} <= cap ${cap:.2f})"
                ),
            )
        return False, ""

    # seller
    if offer_price >= seller.cost:
        utility = offer_price - seller.cost
        return (
            True,
            (
                f"utility={utility:.2f} "
                f"(offer ${offer_price:.2f} >= cost ${seller.cost:.2f})"
            ),
        )
    return False, ""
