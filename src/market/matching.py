"""Buyer / seller generation and random matching."""
from __future__ import annotations

from src.core.config import MarketConfig
from src.core.rng import SeededRNG
from src.core.types import BuyerState, Item, SellerState


def generate_buyers(
    rng: SeededRNG,
    count: int,
    step: int,
    cfg: MarketConfig,
) -> list[BuyerState]:
    buyers: list[BuyerState] = []
    for i in range(count):
        value = round(rng.uniform(cfg.buyer_value_min, cfg.buyer_value_max), 2)
        budget = round(rng.uniform(cfg.buyer_budget_min, cfg.buyer_budget_max), 2)
        patience = rng.randint(cfg.buyer_patience_min, cfg.buyer_patience_max)
        buyers.append(
            BuyerState(
                buyer_id=f"buyer_t{step}_{i:03d}",
                value=value,
                budget=budget,
                patience=patience,
            )
        )
    return buyers


def generate_sellers(
    rng: SeededRNG,
    count: int,
    step: int,
    cfg: MarketConfig,
) -> list[SellerState]:
    sellers: list[SellerState] = []
    for i in range(count):
        cost = round(rng.uniform(cfg.seller_cost_min, cfg.seller_cost_max), 2)
        margin = round(rng.uniform(cfg.seller_margin_min, cfg.seller_margin_max), 4)
        patience = rng.randint(cfg.seller_patience_min, cfg.seller_patience_max)
        sellers.append(
            SellerState(
                seller_id=f"seller_t{step}_{i:03d}",
                cost=cost,
                target_margin=margin,
                patience=patience,
            )
        )
    return sellers


def match_pairs(
    buyers: list[BuyerState],
    sellers: list[SellerState],
    items: list[Item],
    rng: SeededRNG,
) -> list[tuple[BuyerState, SellerState, Item]]:
    """Randomly pair buyers with sellers and assign an item to each pair."""
    n = min(len(buyers), len(sellers))
    b = list(buyers[:n])
    s = list(sellers[:n])
    rng.shuffle(b)
    rng.shuffle(s)
    pairs: list[tuple[BuyerState, SellerState, Item]] = []
    for i in range(n):
        item = rng.choice(items)
        pairs.append((b[i], s[i], item))
    return pairs
