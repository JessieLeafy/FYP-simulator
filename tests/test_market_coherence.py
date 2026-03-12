"""Tests for market coherence: buyer/seller stats relative to item reference price."""
from __future__ import annotations

import pytest

from src.core.config import MarketConfig
from src.core.rng import SeededRNG
from src.core.types import BuyerState, Item, SellerState
from src.market.matching import (
    adjust_pair_for_item,
    validate_market_coherence,
)


def _make_item(ref_price: float = 100.0) -> Item:
    return Item(item_id="item_000", name="Widget A", reference_price=ref_price)


def _make_buyer(**kw) -> BuyerState:
    defaults = dict(buyer_id="buyer_000", value=120.0, budget=150.0, patience=5)
    defaults.update(kw)
    return BuyerState(**defaults)


def _make_seller(**kw) -> SellerState:
    defaults = dict(seller_id="seller_000", cost=80.0, target_margin=0.15, patience=5)
    defaults.update(kw)
    return SellerState(**defaults)


class TestAdjustPairForItem:
    """Post-match coherence adjustment resamples stats relative to ref price."""

    def test_seller_cost_below_reference_price(self):
        """Seller cost must always be below item reference price after adjustment."""
        rng = SeededRNG(42)
        cfg = MarketConfig()
        item = _make_item(100.0)

        for _ in range(200):
            seller = _make_seller(cost=999.0)  # intentionally bad
            buyer = _make_buyer()
            adjust_pair_for_item(buyer, seller, item, rng, cfg)
            assert seller.cost < item.reference_price, (
                f"seller.cost={seller.cost} >= ref={item.reference_price}"
            )

    def test_seller_cost_within_ratio_bounds(self):
        """Seller cost stays within [ref*ratio_min, ref*ratio_max]."""
        rng = SeededRNG(123)
        cfg = MarketConfig()
        item = _make_item(100.0)

        costs = []
        for _ in range(500):
            seller = _make_seller()
            buyer = _make_buyer()
            adjust_pair_for_item(buyer, seller, item, rng, cfg)
            costs.append(seller.cost)

        assert min(costs) >= 100.0 * cfg.seller_cost_ratio_min - 0.01
        assert max(costs) <= 100.0 * cfg.seller_cost_ratio_max + 0.01

    def test_buyer_value_within_ratio_bounds(self):
        """Buyer value stays within [ref*ratio_min, ref*ratio_max]."""
        rng = SeededRNG(456)
        cfg = MarketConfig()
        item = _make_item(80.0)

        values = []
        for _ in range(500):
            buyer = _make_buyer()
            seller = _make_seller()
            adjust_pair_for_item(buyer, seller, item, rng, cfg)
            values.append(buyer.value)

        assert min(values) >= 80.0 * cfg.buyer_value_ratio_min - 0.01
        assert max(values) <= 80.0 * cfg.buyer_value_ratio_max + 0.01

    def test_budget_at_least_value(self):
        """Buyer budget must be >= buyer value after adjustment."""
        rng = SeededRNG(789)
        cfg = MarketConfig()
        item = _make_item(100.0)

        for _ in range(300):
            buyer = _make_buyer()
            seller = _make_seller()
            adjust_pair_for_item(buyer, seller, item, rng, cfg)
            assert buyer.budget >= buyer.value, (
                f"budget={buyer.budget} < value={buyer.value}"
            )

    def test_heterogeneity_preserved(self):
        """Different seeds produce different values (not all identical)."""
        rng = SeededRNG(42)
        cfg = MarketConfig()
        item = _make_item(100.0)

        costs = set()
        for _ in range(20):
            seller = _make_seller()
            buyer = _make_buyer()
            adjust_pair_for_item(buyer, seller, item, rng, cfg)
            costs.add(seller.cost)

        assert len(costs) > 1, "All seller costs are identical — no heterogeneity"

    def test_works_with_low_reference_price(self):
        """Coherence holds even for low reference prices."""
        rng = SeededRNG(42)
        cfg = MarketConfig()
        item = _make_item(40.0)  # low end of default range

        for _ in range(100):
            buyer = _make_buyer()
            seller = _make_seller()
            adjust_pair_for_item(buyer, seller, item, rng, cfg)
            assert seller.cost < item.reference_price
            assert seller.cost >= 40.0 * cfg.seller_cost_ratio_min - 0.01

    def test_works_with_high_reference_price(self):
        """Coherence holds even for high reference prices."""
        rng = SeededRNG(42)
        cfg = MarketConfig()
        item = _make_item(130.0)  # high end of default range

        for _ in range(100):
            buyer = _make_buyer()
            seller = _make_seller()
            adjust_pair_for_item(buyer, seller, item, rng, cfg)
            assert seller.cost < item.reference_price
            assert buyer.value >= 130.0 * cfg.buyer_value_ratio_min - 0.01


class TestValidateMarketCoherence:
    """Validation detects incoherent triples."""

    def test_no_warnings_for_coherent_triple(self):
        item = _make_item(100.0)
        buyer = _make_buyer(value=120.0)
        seller = _make_seller(cost=70.0)
        warnings = validate_market_coherence([(buyer, seller, item)])
        assert warnings == []

    def test_warns_seller_cost_above_reference(self):
        item = _make_item(100.0)
        buyer = _make_buyer(value=130.0)
        seller = _make_seller(cost=117.0)  # the original bug
        warnings = validate_market_coherence([(buyer, seller, item)])
        assert any("Incoherent" in w for w in warnings)

    def test_warns_no_zopa(self):
        item = _make_item(100.0)
        buyer = _make_buyer(value=50.0)
        seller = _make_seller(cost=80.0)
        warnings = validate_market_coherence([(buyer, seller, item)])
        assert any("No ZOPA" in w for w in warnings)

    def test_both_warnings_for_doubly_bad_triple(self):
        item = _make_item(60.0)
        buyer = _make_buyer(value=50.0)
        seller = _make_seller(cost=80.0)  # cost > ref AND cost > buyer value
        warnings = validate_market_coherence([(buyer, seller, item)])
        assert len(warnings) == 2


class TestCoherenceWithDefaultRatios:
    """Verify that the default ratio ranges produce mostly feasible pairs."""

    def test_positive_zopa_rate(self):
        """With default ratios, most pairs should have positive ZOPA."""
        rng = SeededRNG(42)
        cfg = MarketConfig()
        item = _make_item(100.0)

        feasible = 0
        n = 500
        for _ in range(n):
            buyer = _make_buyer()
            seller = _make_seller()
            adjust_pair_for_item(buyer, seller, item, rng, cfg)
            if buyer.value > seller.cost:
                feasible += 1

        rate = feasible / n
        # With default ratios (buyer 0.85-1.5, seller 0.3-0.85), most should
        # have positive ZOPA. Allow a small fraction of infeasible pairs.
        assert rate > 0.70, f"Only {rate:.1%} of pairs have positive ZOPA"
