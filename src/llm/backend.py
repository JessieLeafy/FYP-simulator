"""Ollama LLM backend using only the Python standard library."""
from __future__ import annotations

import json
import logging
import time
import urllib.error
import urllib.request
from typing import Any, Optional

logger = logging.getLogger(__name__)


class OllamaLLMBackend:
    """HTTP client for Ollama's /api/generate endpoint."""

    def __init__(
        self,
        model: str = "qwen2.5:3b",
        base_url: str = "http://localhost:11434",
        temperature: float = 0.2,
        max_tokens: int = 256,
        timeout_sec: float = 30.0,
        max_retries: int = 3,
        debug: bool = False,
    ):
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.timeout_sec = timeout_sec
        self.max_retries = max_retries
        self.debug = debug
        self._call_count = 0

    def generate(self, prompt: str, **overrides: Any) -> str:
        """Send a prompt to Ollama and return the generated text.

        Retries with exponential back-off on transient failures.
        """
        model = overrides.get("model", self.model)
        temperature = overrides.get("temperature", self.temperature)
        max_tokens = overrides.get("max_tokens", self.max_tokens)
        timeout = overrides.get("timeout_sec", self.timeout_sec)

        payload = {
            "model": model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens,
            },
        }

        url = f"{self.base_url}/api/generate"
        data = json.dumps(payload).encode("utf-8")

        if self.debug:
            logger.debug(
                "Ollama request #%d  model=%s  prompt_len=%d",
                self._call_count, model, len(prompt),
            )

        last_error: Optional[Exception] = None
        for attempt in range(self.max_retries):
            try:
                req = urllib.request.Request(
                    url,
                    data=data,
                    headers={"Content-Type": "application/json"},
                    method="POST",
                )
                with urllib.request.urlopen(req, timeout=timeout) as resp:
                    if resp.status != 200:
                        raise RuntimeError(
                            f"Ollama returned HTTP {resp.status}"
                        )
                    body = json.loads(resp.read().decode("utf-8"))

                response_text: str = body.get("response", "")
                self._call_count += 1

                if self.debug:
                    logger.debug(
                        "Ollama response (first 300 chars): %s",
                        response_text[:300],
                    )
                return response_text

            except (
                urllib.error.URLError,
                urllib.error.HTTPError,
                OSError,
                RuntimeError,
                json.JSONDecodeError,
            ) as exc:
                last_error = exc
                wait = min(2 ** attempt, 16) + 0.1 * attempt
                logger.warning(
                    "Ollama request failed (attempt %d/%d): %s  – retrying in %.1fs",
                    attempt + 1, self.max_retries, exc, wait,
                )
                time.sleep(wait)

        raise ConnectionError(
            f"Ollama request failed after {self.max_retries} attempts: {last_error}"
        )

    @property
    def call_count(self) -> int:
        return self._call_count
