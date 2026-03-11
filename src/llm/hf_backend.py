"""HuggingFace Transformers backend – drop-in replacement for OllamaLLMBackend.

Exposes the same ``generate(prompt) -> str`` interface so it can be used
with the existing simulator pipeline without any changes to agents,
sessions, or prompts.

Requires: torch, transformers, accelerate
"""
from __future__ import annotations

import logging
import time
from typing import Optional

logger = logging.getLogger(__name__)

# Lazy imports so the rest of the codebase doesn't break when
# torch/transformers aren't installed (e.g. on a dev laptop).
_torch = None
_AutoModelForCausalLM = None
_AutoTokenizer = None


def _ensure_imports():
    global _torch, _AutoModelForCausalLM, _AutoTokenizer
    if _torch is None:
        import torch as _t
        from transformers import AutoModelForCausalLM as _M, AutoTokenizer as _T
        _torch = _t
        _AutoModelForCausalLM = _M
        _AutoTokenizer = _T


class HuggingFaceBackend:
    """Local HuggingFace model with the same interface as OllamaLLMBackend."""

    def __init__(
        self,
        model: str = "Qwen/Qwen2.5-7B-Instruct",
        device: str = "cuda:0",
        temperature: float = 0.4,
        max_tokens: int = 300,
        debug: bool = False,
        # Unused but accepted for interface compatibility with LLMConfig
        base_url: str = "",
        timeout_sec: float = 30.0,
        max_retries: int = 3,
        proxy: Optional[str] = None,
    ):
        _ensure_imports()

        self.model_name = model
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.debug = debug
        self._call_count = 0

        logger.info("Loading tokenizer: %s", model)
        self.tokenizer = _AutoTokenizer.from_pretrained(
            model, trust_remote_code=True,
        )
        if self.tokenizer.pad_token is None:
            self.tokenizer.pad_token = self.tokenizer.eos_token

        logger.info("Loading model: %s → %s", model, device)
        load_kwargs = {"dtype": _torch.float16, "trust_remote_code": True}
        if device == "auto":
            load_kwargs["device_map"] = "auto"
        else:
            load_kwargs["device_map"] = {"": device}

        self.model = _AutoModelForCausalLM.from_pretrained(model, **load_kwargs)
        self.model.eval()
        logger.info(
            "Model loaded. Device map: %s",
            getattr(self.model, "hf_device_map", device),
        )

    def generate(self, prompt: str, **overrides) -> str:
        """Generate text from *prompt*.  Returns raw string (same as Ollama)."""
        temperature = overrides.get("temperature", self.temperature)
        max_tokens = overrides.get("max_tokens", self.max_tokens)

        # Apply chat template if available
        if hasattr(self.tokenizer, "chat_template") and self.tokenizer.chat_template:
            messages = [{"role": "user", "content": prompt}]
            text = self.tokenizer.apply_chat_template(
                messages, tokenize=False, add_generation_prompt=True,
            )
        else:
            text = prompt

        inputs = self.tokenizer(text, return_tensors="pt").to(self.model.device)

        t0 = time.time()
        with _torch.no_grad():
            outputs = self.model.generate(
                **inputs,
                max_new_tokens=max_tokens,
                temperature=temperature,
                do_sample=True,
                top_p=0.9,
                pad_token_id=self.tokenizer.pad_token_id,
            )
        elapsed = time.time() - t0

        new_tokens = outputs[0][inputs["input_ids"].shape[1]:]
        response = self.tokenizer.decode(new_tokens, skip_special_tokens=True).strip()

        self._call_count += 1
        if self.debug:
            logger.debug(
                "HF response (%d tokens, %.1fs): %s",
                len(new_tokens), elapsed, response[:300],
            )
        return response

    @property
    def call_count(self) -> int:
        return self._call_count
