"""Parse diagnostics for free-language experiment outputs.

Reads events.jsonl files and computes reliability metrics for the
free-language parsing pipeline: parse success rate, retry rate,
invalid action rate, timeout rate, acceptance source breakdown,
and mean response length.
"""
from __future__ import annotations

import json
import os
from typing import Any


def compute_parse_diagnostics(events_jsonl_path: str) -> dict[str, Any]:
    """Compute parse diagnostics from a single events.jsonl file.

    Returns a dict with:
        total_turns: int
        total_sessions: int
        parse_success_rate: float  (turns that extracted price or accept on first attempt)
        retry_rate: float  (turns that used the retry hint)
        reject_from_parse_rate: float  (turns ending in REJECT due to parse failure)
        invalid_action_rate: float  (risk events / total turns)
        timeout_rate: float  (sessions ending in timeout / total sessions)
        deal_rate: float
        accept_price_conflict_count: int
        mean_response_length: float  (characters in raw_llm_output)
        acceptance_sources: dict  (llm_accept, override, parse_fallback counts)
    """
    turns: list[dict] = []
    results: list[dict] = []
    risk_events: list[dict] = []

    with open(events_jsonl_path, "r") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            event = json.loads(line)
            etype = event.get("event")
            if etype == "turn":
                turns.append(event)
            elif etype == "result":
                results.append(event)
            elif etype == "risk":
                risk_events.append(event)

    total_turns = len(turns)
    total_sessions = len(results)

    if total_turns == 0:
        return {
            "total_turns": 0,
            "total_sessions": total_sessions,
            "parse_success_rate": 0.0,
            "retry_rate": 0.0,
            "reject_from_parse_rate": 0.0,
            "invalid_action_rate": 0.0,
            "timeout_rate": 0.0,
            "deal_rate": 0.0,
            "accept_price_conflict_count": 0,
            "mean_response_length": 0.0,
            "acceptance_sources": {},
        }

    # Retry detection: prompt_sent contains the retry hint text
    retry_hint_marker = "Your previous response did not include a valid price offer"
    retry_count = sum(
        1 for t in turns
        if t.get("prompt_sent") and retry_hint_marker in t["prompt_sent"]
    )

    # Parse failure = action is "reject" AND the turn has raw_llm_output
    # (meaning it was an LLM turn that failed to parse, not a rule-based reject)
    reject_from_parse = sum(
        1 for t in turns
        if t.get("action") == "reject" and t.get("raw_llm_output") is not None
    )

    # Parse success = turns with raw_llm_output that are NOT reject
    llm_turns = [t for t in turns if t.get("raw_llm_output") is not None]
    first_attempt_success = len(llm_turns) - retry_count  # approximate
    parse_success_rate = (
        (len(llm_turns) - reject_from_parse) / len(llm_turns)
        if llm_turns else 0.0
    )

    # Accept+price conflict detection
    accept_price_conflicts = sum(
        1 for t in turns
        if t.get("action") == "accept"
        and t.get("raw_llm_output")
        and "ACCEPT+PRICE conflict" in (t.get("override_reason", "") or "")
    )
    # Also check via rationale in message patterns — but since rationale isn't
    # in JSONL, check if there's a prompt_sent that contains a price tag AND
    # the effective action was accept. We'll count from the raw output instead.

    # Timeout and deal rates
    timeouts = sum(1 for r in results if r.get("termination") == "timeout")
    deals = sum(1 for r in results if r.get("deal_made"))

    # Override rate (judge overrides)
    overrides = sum(1 for t in turns if t.get("override_flag"))

    # Mean response length
    response_lengths = [
        len(t["raw_llm_output"]) for t in turns
        if t.get("raw_llm_output") is not None
    ]
    mean_response_length = (
        sum(response_lengths) / len(response_lengths)
        if response_lengths else 0.0
    )

    # Acceptance source breakdown
    llm_accepts = sum(
        1 for t in turns
        if t.get("effective_action") == "accept"
        and t.get("llm_action") == "accept"
        and not t.get("override_flag")
    )
    override_accepts = sum(
        1 for t in turns
        if t.get("effective_action") == "accept"
        and t.get("override_flag")
    )
    # Total accepts from results
    total_accepts = sum(
        1 for t in turns
        if t.get("effective_action") == "accept"
    )

    return {
        "total_turns": total_turns,
        "total_llm_turns": len(llm_turns),
        "total_sessions": total_sessions,
        "parse_success_rate": round(parse_success_rate, 4),
        "retry_rate": round(retry_count / total_turns, 4) if total_turns else 0.0,
        "reject_from_parse_count": reject_from_parse,
        "reject_from_parse_rate": round(reject_from_parse / total_turns, 4) if total_turns else 0.0,
        "invalid_action_rate": round(len(risk_events) / total_turns, 4) if total_turns else 0.0,
        "override_count": overrides,
        "timeout_count": timeouts,
        "timeout_rate": round(timeouts / total_sessions, 4) if total_sessions else 0.0,
        "deal_count": deals,
        "deal_rate": round(deals / total_sessions, 4) if total_sessions else 0.0,
        "accept_price_conflict_count": accept_price_conflicts,
        "mean_response_length": round(mean_response_length, 1),
        "acceptance_sources": {
            "llm_accept": llm_accepts,
            "override_accept": override_accepts,
            "total_accepts": total_accepts,
        },
    }


