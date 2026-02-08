"""Optional market shocks: demand/supply multipliers."""
from __future__ import annotations

from src.core.config import ShockConfig
from src.core.rng import SeededRNG
from src.core.types import BuyerState, SellerState


def apply_shocks(
    buyers: list[BuyerState],
    sellers: list[SellerState],
    rng: SeededRNG,
    cfg: ShockConfig,
) -> tuple[list[BuyerState], list[SellerState]]:
    """Optionally apply multiplicative shocks to buyer values / seller costs.

    Shocks fire with probability ``cfg.shock_probability`` each step.
    Budgets and margins are left unchanged.
    """
    if not cfg.enabled:
        return buyers, sellers

    if rng.random() > cfg.shock_probability:
        return buyers, sellers

    demand_mult = rng.uniform(cfg.demand_multiplier_min, cfg.demand_multiplier_max)
    supply_mult = rng.uniform(cfg.supply_multiplier_min, cfg.supply_multiplier_max)

    new_buyers = [
        BuyerState(
            buyer_id=b.buyer_id,
            value=round(b.value * demand_mult, 2),
            budget=b.budget,          # budget is a hard constraint, unchanged
            patience=b.patience,
        )
        for b in buyers
    ]

    new_sellers = [
        SellerState(
            seller_id=s.seller_id,
            cost=round(s.cost * supply_mult, 2),
            target_margin=s.target_margin,
            patience=s.patience,
        )
        for s in sellers
    ]

    return new_buyers, new_sellers
