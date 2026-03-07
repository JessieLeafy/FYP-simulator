"""Matching strategies for pairing buyers with sellers.

Provides a ``Matcher`` interface and implementations:

- ``RandomMatcher``     — random 1:1 pairing (baseline).
- ``SurplusMaxMatcher`` — pairs to maximise total ZOPA (oracle upper bound).
- ``SortedMatcher``     — pairs by closest reservation prices (practical heuristic).
- ``RoundRobinMatcher`` — deterministic repeated pairings across ticks (for
  reputation / memory experiments).

New matching strategies can be added by subclassing ``Matcher``.
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


class SurplusMaxMatcher(Matcher):
    """Oracle matcher that maximises total zone-of-possible-agreement (ZOPA).

    Pairs buyers and sellers greedily: compute ZOPA = buyer.value - seller.cost
    for all possible pairs, sort descending, and greedily assign pairs
    (each agent used at most once).  Only pairs with positive ZOPA are matched.

    This uses private information (buyer value, seller cost) and represents
    a *theoretical upper bound* on matching efficiency — not a realistic
    mechanism.
    """

    def match(
        self,
        buyers: list[BuyerState],
        sellers: list[SellerState],
        items: list[Item],
        rng: SeededRNG,
    ) -> list[tuple[BuyerState, SellerState, Item]]:
        # compute all candidate pairs with positive ZOPA
        candidates: list[tuple[float, int, int]] = []
        for bi, buyer in enumerate(buyers):
            for si, seller in enumerate(sellers):
                zopa = buyer.value - seller.cost
                if zopa > 0:
                    candidates.append((zopa, bi, si))

        # greedy assignment: highest ZOPA first
        candidates.sort(key=lambda x: x[0], reverse=True)
        used_buyers: set[int] = set()
        used_sellers: set[int] = set()
        pairs: list[tuple[BuyerState, SellerState, Item]] = []

        for _zopa, bi, si in candidates:
            if bi in used_buyers or si in used_sellers:
                continue
            used_buyers.add(bi)
            used_sellers.add(si)
            item = rng.choice(items)
            pairs.append((buyers[bi], sellers[si], item))

        return pairs


class SortedMatcher(Matcher):
    """Pairs buyers and sellers by closest reservation prices.

    Sorts buyers by value (descending) and sellers by cost (descending),
    then zips them.  This tends to pair high-value buyers with high-cost
    sellers, creating moderate but consistent ZOPAs.
    """

    def match(
        self,
        buyers: list[BuyerState],
        sellers: list[SellerState],
        items: list[Item],
        rng: SeededRNG,
    ) -> list[tuple[BuyerState, SellerState, Item]]:
        n = min(len(buyers), len(sellers))
        b = sorted(buyers, key=lambda x: x.value, reverse=True)[:n]
        s = sorted(sellers, key=lambda x: x.cost, reverse=True)[:n]
        pairs: list[tuple[BuyerState, SellerState, Item]] = []
        for i in range(n):
            item = rng.choice(items)
            pairs.append((b[i], s[i], item))
        return pairs


class RoundRobinMatcher(Matcher):
    """Deterministic repeated pairings for reputation/memory experiments.

    On the first call, pairs buyers and sellers 1:1 in order and remembers
    the pairings.  On subsequent calls with agents that share the same IDs,
    restores the same pairings.  New agents are paired randomly with any
    unmatched partners.

    This ensures the same buyer-seller pairs interact across multiple ticks,
    enabling reputation and memory effects.
    """

    def __init__(self) -> None:
        self._pairings: dict[str, str] = {}  # buyer_id → seller_id

    def match(
        self,
        buyers: list[BuyerState],
        sellers: list[SellerState],
        items: list[Item],
        rng: SeededRNG,
    ) -> list[tuple[BuyerState, SellerState, Item]]:
        buyer_map = {b.buyer_id: b for b in buyers}
        seller_map = {s.seller_id: s for s in sellers}

        pairs: list[tuple[BuyerState, SellerState, Item]] = []
        used_sellers: set[str] = set()

        # restore known pairings
        for bid, sid in list(self._pairings.items()):
            if bid in buyer_map and sid in seller_map:
                item = rng.choice(items)
                pairs.append((buyer_map[bid], seller_map[sid], item))
                used_sellers.add(sid)

        # pair remaining agents
        remaining_buyers = [
            b for b in buyers if b.buyer_id not in self._pairings
        ]
        remaining_sellers = [
            s for s in sellers
            if s.seller_id not in used_sellers
        ]
        n = min(len(remaining_buyers), len(remaining_sellers))
        rng.shuffle(remaining_buyers)
        rng.shuffle(remaining_sellers)
        for i in range(n):
            b = remaining_buyers[i]
            s = remaining_sellers[i]
            self._pairings[b.buyer_id] = s.seller_id
            item = rng.choice(items)
            pairs.append((b, s, item))

        return pairs
