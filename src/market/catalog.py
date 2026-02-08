"""Item catalog generation."""
from __future__ import annotations

from src.core.rng import SeededRNG
from src.core.types import Item

_ITEM_NAMES = [
    "Widget", "Gadget", "Doohickey", "Thingamajig", "Gizmo",
    "Contraption", "Apparatus", "Device", "Module", "Component",
]


class Catalog:
    """Fixed set of item types generated once from a seeded RNG."""

    def __init__(
        self,
        rng: SeededRNG,
        num_types: int = 5,
        ref_price_min: float = 40.0,
        ref_price_max: float = 130.0,
    ):
        self._items: list[Item] = []
        for i in range(num_types):
            name = _ITEM_NAMES[i % len(_ITEM_NAMES)]
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
