"""Buyer / seller generation, ParameterSource abstraction, and matching."""
from __future__ import annotations

from typing import Any, Optional

from src.core.config import FixedScenarioConfig, MarketConfig
from src.core.rng import SeededRNG
from src.core.types import BuyerState, SellerState


# ── ParameterSource ──────────────────────────────────────────────────────────

class ParameterSource:
    """Draws values from either a uniform distribution or a fixed spec.

    *fixed_value* can be:
      - ``None``  → fall back to uniform(dist_min, dist_max)
      - a scalar  → always return that value
      - a list    → cycle through or randomly sample (per *selection*)
    """

    def __init__(
        self,
        fixed_value: Any = None,
        dist_min: float = 0.0,
        dist_max: float = 1.0,
        is_int: bool = False,
        selection: str = "cycle",
    ):
        self._is_int = is_int
        self._selection = selection
        self._cycle_idx = 0

        if fixed_value is not None:
            self._values: Optional[list] = (
                list(fixed_value) if isinstance(fixed_value, (list, tuple))
                else [fixed_value]
            )
        else:
            self._values = None

        self._dist_min = dist_min
        self._dist_max = dist_max

    @property
    def is_fixed(self) -> bool:
        return self._values is not None

    def draw(self, rng: SeededRNG) -> float | int:
        """Return the next parameter value."""
        if self._values is not None:
            if len(self._values) == 1:
                val = self._values[0]
            elif self._selection == "random":
                val = rng.choice(self._values)
            else:  # cycle (default)
                val = self._values[self._cycle_idx % len(self._values)]
                self._cycle_idx += 1
            return int(val) if self._is_int else round(float(val), 2)

        if self._is_int:
            return rng.randint(int(self._dist_min), int(self._dist_max))
        return round(rng.uniform(self._dist_min, self._dist_max), 2)


def _src(
    fixed_val: Any,
    dist_min: float,
    dist_max: float,
    is_int: bool = False,
    selection: str = "cycle",
) -> ParameterSource:
    return ParameterSource(fixed_val, dist_min, dist_max, is_int, selection)


# ── buyer / seller generators ───────────────────────────────────────────────

def generate_buyers(
    rng: SeededRNG,
    count: int,
    step: int,
    cfg: MarketConfig,
    fixed: Optional[FixedScenarioConfig] = None,
) -> list[BuyerState]:
    sel = fixed.selection if fixed else "cycle"
    value_src = _src(
        fixed.buyer_value if fixed else None,
        cfg.buyer_value_min, cfg.buyer_value_max, selection=sel,
    )
    budget_src = _src(
        fixed.buyer_budget if fixed else None,
        cfg.buyer_budget_min, cfg.buyer_budget_max, selection=sel,
    )
    patience_src = _src(
        fixed.buyer_patience if fixed else None,
        cfg.buyer_patience_min, cfg.buyer_patience_max,
        is_int=True, selection=sel,
    )

    buyers: list[BuyerState] = []
    for i in range(count):
        buyers.append(
            BuyerState(
                buyer_id=f"buyer_t{step}_{i:03d}",
                value=value_src.draw(rng),
                budget=budget_src.draw(rng),
                patience=patience_src.draw(rng),
            )
        )
    return buyers


def generate_sellers(
    rng: SeededRNG,
    count: int,
    step: int,
    cfg: MarketConfig,
    fixed: Optional[FixedScenarioConfig] = None,
) -> list[SellerState]:
    sel = fixed.selection if fixed else "cycle"
    cost_src = _src(
        fixed.seller_cost if fixed else None,
        cfg.seller_cost_min, cfg.seller_cost_max, selection=sel,
    )
    margin_src = _src(
        fixed.seller_target_margin if fixed else None,
        cfg.seller_margin_min, cfg.seller_margin_max, selection=sel,
    )
    patience_src = _src(
        fixed.seller_patience if fixed else None,
        cfg.seller_patience_min, cfg.seller_patience_max,
        is_int=True, selection=sel,
    )

    sellers: list[SellerState] = []
    for i in range(count):
        sellers.append(
            SellerState(
                seller_id=f"seller_t{step}_{i:03d}",
                cost=cost_src.draw(rng),
                target_margin=round(margin_src.draw(rng), 4),
                patience=patience_src.draw(rng),
            )
        )
    return sellers
