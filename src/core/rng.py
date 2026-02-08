"""Seeded random number generator for reproducibility."""
from __future__ import annotations

import random


class SeededRNG:
    """Wrapper around random.Random for deterministic simulation."""

    def __init__(self, seed: int):
        self._rng = random.Random(seed)
        self._seed = seed

    @property
    def seed(self) -> int:
        return self._seed

    def uniform(self, a: float, b: float) -> float:
        return self._rng.uniform(a, b)

    def randint(self, a: int, b: int) -> int:
        return self._rng.randint(a, b)

    def choice(self, seq: list):
        return self._rng.choice(seq)

    def shuffle(self, seq: list) -> None:
        self._rng.shuffle(seq)

    def random(self) -> float:
        return self._rng.random()

    def gauss(self, mu: float, sigma: float) -> float:
        return self._rng.gauss(mu, sigma)

    def fork(self) -> SeededRNG:
        """Create a child RNG with a derived seed for sub-tasks."""
        child_seed = self._rng.randint(0, 2**31 - 1)
        return SeededRNG(child_seed)
