"""Matching strategies for pairing buyers with sellers.

Provides a ``Matcher`` interface and a ``RandomMatcher`` implementation.
New matching strategies (e.g., preference-based, auction-style) can be
added by subclassing ``Matcher``.
"""
from __future__ import annotations

from abc import ABC, abstractmethod

from src.core.rng import SeededRNG
from src.core.types import BuyerState, Item, SellerState


class Matcher(ABC):
    """Interface for buyer-seller matching strategies."""

    @abstractmethod
    def match(
        self,
        buyers: list[BuyerState],
        sellers: list[SellerState],
        items: list[Item],
        rng: SeededRNG,
    ) -> list[tuple[BuyerState, SellerState, Item]]:
        """Return paired (buyer, seller, item) tuples."""
        ...


class RandomMatcher(Matcher):
    """Random 1:1 pairing with random item assignment.

    Pairs min(|buyers|, |sellers|) agents. Unmatched agents are silently
    dropped (logged at the market level if needed).
    """

    def match(
        self,
        buyers: list[BuyerState],
        sellers: list[SellerState],
        items: list[Item],
        rng: SeededRNG,
    ) -> list[tuple[BuyerState, SellerState, Item]]:
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
