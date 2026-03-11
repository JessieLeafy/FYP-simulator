#!/usr/bin/env python3
"""Standalone free-language negotiation test for HuggingFace models.

Runs a single buyer–seller negotiation session with full prompt/output logging.
Designed to test model capabilities on a GPU server with transformers.

Usage:
    python run_free_language_test.py --model meta-llama/Llama-3.1-8B-Instruct
    python run_free_language_test.py --model Qwen/Qwen2.5-7B-Instruct
    python run_free_language_test.py --model mistralai/Mistral-7B-Instruct-v0.3
    python run_free_language_test.py --model Qwen/Qwen2.5-72B-Instruct --device "auto"
"""
from __future__ import annotations

import argparse
import json
import os
import re
import time
from datetime import datetime
from pathlib import Path

import torch
from transformers import AutoModelForCausalLM, AutoTokenizer

# ═══════════════════════════════════════════════════════════════════════
#  Scenario config
# ═══════════════════════════════════════════════════════════════════════

SCENARIO = {
    "item_name": "Wireless Headphones",
    "reference_price": 80.00,
    "buyer_value": 100.00,       # max willingness to pay
    "buyer_budget": 120.00,
    "seller_cost": 60.00,        # min acceptable (private)
    "seller_margin": 0.20,
    "max_rounds": 10,
}

# ═══════════════════════════════════════════════════════════════════════
#  Prompt builders (mirrors src/llm/prompts.py)
# ═══════════════════════════════════════════════════════════════════════

def build_buyer_prompt(history: list[dict], round_num: int, cfg: dict) -> str:
    cap = min(cfg["buyer_value"], cfg["buyer_budget"])
    remaining = cfg["max_rounds"] - round_num - 1
    history_str = _format_history(history) if history else "(no conversation yet)"

    return f"""You are Buyer, a buyer looking for a good deal on "{cfg['item_name']}". You are polite, strategic, and want to get the best price within your budget.

Round {round_num + 1} of {cfg['max_rounds']} ({remaining} remaining).

Conversation History:
{history_str}

Please respond naturally as Buyer would. Be strategic but realistic in your negotiation.

IMPORTANT:
- Your top price is ${cap:.2f} (confidential, do not reveal).
- CRITICAL: In each turn, you MUST make exactly ONE price offer using the format:
  ### BUYER_PRICE($X) ###
- Example: "I can offer ### BUYER_PRICE(${cap * 0.6:.2f}) ### for this."
- Example: "How about ### BUYER_PRICE(${cap * 0.7:.2f}) ###?"
- This specific format is required for the system to correctly extract your offer price.
- NEVER reveal your maximum acceptable price to the seller.
- Keep communication short (150 words or less), clear, and focused on negotiation.

DEAL AGREEMENT INSTRUCTION:
- Only finalize the transaction when you believe the price is reasonably balanced.
- If you decide to accept the deal, you MUST include the exact phrase "MAKE_DEAL" in your response.
- Example: "That sounds acceptable to me. MAKE_DEAL"

Now, respond as Buyer:"""


def build_seller_prompt(history: list[dict], round_num: int, cfg: dict) -> str:
    cost = cfg["seller_cost"]
    margin = cfg["seller_margin"]
    initial_price = cost * (1 + 2 * margin)
    remaining = cfg["max_rounds"] - round_num - 1
    history_str = _format_history(history) if history else "(no conversation yet)"

    return f"""You are Seller, a seller trying to maximize profit on "{cfg['item_name']}" while being reasonable. You are professional, friendly, and want to close a deal that benefits both parties.

Round {round_num + 1} of {cfg['max_rounds']} ({remaining} remaining).

Conversation History:
{history_str}

Please respond naturally as Seller would. Be strategic but realistic in your negotiation.

IMPORTANT REMINDERS:
- Your initial asking price is ${initial_price:.2f}.
- Your minimum acceptable price (confidential) is ${cost:.2f}. Never reveal it.
- CRITICAL: In each turn, you MUST make exactly ONE price offer using the format:
  ### SELLER_PRICE($X) ###
- Example: "I can offer ### SELLER_PRICE(${initial_price:.2f}) ### for this product."
- Example: "How about ### SELLER_PRICE(${cost * 1.2:.2f}) ###?"
- This specific format is required for the system to correctly extract your offer price.
- NEVER reveal your minimum acceptable price to the buyer.
- Keep communication short (150 words or less), professional, and negotiation-focused.

DEAL AGREEMENT INSTRUCTION:
- Only finalize the transaction when you believe the price is reasonably balanced.
- If you decide to accept the deal, you MUST include the exact phrase "MAKE_DEAL" in your response.
- Example: "That sounds acceptable to me. MAKE_DEAL"

Now, respond as Seller:"""


