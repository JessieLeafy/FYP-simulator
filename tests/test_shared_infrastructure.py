"""Tests for shared infrastructure added for Experiments F, G, H.

Covers:
- Feasibility gate toggle (gate_enabled flag)
- New matchers (SurplusMaxMatcher, SortedMatcher, RoundRobinMatcher)
- Matcher factory in MarketSimulator
- Communication strategy in prompt builders
- ReputationStore
- Allocative efficiency and Gini metrics
- build_reputation_context prompt helper
"""
from __future__ import annotations

import pytest

from src.agents.memory_agent import MemoryStore, ReputationStore
from src.core.config import NegotiationConfig, PromptConfig, SimulationConfig
from src.core.rng import SeededRNG
from src.core.types import (
    ActionType,
    AgentContext,
    AgentRole,
    BuyerState,
    Item,
    NegotiationAction,
    NegotiationResult,
    NegotiationTurn,
    SellerState,
    TerminationReason,
)
from src.evaluation.metrics import compute_allocative_efficiency, compute_surplus_gini
from src.llm.prompts import (
    _COMMUNICATION_STRATEGIES,
    build_deliberative_prompt,
    build_reactive_prompt,
    build_reputation_context,
)
from src.market.matcher import (
    RandomMatcher,
    RoundRobinMatcher,
    SortedMatcher,
    SurplusMaxMatcher,
)


# ── helpers ──────────────────────────────────────────────────────────────

def _item() -> Item:
    return Item(item_id="item_001", name="Widget", reference_price=100.0)


def _buyers(n: int = 5) -> list[BuyerState]:
    """Generate buyers with values 150, 140, 130, ..."""
    return [
        BuyerState(
            buyer_id=f"buyer_{i}",
            value=150.0 - i * 10,
            budget=200.0,
            patience=5,
        )
        for i in range(n)
    ]


def _sellers(n: int = 5) -> list[SellerState]:
    """Generate sellers with costs 60, 70, 80, ..."""
    return [
        SellerState(
            seller_id=f"seller_{i}",
            cost=60.0 + i * 10,
            target_margin=0.15,
            patience=5,
        )
        for i in range(n)
    ]


def _rng() -> SeededRNG:
    return SeededRNG(42)


def _ctx(role: AgentRole = AgentRole.BUYER) -> AgentContext:
    """Basic agent context for prompt testing."""
    return AgentContext(
        item=_item(),
        role=role,
        round_number=2,
        max_rounds=10,
        history=[],
        last_offer=90.0 if role == AgentRole.SELLER else 110.0,
        reservation_price=120.0 if role == AgentRole.BUYER else 80.0,
        budget=130.0 if role == AgentRole.BUYER else None,
        target_margin=0.15 if role == AgentRole.SELLER else None,
    )


def _make_result(
    buyer_value: float, seller_cost: float, deal_price: float | None,
) -> NegotiationResult:
    return NegotiationResult(
        item=_item(),
        buyer_id="buyer_0",
        seller_id="seller_0",
        deal_made=deal_price is not None,
        deal_price=deal_price,
        termination_reason=(
            TerminationReason.ACCEPTED if deal_price
            else TerminationReason.TIMEOUT
        ),
        rounds_taken=3,
        buyer_value=buyer_value,
        seller_cost=seller_cost,
        buyer_surplus=(buyer_value - deal_price) if deal_price else 0.0,
        seller_surplus=(deal_price - seller_cost) if deal_price else 0.0,
    )


# ═══════════════════════════════════════════════════════════════════════
#  Gate toggle tests
# ═══════════════════════════════════════════════════════════════════════

