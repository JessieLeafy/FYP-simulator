"""Market simulation engine – the main orchestration loop.

Supports two modes:
  - ``session`` (default): runs steps of negotiations, writes summary.
  - ``market``: same loop + per-tick MarketTickStats and tick_end logging.
"""
from __future__ import annotations

import logging
import os
import time
from typing import Callable, Optional

from src.core.config import SimulationConfig, resolve_fixed_params
from src.core.logging import EventLogger
from src.core.rng import SeededRNG
from src.core.types import AgentRole, MarketTickStats, NegotiationResult
from src.evaluation.metrics import compute_metrics, compute_tick_stats
from src.evaluation.reports import write_deals_csv, write_summary
from src.llm.backend import OllamaLLMBackend
from src.llm.hf_backend import HuggingFaceBackend
from src.market.catalog import Catalog
from src.market.matcher import (
    Matcher,
    RandomMatcher,
    RoundRobinMatcher,
    SortedMatcher,
    SurplusMaxMatcher,
)
from src.market.matching import (
    adjust_pair_for_item,
    generate_buyers,
    generate_sellers,
    validate_market_coherence,
)
from src.market.shocks import apply_shocks
from src.negotiation.session import NegotiationSession


class MarketSimulator:
    """Runs *steps* time-steps (ticks) of buyer/seller generation, matching,
    and negotiation, then writes evaluation outputs.

    In ``market`` mode, per-tick aggregate statistics are computed and
    logged as ``tick_end`` events in the JSONL log.
    """

    def __init__(self, config: SimulationConfig, rng: SeededRNG,
                 backend: Optional[OllamaLLMBackend | HuggingFaceBackend] = None):
        self.config = config
        self.rng = rng

        # run directory — use high-resolution timestamp + agent_type to avoid
        # collisions when multiple conditions share the same seed and start
        # within the same wall-clock second (e.g. fast rule_based runs).
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        agent_label = (config.buyer_agent_type or config.agent_type or "agent")[:12]
        self.run_dir = os.path.join(
            config.output_dir, f"{timestamp}_{agent_label}_s{config.seed}"
        )
        os.makedirs(self.run_dir, exist_ok=True)

        # fixed-mode: pass fixed reference prices to catalog
        fixed_ref = None
        if config.scenario_mode == "fixed" and config.fixed.item_reference_price is not None:
            fixed_ref = config.fixed.item_reference_price

        # catalog
        self.catalog = Catalog(
            rng=rng,
            num_types=config.market.num_item_types,
            ref_price_min=config.market.item_ref_price_min,
            ref_price_max=config.market.item_ref_price_max,
            fixed_ref_prices=fixed_ref,
        )

        # logger
        self.event_logger = EventLogger(self.run_dir)

        # matcher (pluggable via Matcher interface)
        self.matcher: Matcher = self._create_matcher(config.matching)

        # lazy LLM backend (reuse pre-built backend if provided)
        self._backend: Optional[OllamaLLMBackend | HuggingFaceBackend] = backend

        # anchor tracking: effective reference price per item_id
        # (used by anchor_mode "updated" and "no_anchor")
        self._original_ref_prices: dict[str, float] = {
            item.item_id: item.reference_price
            for item in self.catalog.items
        }
        self._effective_anchors: dict[str, float] = dict(self._original_ref_prices)

        # collected results
        self.results: list[NegotiationResult] = []
        self.tick_stats: list[MarketTickStats] = []

    # ── matcher creation ─────────────────────────────────────────────────

    @staticmethod
    def _create_matcher(name: str) -> Matcher:
        """Instantiate a Matcher by config name."""
        if name == "random":
            return RandomMatcher()
        if name == "surplus_max":
            return SurplusMaxMatcher()
        if name == "sorted":
            return SortedMatcher()
        if name == "round_robin":
            return RoundRobinMatcher()
        raise ValueError(
            f"Unknown matching strategy: {name!r}. "
            f"Available: random, surplus_max, sorted, round_robin"
        )

    # ── agent creation ───────────────────────────────────────────────────

    def _get_backend(self) -> OllamaLLMBackend | HuggingFaceBackend:
        if self._backend is None:
            c = self.config.llm
            if getattr(c, "backend", "ollama") == "huggingface":
                self._backend = HuggingFaceBackend(
                    model=c.model,
                    device=getattr(c, "device", "cuda:0"),
                    temperature=c.temperature,
                    max_tokens=c.max_tokens,
                    debug=c.debug,
                    quantize=getattr(c, "quantize", None) or None,
                )
            else:
                self._backend = OllamaLLMBackend(
                    model=c.model,
                    base_url=c.base_url,
                    temperature=c.temperature,
                    max_tokens=c.max_tokens,
                    timeout_sec=c.timeout_sec,
                    max_retries=c.max_retries,
                    debug=c.debug,
                )
        return self._backend

    def _create_agent(
        self, agent_type: str, role: AgentRole, agent_id: str = "",
    ):
        from src.agents.llm_free_language import LLMFreeLanguageAgent
        from src.agents.rule_based import RuleBasedAgent

        pcfg = self.config.prompt

        if agent_type == "rule_based":
            return RuleBasedAgent()
        if agent_type == "llm_free_language":
            return LLMFreeLanguageAgent(self._get_backend(), prompt_cfg=pcfg)
        raise ValueError(f"Unknown agent type: {agent_type}")

    # ── main loop ────────────────────────────────────────────────────────

    def run(
        self,
        on_session: Callable[[NegotiationResult], None] | None = None,
    ) -> list[NegotiationResult]:
        cfg = self.config
        buyer_type = cfg.buyer_agent_type or cfg.agent_type
        seller_type = cfg.seller_agent_type or cfg.agent_type
        is_market_mode = cfg.mode == "market"

        # resolve fixed config (None when in distribution mode)
        fixed_cfg = cfg.fixed if cfg.scenario_mode == "fixed" else None

        # Use stable IDs for round-robin matching (needed for reputation tracking)
        use_stable_ids = cfg.matching == "round_robin"

        for step in range(cfg.steps):
            step_rng = self.rng.fork()
            tick_results: list[NegotiationResult] = []

            buyers = generate_buyers(
                step_rng, cfg.buyers_per_step, step, cfg.market, fixed_cfg,
                stable_ids=use_stable_ids,
            )
            sellers = generate_sellers(
                step_rng, cfg.sellers_per_step, step, cfg.market, fixed_cfg,
                stable_ids=use_stable_ids,
            )

            buyers, sellers = apply_shocks(
                buyers, sellers, step_rng, cfg.shock,
            )

            # use Matcher interface instead of raw match_pairs
            pairs = self.matcher.match(
                buyers, sellers, self.catalog.items, step_rng,
            )

            # Post-match coherence: resample private stats relative to
            # item reference price so each triple is economically sensible.
            if cfg.market.coherent_sampling and cfg.scenario_mode != "fixed":
                for buyer, seller, item in pairs:
                    adjust_pair_for_item(
                        buyer, seller, item, step_rng, cfg.market,
                    )

            # Validate coherence (logs warnings for any remaining issues)
            coherence_warnings = validate_market_coherence(pairs)
            for w in coherence_warnings:
                logging.getLogger(__name__).warning(w)

            # ── apply anchor mode ──────────────────────────────────────
            anchor_mode = cfg.market.anchor_mode
            if anchor_mode == "no_anchor":
                for _, _, item in pairs:
                    item.reference_price = 0.0
            elif anchor_mode == "updated":
                for _, _, item in pairs:
                    item.reference_price = self._effective_anchors.get(
                        item.item_id, item.reference_price,
                    )

            for buyer, seller, item in pairs:
                buyer_agent = self._create_agent(
                    buyer_type, AgentRole.BUYER, buyer.buyer_id,
                )
                seller_agent = self._create_agent(
                    seller_type, AgentRole.SELLER, seller.seller_id,
                )

                session = NegotiationSession(
                    buyer_agent=buyer_agent,
                    seller_agent=seller_agent,
                    item=item,
                    buyer=buyer,
                    seller=seller,
                    max_rounds=cfg.negotiation.max_rounds,
                    min_price=cfg.negotiation.min_price,
                    max_price=cfg.negotiation.max_price,
                    event_logger=self.event_logger,
                    time_step=step,
                    gate_enabled=cfg.negotiation.gate_enabled,
                )
                result = session.run()

                self.event_logger.log_result(result)
                tick_results.append(result)
                self.results.append(result)

                if on_session is not None:
                    on_session(result)

            # ── market mode: compute and log per-tick stats ───────────
            if is_market_mode and tick_results:
                stats = compute_tick_stats(step, tick_results)
                self.tick_stats.append(stats)
                self.event_logger.log_tick_stats(stats)

            # ── update effective anchors for next tick ────────────────
            if cfg.market.anchor_mode == "updated" and tick_results:
                # group deal prices by item
                item_prices: dict[str, list[float]] = {}
                for r in tick_results:
                    if r.deal_made and r.deal_price is not None:
                        item_prices.setdefault(r.item.item_id, []).append(
                            r.deal_price,
                        )
                for iid, prices in item_prices.items():
                    self._effective_anchors[iid] = (
                        sum(prices) / len(prices)
                    )

        # ── finalise ─────────────────────────────────────────────────────
        self.event_logger.close()
        metrics = compute_metrics(self.results)

        # inject scenario metadata into summary
        metrics["scenario_mode"] = cfg.scenario_mode
        metrics["mode"] = cfg.mode
        if cfg.scenario_mode == "fixed":
            metrics["fixed_params"] = resolve_fixed_params(cfg)

        if is_market_mode:
            metrics["num_ticks"] = cfg.steps

        write_summary(metrics, self.run_dir)
        write_deals_csv(self.results, self.run_dir)
        return self.results
