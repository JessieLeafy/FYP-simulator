"""Item catalog generation."""
from __future__ import annotations

from typing import Any, Optional, Union

from src.core.rng import SeededRNG
from src.core.types import Item

_ITEM_NAMES = [
    "Widget", "Gadget", "Doohickey", "Thingamajig", "Gizmo",
    "Contraption", "Apparatus", "Device", "Module", "Component",
]


class Catalog:
    """Fixed set of item types generated once from a seeded RNG.

    When *fixed_ref_prices* is provided (scalar or list), those prices
    are used instead of sampling from [ref_price_min, ref_price_max].
    """

    def __init__(
        self,
        rng: SeededRNG,
        num_types: int = 5,
        ref_price_min: float = 40.0,
        ref_price_max: float = 130.0,
        fixed_ref_prices: Optional[Any] = None,
    ):
        # normalise fixed prices to a list (or None)
        if fixed_ref_prices is not None:
            if isinstance(fixed_ref_prices, (list, tuple)):
                prices: list[float] = [float(p) for p in fixed_ref_prices]
            else:
                prices = [float(fixed_ref_prices)]
        else:
            prices = []

        self._items: list[Item] = []
        for i in range(num_types):
            name = _ITEM_NAMES[i % len(_ITEM_NAMES)]
            if prices:
                ref_price = round(prices[i % len(prices)], 2)
            else:
                ref_price = round(rng.uniform(ref_price_min, ref_price_max), 2)
            self._items.append(
                Item(
                    item_id=f"item_{i:03d}",
                    name=f"{name} {chr(65 + i)}",
                    reference_price=ref_price,
                )
            )

    @property
    def items(self) -> list[Item]:
        return list(self._items)

    def get_random_item(self, rng: SeededRNG) -> Item:
        return rng.choice(self._items)