class TestGateToggle:
    """Test that NegotiationConfig.gate_enabled defaults to True and is
    respected by NegotiationSession."""

    def test_default_gate_enabled(self):
        cfg = NegotiationConfig()
        assert cfg.gate_enabled is True

    def test_gate_disabled_config(self):
        cfg = NegotiationConfig(gate_enabled=False)
        assert cfg.gate_enabled is False

    def test_session_accepts_gate_flag(self):
        from src.negotiation.session import NegotiationSession
        from src.agents.rule_based import RuleBasedAgent

        buyer = BuyerState("b1", value=120.0, budget=130.0, patience=5)
        seller = SellerState("s1", cost=80.0, target_margin=0.15, patience=5)
        item = _item()

        # gate_enabled=True — session should have gate on
        session_on = NegotiationSession(
            RuleBasedAgent(), RuleBasedAgent(), item, buyer, seller,
            gate_enabled=True,
        )
        assert session_on.gate_enabled is True

        # gate_enabled=False — session should have gate off
        session_off = NegotiationSession(
            RuleBasedAgent(), RuleBasedAgent(), item, buyer, seller,
            gate_enabled=False,
        )
        assert session_off.gate_enabled is False

    def test_gate_disabled_allows_more_rounds(self):
        """With gate disabled, rule-based agents negotiate beyond round 2."""
        from src.negotiation.session import NegotiationSession
        from src.agents.rule_based import RuleBasedAgent

        buyer = BuyerState("b1", value=120.0, budget=130.0, patience=5)
        seller = SellerState("s1", cost=80.0, target_margin=0.15, patience=5)
        item = _item()

        # Gate ON: should settle quickly (≤3 rounds typically)
        session_on = NegotiationSession(
            RuleBasedAgent(), RuleBasedAgent(), item, buyer, seller,
            max_rounds=10, gate_enabled=True,
        )
        result_on = session_on.run()

        # Gate OFF: rule-based agents should still reach a deal eventually
        session_off = NegotiationSession(
            RuleBasedAgent(), RuleBasedAgent(), item, buyer, seller,
            max_rounds=10, gate_enabled=False,
        )
        result_off = session_off.run()

        # Gate off should take at least as many rounds as gate on
        assert result_off.rounds_taken >= result_on.rounds_taken
        # Both should still make a deal (rule-based agents are rational)
        assert result_on.deal_made
        assert result_off.deal_made


# ═══════════════════════════════════════════════════════════════════════
#  Matcher tests
# ═══════════════════════════════════════════════════════════════════════

class TestSurplusMaxMatcher:

    def test_pairs_highest_zopa_first(self):
        buyers = _buyers(3)   # values: 150, 140, 130
        sellers = _sellers(3)  # costs: 60, 70, 80
        items = [_item()]
        rng = _rng()

        matcher = SurplusMaxMatcher()
        pairs = matcher.match(buyers, sellers, items, rng)

        assert len(pairs) == 3
        # highest ZOPA = 150-60=90, should be matched first
        zopas = [b.value - s.cost for b, s, _ in pairs]
        assert zopas == sorted(zopas, reverse=True)

    def test_excludes_negative_zopa(self):
        """Buyers with value < seller cost should not be matched."""
        buyers = [BuyerState("b0", value=50.0, budget=60.0, patience=5)]
        sellers = [SellerState("s0", cost=100.0, target_margin=0.15, patience=5)]
        items = [_item()]

        matcher = SurplusMaxMatcher()
        pairs = matcher.match(buyers, sellers, items, _rng())
        assert len(pairs) == 0

    def test_empty_inputs(self):
        matcher = SurplusMaxMatcher()
        assert matcher.match([], [], [_item()], _rng()) == []

    def test_greedy_no_double_assignment(self):
        """Each agent appears at most once in the output."""
        buyers = _buyers(5)
        sellers = _sellers(5)
        matcher = SurplusMaxMatcher()
        pairs = matcher.match(buyers, sellers, [_item()], _rng())

        buyer_ids = [b.buyer_id for b, _, _ in pairs]
        seller_ids = [s.seller_id for _, s, _ in pairs]
        assert len(buyer_ids) == len(set(buyer_ids))
        assert len(seller_ids) == len(set(seller_ids))


class TestSortedMatcher:

    def test_pairs_by_descending_value_cost(self):
        buyers = _buyers(3)   # values: 150, 140, 130
        sellers = _sellers(3)  # costs: 60, 70, 80

        matcher = SortedMatcher()
        pairs = matcher.match(buyers, sellers, [_item()], _rng())

        assert len(pairs) == 3
        # highest value buyer (150) should pair with highest cost seller (80)
        assert pairs[0][0].value == 150.0
        assert pairs[0][1].cost == 80.0

    def test_min_of_buyers_sellers(self):
        """Pairs min(|buyers|, |sellers|) agents."""
        buyers = _buyers(5)
        sellers = _sellers(2)
        matcher = SortedMatcher()
        pairs = matcher.match(buyers, sellers, [_item()], _rng())
        assert len(pairs) == 2