def _format_history(history: list[dict]) -> str:
    lines = []
    for turn in history:
        lines.append(f"[Round {turn['round'] + 1}] {turn['role'].upper()}: {turn['message']}")
    return "\n".join(lines)

# ═══════════════════════════════════════════════════════════════════════
#  Parsing (mirrors src/negotiation/parser.py)
# ═══════════════════════════════════════════════════════════════════════

_ROLE_PRICE_TAG_RE = re.compile(
    r"###\s*(?:BUYER_PRICE|SELLER_PRICE)\(\s*\$\s*([\d]+(?:\.[\d]+)?)\s*\)\s*###",
    re.IGNORECASE,
)
_BARE_PRICE_RE = re.compile(r"\$\s*([\d]+(?:\.[\d]+)?)")
_ACCEPT_KEYWORDS = ("ACCEPT_DEAL", "MAKE_DEAL")
_THINK_RE = re.compile(r"<think>.*?</think>", re.DOTALL | re.IGNORECASE)


def extract_price(text: str) -> float | None:
    matches = _ROLE_PRICE_TAG_RE.findall(text)
    if matches:
        return float(matches[-1])
    bare = _BARE_PRICE_RE.findall(text)
    if bare:
        return float(bare[-1])
    return None


def detect_accept(text: str) -> bool:
    upper = text.upper()
    return any(kw in upper for kw in _ACCEPT_KEYWORDS)

# ═══════════════════════════════════════════════════════════════════════
#  LLM backend (HuggingFace transformers)
# ═══════════════════════════════════════════════════════════════════════

class HFBackend:
    """HuggingFace transformers inference backend."""

    def __init__(
        self,
        model_name: str,
        device: str = "cuda:0",
        temperature: float = 0.4,
        max_new_tokens: int = 300,
    ):
        self.model_name = model_name
        self.temperature = temperature
        self.max_new_tokens = max_new_tokens

        print(f"\n[*] Loading tokenizer: {model_name}")
        self.tokenizer = AutoTokenizer.from_pretrained(
            model_name, trust_remote_code=True
        )
        if self.tokenizer.pad_token is None:
            self.tokenizer.pad_token = self.tokenizer.eos_token

        print(f"[*] Loading model: {model_name} → {device}")
        load_kwargs = {"torch_dtype": torch.float16, "trust_remote_code": True}
        if device == "auto":
            load_kwargs["device_map"] = "auto"  # multi-GPU
        else:
            load_kwargs["device_map"] = {"": device}

        self.model = AutoModelForCausalLM.from_pretrained(model_name, **load_kwargs)
        self.model.eval()
        print(f"[*] Model loaded. Device map: {getattr(self.model, 'hf_device_map', device)}")

    def generate(self, prompt: str) -> str:
        # Use chat template if available
        if hasattr(self.tokenizer, "chat_template") and self.tokenizer.chat_template:
            messages = [{"role": "user", "content": prompt}]
            text = self.tokenizer.apply_chat_template(
                messages, tokenize=False, add_generation_prompt=True
            )
        else:
            text = prompt

        inputs = self.tokenizer(text, return_tensors="pt").to(self.model.device)

        t0 = time.time()
        with torch.no_grad():
            outputs = self.model.generate(
                **inputs,
                max_new_tokens=self.max_new_tokens,
                temperature=self.temperature,
                do_sample=True,
                top_p=0.9,
                pad_token_id=self.tokenizer.pad_token_id,
            )
        elapsed = time.time() - t0

        # Decode only new tokens
        new_tokens = outputs[0][inputs["input_ids"].shape[1]:]
        response = self.tokenizer.decode(new_tokens, skip_special_tokens=True).strip()
        n_tokens = len(new_tokens)

        return response, elapsed, n_tokens

