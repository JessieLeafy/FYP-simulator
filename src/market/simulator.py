"""Market simulation engine – the main orchestration loop.

Supports two modes:
  - ``session`` (default): runs steps of negotiations, writes summary.
  - ``market``: same loop + per-tick MarketTickStats and tick_end logging.
"""
from __future__ import annotations

import os
import time
from typing import Optional

from src.agents.memory_agent import MemoryStore
from src.core.config import SimulationConfig, resolve_fixed_params
from src.core.logging import EventLogger
from src.core.rng import SeededRNG
from src.core.types import AgentRole, MarketTickStats, NegotiationResult
from src.evaluation.metrics import compute_metrics, compute_tick_stats
from src.evaluation.reports import write_deals_csv, write_summary
from src.llm.backend import OllamaLLMBackend
from src.market.catalog import Catalog
from src.market.matcher import Matcher, RandomMatcher
from src.market.matching import generate_buyers, generate_sellers
from src.market.shocks import apply_shocks
from src.negotiation.session import NegotiationSession


class MarketSimulator:
    """Runs *steps* time-steps (ticks) of buyer/seller generation, matching,
    and negotiation, then writes evaluation outputs.

    In ``market`` mode, per-tick aggregate statistics are computed and
    logged as ``tick_end`` events in the JSONL log.
    """

    def __init__(self, config: SimulationConfig, rng: SeededRNG):
        self.config = config
        self.rng = rng

        # run directory
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        self.run_dir = os.path.join(
            config.output_dir, f"{timestamp}_s{config.seed}"
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
        self.matcher: Matcher = RandomMatcher()

        # lazy LLM backend
        self._backend: Optional[OllamaLLMBackend] = None

        # shared memory stores (for memory agents)
        self._buyer_memory = MemoryStore(k=config.memory_k)
        self._seller_memory = MemoryStore(k=config.memory_k)

        # collected results
        self.results: list[NegotiationResult] = []
        self.tick_stats: list[MarketTickStats] = []

    # ── agent creation ───────────────────────────────────────────────────

    def _get_backend(self) -> OllamaLLMBackend:
        if self._backend is None:
            c = self.config.llm
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

    def _create_agent(self, agent_type: str, role: AgentRole):
        from src.agents.llm_deliberative import LLMDeliberativeAgent
        from src.agents.llm_reactive import LLMReactiveAgent
        from src.agents.memory_agent import MemoryAgent
        from src.agents.rule_based import RuleBasedAgent

        if agent_type == "rule_based":
            return RuleBasedAgent()
        if agent_type == "llm_reactive":
            return LLMReactiveAgent(self._get_backend())
        if agent_type == "llm_deliberative":
            return LLMDeliberativeAgent(self._get_backend())
        if agent_type == "memory":
            store = (
                self._buyer_memory
                if role == AgentRole.BUYER
                else self._seller_memory
            )
            return MemoryAgent(self._get_backend(), memory_store=store)
        raise ValueError(f"Unknown agent type: {agent_type}")

    # ── main loop ────────────────────────────────────────────────────────

    def run(self) -> list[NegotiationResult]:
        cfg = self.config
        buyer_type = cfg.buyer_agent_type or cfg.agent_type
        seller_type = cfg.seller_agent_type or cfg.agent_type
        is_market_mode = cfg.mode == "market"

        # resolve fixed config (None when in distribution mode)
        fixed_cfg = cfg.fixed if cfg.scenario_mode == "fixed" else None

        for step in range(cfg.steps):
            step_rng = self.rng.fork()
            tick_results: list[NegotiationResult] = []

            buyers = generate_buyers(
                step_rng, cfg.buyers_per_step, step, cfg.market, fixed_cfg,
            )
            sellers = generate_sellers(
                step_rng, cfg.sellers_per_step, step, cfg.market, fixed_cfg,
            )

            buyers, sellers = apply_shocks(
                buyers, sellers, step_rng, cfg.shock,
            )

            # use Matcher interface instead of raw match_pairs
            pairs = self.matcher.match(
                buyers, sellers, self.catalog.items, step_rng,
            )

            for buyer, seller, item in pairs:
                buyer_agent = self._create_agent(buyer_type, AgentRole.BUYER)
                seller_agent = self._create_agent(seller_type, AgentRole.SELLER)

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
                )
                result = session.run()

                self.event_logger.log_result(result)
                tick_results.append(result)
                self.results.append(result)

                # feed memory agents
                if hasattr(buyer_agent, "record_outcome"):
                    buyer_agent.record_outcome(result)
                if hasattr(seller_agent, "record_outcome"):
                    seller_agent.record_outcome(result)

            # ── market mode: compute and log per-tick stats ───────────
            if is_market_mode and tick_results:
                stats = compute_tick_stats(step, tick_results)
                self.tick_stats.append(stats)
                self.event_logger.log_tick_stats(stats)

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