class TestRoundRobinMatcher:

    def test_remembers_pairings_across_calls(self):
        buyers = _buyers(3)
        sellers = _sellers(3)
        items = [_item()]
        rng = _rng()

        matcher = RoundRobinMatcher()
        pairs1 = matcher.match(buyers, sellers, items, rng)
        assert len(pairs1) == 3

        # second call with same agents should produce same pairings
        pairs2 = matcher.match(buyers, sellers, items, rng)
        assert len(pairs2) == 3

        for (b1, s1, _), (b2, s2, _) in zip(pairs1, pairs2):
            assert b1.buyer_id == b2.buyer_id
            assert s1.seller_id == s2.seller_id

    def test_new_agents_paired_with_remaining(self):
        buyers = _buyers(2)
        sellers = _sellers(2)
        items = [_item()]
        rng = _rng()

        matcher = RoundRobinMatcher()
        pairs1 = matcher.match(buyers, sellers, items, rng)
        assert len(pairs1) == 2

        # add new agents
        new_buyers = _buyers(2) + [
            BuyerState("buyer_new", value=160.0, budget=200.0, patience=5)
        ]
        new_sellers = _sellers(2) + [
            SellerState("seller_new", cost=50.0, target_margin=0.15, patience=5)
        ]
        pairs2 = matcher.match(new_buyers, new_sellers, items, rng)
        assert len(pairs2) == 3  # 2 remembered + 1 new


class TestMatcherFactory:

    def test_factory_creates_all_types(self):
        from src.market.simulator import MarketSimulator

        for name, cls in [
            ("random", RandomMatcher),
            ("surplus_max", SurplusMaxMatcher),
            ("sorted", SortedMatcher),
            ("round_robin", RoundRobinMatcher),
        ]:
            matcher = MarketSimulator._create_matcher(name)
            assert isinstance(matcher, cls)

    def test_factory_rejects_unknown(self):
        from src.market.simulator import MarketSimulator

        with pytest.raises(ValueError, match="Unknown matching"):
            MarketSimulator._create_matcher("nonexistent")


# ═══════════════════════════════════════════════════════════════════════
#  Communication strategy tests
# ═══════════════════════════════════════════════════════════════════════

class TestCommunicationStrategy:

    def test_strategies_defined(self):
        for key in ("neutral", "assertive", "collaborative", "strategic"):
            assert key in _COMMUNICATION_STRATEGIES

    def test_neutral_is_empty(self):
        assert _COMMUNICATION_STRATEGIES["neutral"] == ""

    def test_strategy_injected_in_reactive_prompt(self):
        ctx = _ctx(AgentRole.BUYER)
        cfg = PromptConfig(communication_strategy="assertive")
        prompt = build_reactive_prompt(ctx, prompt_cfg=cfg)
        assert "COMMUNICATION STRATEGY" in prompt
        assert "assertive" in prompt.lower()

    def test_strategy_injected_in_deliberative_prompt(self):
        ctx = _ctx(AgentRole.SELLER)
        cfg = PromptConfig(communication_strategy="strategic")
        prompt = build_deliberative_prompt(ctx, prompt_cfg=cfg)
        assert "COMMUNICATION STRATEGY" in prompt
        assert "maximise your advantage" in prompt.lower()

    def test_neutral_strategy_not_injected(self):
        ctx = _ctx(AgentRole.BUYER)
        cfg = PromptConfig(communication_strategy="neutral")
        prompt = build_reactive_prompt(ctx, prompt_cfg=cfg)
        assert "COMMUNICATION STRATEGY" not in prompt

    def test_config_field_exists(self):
        cfg = PromptConfig()
        assert cfg.communication_strategy == "neutral"


# ═══════════════════════════════════════════════════════════════════════
#  Reputation tests
# ═══════════════════════════════════════════════════════════════════════