def compute_diagnostics_for_experiment(run_dir: str) -> dict[str, Any]:
    """Compute parse diagnostics across all events.jsonl files in an experiment.

    Searches for events.jsonl in run_dir and all subdirectories (runs/).
    Returns aggregated diagnostics.
    """
    jsonl_files: list[str] = []
    for root, _dirs, files in os.walk(run_dir):
        for fname in files:
            if fname == "events.jsonl":
                jsonl_files.append(os.path.join(root, fname))

    if not jsonl_files:
        return {"error": f"No events.jsonl found in {run_dir}"}

    # Aggregate across all JSONL files
    agg: dict[str, Any] = {
        "total_turns": 0,
        "total_llm_turns": 0,
        "total_sessions": 0,
        "retry_count": 0,
        "reject_from_parse_count": 0,
        "override_count": 0,
        "timeout_count": 0,
        "deal_count": 0,
        "accept_price_conflict_count": 0,
        "response_length_sum": 0.0,
        "response_count": 0,
        "llm_accepts": 0,
        "override_accepts": 0,
        "total_accepts": 0,
        "risk_events": 0,
        "per_file": [],
    }

    for path in jsonl_files:
        diag = compute_parse_diagnostics(path)
        agg["total_turns"] += diag["total_turns"]
        agg["total_llm_turns"] += diag["total_llm_turns"]
        agg["total_sessions"] += diag["total_sessions"]
        agg["reject_from_parse_count"] += diag["reject_from_parse_count"]
        agg["override_count"] += diag["override_count"]
        agg["timeout_count"] += diag["timeout_count"]
        agg["deal_count"] += diag["deal_count"]
        agg["accept_price_conflict_count"] += diag["accept_price_conflict_count"]
        agg["llm_accepts"] += diag["acceptance_sources"]["llm_accept"]
        agg["override_accepts"] += diag["acceptance_sources"]["override_accept"]
        agg["total_accepts"] += diag["acceptance_sources"]["total_accepts"]
        # For retry rate, re-derive from per-file
        agg["retry_count"] += round(diag["retry_rate"] * diag["total_turns"])
        # Response length
        agg["response_length_sum"] += diag["mean_response_length"] * diag["total_llm_turns"]
        agg["response_count"] += diag["total_llm_turns"]

    tt = agg["total_turns"]
    ts = agg["total_sessions"]
    tl = agg["total_llm_turns"]

    result = {
        "files_processed": len(jsonl_files),
        "total_turns": tt,
        "total_llm_turns": tl,
        "total_sessions": ts,
        "parse_success_rate": round((tl - agg["reject_from_parse_count"]) / tl, 4) if tl else 0.0,
        "retry_rate": round(agg["retry_count"] / tt, 4) if tt else 0.0,
        "reject_from_parse_count": agg["reject_from_parse_count"],
        "reject_from_parse_rate": round(agg["reject_from_parse_count"] / tt, 4) if tt else 0.0,
        "invalid_action_rate": round(agg["override_count"] / tt, 4) if tt else 0.0,
        "override_count": agg["override_count"],
        "timeout_count": agg["timeout_count"],
        "timeout_rate": round(agg["timeout_count"] / ts, 4) if ts else 0.0,
        "deal_count": agg["deal_count"],
        "deal_rate": round(agg["deal_count"] / ts, 4) if ts else 0.0,
        "accept_price_conflict_count": agg["accept_price_conflict_count"],
        "mean_response_length": round(agg["response_length_sum"] / agg["response_count"], 1) if agg["response_count"] else 0.0,
        "acceptance_sources": {
            "llm_accept": agg["llm_accepts"],
            "override_accept": agg["override_accepts"],
            "total_accepts": agg["total_accepts"],
        },
    }
    return result


def write_parse_diagnostics(diagnostics: dict[str, Any], run_dir: str) -> str:
    """Write parse diagnostics as ``parse_diagnostics.json``."""
    path = os.path.join(run_dir, "parse_diagnostics.json")
    with open(path, "w") as f:
        json.dump(diagnostics, f, indent=2)
    return path