# ═══════════════════════════════════════════════════════════════════════
#  Session runner
# ═══════════════════════════════════════════════════════════════════════

def run_session(backend: HFBackend, cfg: dict, log_dir: Path):
    """Run a single buyer–seller free-language negotiation session."""
    history: list[dict] = []
    log_entries: list[dict] = []
    deal_made = False
    deal_price = None
    deal_round = None

    zopa_low = cfg["seller_cost"]
    zopa_high = cfg["buyer_value"]

    print(f"\n{'='*70}")
    print(f"  FREE-LANGUAGE NEGOTIATION SESSION")
    print(f"  Model: {backend.model_name}")
    print(f"  Item: {cfg['item_name']} (ref ${cfg['reference_price']:.2f})")
    print(f"  Buyer value: ${cfg['buyer_value']:.2f} | Seller cost: ${cfg['seller_cost']:.2f}")
    print(f"  ZOPA: ${zopa_low:.2f} – ${zopa_high:.2f}")
    print(f"  Max rounds: {cfg['max_rounds']}")
    print(f"{'='*70}\n")

    for round_num in range(cfg["max_rounds"]):
        # ── Buyer turn ────────────────────────────────────────
        buyer_prompt = build_buyer_prompt(history, round_num, cfg)
        buyer_raw, buyer_time, buyer_tokens = backend.generate(buyer_prompt)
        buyer_cleaned = _THINK_RE.sub("", buyer_raw).strip()
        buyer_price = extract_price(buyer_cleaned)
        buyer_accept = detect_accept(buyer_cleaned)

        buyer_entry = {
            "round": round_num,
            "role": "buyer",
            "prompt": buyer_prompt,
            "raw_output": buyer_raw,
            "cleaned_output": buyer_cleaned,
            "extracted_price": buyer_price,
            "accept_detected": buyer_accept,
            "gen_time_sec": round(buyer_time, 2),
            "n_tokens": buyer_tokens,
        }
        log_entries.append(buyer_entry)

        print(f"--- Round {round_num + 1} | BUYER ---")
        print(f"  Output: {buyer_cleaned[:200]}{'...' if len(buyer_cleaned) > 200 else ''}")
        print(f"  Price: ${buyer_price:.2f}" if buyer_price else "  Price: NONE")
        print(f"  Accept: {buyer_accept} | Tokens: {buyer_tokens} | Time: {buyer_time:.1f}s")

        history.append({
            "round": round_num,
            "role": "buyer",
            "message": buyer_cleaned,
            "price": buyer_price,
        })

        if buyer_accept:
            deal_made = True
            deal_price = buyer_price or (history[-2]["price"] if len(history) >= 2 else None)
            deal_round = round_num
            print(f"\n  >>> BUYER ACCEPTS DEAL at round {round_num + 1}! <<<\n")
            break

        # ── Seller turn ───────────────────────────────────────
        seller_prompt = build_seller_prompt(history, round_num, cfg)
        seller_raw, seller_time, seller_tokens = backend.generate(seller_prompt)
        seller_cleaned = _THINK_RE.sub("", seller_raw).strip()
        seller_price = extract_price(seller_cleaned)
        seller_accept = detect_accept(seller_cleaned)

        seller_entry = {
            "round": round_num,
            "role": "seller",
            "prompt": seller_prompt,
            "raw_output": seller_raw,
            "cleaned_output": seller_cleaned,
            "extracted_price": seller_price,
            "accept_detected": seller_accept,
            "gen_time_sec": round(seller_time, 2),
            "n_tokens": seller_tokens,
        }
        log_entries.append(seller_entry)

        print(f"--- Round {round_num + 1} | SELLER ---")
        print(f"  Output: {seller_cleaned[:200]}{'...' if len(seller_cleaned) > 200 else ''}")
        print(f"  Price: ${seller_price:.2f}" if seller_price else "  Price: NONE")
        print(f"  Accept: {seller_accept} | Tokens: {seller_tokens} | Time: {seller_time:.1f}s")

        history.append({
            "round": round_num,
            "role": "seller",
            "message": seller_cleaned,
            "price": seller_price,
        })

        if seller_accept:
            deal_made = True
            deal_price = seller_price or buyer_price
            deal_round = round_num
            print(f"\n  >>> SELLER ACCEPTS DEAL at round {round_num + 1}! <<<\n")
            break

        print()

    # ── Summary ───────────────────────────────────────────────────────
    print(f"\n{'='*70}")
    print(f"  SESSION SUMMARY")
    print(f"{'='*70}")
    if deal_made:
        print(f"  Result: DEAL at round {deal_round + 1}")
        print(f"  Deal price: ${deal_price:.2f}" if deal_price else "  Deal price: unknown")
        if deal_price:
            buyer_surplus = cfg["buyer_value"] - deal_price
            seller_surplus = deal_price - cfg["seller_cost"]
            print(f"  Buyer surplus: ${buyer_surplus:.2f}")
            print(f"  Seller surplus: ${seller_surplus:.2f}")
            in_zopa = zopa_low <= deal_price <= zopa_high
            print(f"  In ZOPA: {in_zopa}")
    else:
        print(f"  Result: NO DEAL (exhausted {cfg['max_rounds']} rounds)")

    # Price trajectory
    prices = [(e["round"], e["role"], e["extracted_price"])
              for e in log_entries if e["extracted_price"] is not None]
    if prices:
        print(f"\n  Price trajectory:")
        for r, role, p in prices:
            print(f"    Round {r+1} {role:6s}: ${p:.2f}")

    print(f"{'='*70}\n")

    # ── Save full log ─────────────────────────────────────────────────
    summary = {
        "model": backend.model_name,
        "scenario": cfg,
        "deal_made": deal_made,
        "deal_price": deal_price,
        "deal_round": deal_round,
        "total_rounds": len(set(e["round"] for e in log_entries)),
        "price_trajectory": prices,
        "timestamp": datetime.now().isoformat(),
    }

    model_short = backend.model_name.split("/")[-1]
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_path = log_dir / f"session_{model_short}_{ts}.json"
    log_path.parent.mkdir(parents=True, exist_ok=True)

    with open(log_path, "w") as f:
        json.dump({"summary": summary, "turns": log_entries}, f, indent=2)

    print(f"[*] Full log saved to: {log_path}")
    return summary

# ═══════════════════════════════════════════════════════════════════════
#  CLI
# ═══════════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(description="Free-language negotiation model test")
    parser.add_argument("--model", required=True, help="HuggingFace model ID")
    parser.add_argument("--device", default="cuda:0",
                        help="Device: cuda:0, cuda:1, auto (multi-GPU)")
    parser.add_argument("--temperature", type=float, default=0.4)
    parser.add_argument("--max-tokens", type=int, default=300)
    parser.add_argument("--max-rounds", type=int, default=10)
    parser.add_argument("--log-dir", default="logs/free_language_test",
                        help="Directory to save session logs")
    args = parser.parse_args()

    SCENARIO["max_rounds"] = args.max_rounds

    backend = HFBackend(
        model_name=args.model,
        device=args.device,
        temperature=args.temperature,
        max_new_tokens=args.max_tokens,
    )

    log_dir = Path(args.log_dir)
    run_session(backend, SCENARIO, log_dir)


if __name__ == "__main__":
    main()