class TestReputationStore:

    def test_empty_reputation(self):
        store = ReputationStore()
        assert store.get_reputation("unknown") is None
        assert store.known_opponents == []

    def test_single_interaction(self):
        store = ReputationStore()
        store.record("seller_0", {
            "deal_made": True, "deal_price": 95.0, "rounds": 3,
        })
        rep = store.get_reputation("seller_0")
        assert rep is not None
        assert rep["interactions"] == 1
        assert rep["deal_rate"] == 1.0
        assert rep["avg_deal_price"] == 95.0

    def test_multiple_interactions(self):
        store = ReputationStore()
        store.record("s1", {"deal_made": True, "deal_price": 90.0, "rounds": 2})
        store.record("s1", {"deal_made": True, "deal_price": 100.0, "rounds": 4})
        store.record("s1", {"deal_made": False, "deal_price": None, "rounds": 10})

        rep = store.get_reputation("s1")
        assert rep["interactions"] == 3
        assert rep["deal_rate"] == pytest.approx(0.67, abs=0.01)
        assert rep["avg_deal_price"] == 95.0  # (90+100)/2
        assert rep["style"] == "moderate"

    def test_known_opponents(self):
        store = ReputationStore()
        store.record("s1", {"deal_made": True, "deal_price": 90.0, "rounds": 2})
        store.record("s2", {"deal_made": False, "deal_price": None, "rounds": 10})
        assert set(store.known_opponents) == {"s1", "s2"}

    def test_cooperative_style(self):
        store = ReputationStore()
        for _ in range(5):
            store.record("s1", {"deal_made": True, "deal_price": 90.0, "rounds": 2})
        rep = store.get_reputation("s1")
        assert rep["style"] == "cooperative"

    def test_unreliable_style(self):
        store = ReputationStore()
        for _ in range(5):
            store.record("s1", {"deal_made": False, "deal_price": None, "rounds": 10})
        rep = store.get_reputation("s1")
        assert rep["style"] == "unreliable"


class TestBuildReputationContext:

    def test_empty_reputation(self):
        assert build_reputation_context({}) == ""

    def test_formats_reputation(self):
        rep = {
            "opponent_id": "seller_42",
            "interactions": 5,
            "deal_rate": 0.8,
            "avg_deal_price": 95.0,
            "avg_rounds": 3.2,
            "style": "cooperative",
        }
        text = build_reputation_context(rep)
        assert "seller_42" in text
        assert "80%" in text
        assert "$95.00" in text
        assert "cooperative" in text
        assert "OPPONENT HISTORY" in text


# ═══════════════════════════════════════════════════════════════════════
#  Allocative efficiency + Gini tests
# ═══════════════════════════════════════════════════════════════════════

class TestAllocativeEfficiency:

    def test_perfect_efficiency(self):
        """All possible surplus captured."""
        results = [
            _make_result(buyer_value=120.0, seller_cost=80.0, deal_price=100.0),
        ]
        eff = compute_allocative_efficiency(results)
        assert eff == 1.0

    def test_zero_efficiency_no_deals(self):
        results = [
            _make_result(buyer_value=120.0, seller_cost=80.0, deal_price=None),
        ]
        eff = compute_allocative_efficiency(results)
        assert eff == 0.0

    def test_partial_efficiency(self):
        results = [
            _make_result(buyer_value=120.0, seller_cost=80.0, deal_price=100.0),
            _make_result(buyer_value=100.0, seller_cost=90.0, deal_price=None),
        ]
        # theoretical max = 40 + 10 = 50, realised = 40
        eff = compute_allocative_efficiency(results)
        assert eff == 0.8

    def test_negative_zopa_excluded(self):
        results = [
            _make_result(buyer_value=50.0, seller_cost=100.0, deal_price=None),
        ]
        eff = compute_allocative_efficiency(results)
        assert eff == 0.0

    def test_empty_results(self):
        assert compute_allocative_efficiency([]) == 0.0


class TestSurplusGini:

    def test_perfect_equality(self):
        assert compute_surplus_gini([10, 10, 10, 10]) == 0.0

    def test_maximum_inequality(self):
        gini = compute_surplus_gini([0, 0, 0, 100])
        assert gini > 0.5  # should be high

    def test_empty(self):
        assert compute_surplus_gini([]) == 0.0

    def test_single(self):
        assert compute_surplus_gini([42]) == 0.0

    def test_moderate_inequality(self):
        gini = compute_surplus_gini([10, 20, 30, 40])
        assert 0 < gini < 0.5


# ═══════════════════════════════════════════════════════════════════════
#  Per-agent memory config test
# ═══════════════════════════════════════════════════════════════════════

class TestPerAgentMemoryConfig:

    def test_default_is_shared(self):
        cfg = SimulationConfig()
        assert cfg.memory_per_agent is False

    def test_can_enable(self):
        cfg = SimulationConfig(memory_per_agent=True)
        assert cfg.memory_per_agent is True
