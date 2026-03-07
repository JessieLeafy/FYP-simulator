"""Pure-Python statistical helpers for experiment analysis.

No external dependencies — all computations use stdlib only.
"""
from __future__ import annotations

import math


def pearson_correlation(xs: list[float], ys: list[float]) -> float:
    """Compute Pearson product-moment correlation coefficient.

    Returns 0.0 when the input is too short or has zero variance.
    """
    n = len(xs)
    if n != len(ys) or n < 2:
        return 0.0

    mean_x = sum(xs) / n
    mean_y = sum(ys) / n

    cov = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys))
    var_x = sum((x - mean_x) ** 2 for x in xs)
    var_y = sum((y - mean_y) ** 2 for y in ys)

    denom = math.sqrt(var_x * var_y)
    if denom == 0:
        return 0.0
    return cov / denom


def simple_linear_regression(
    xs: list[float], ys: list[float],
) -> tuple[float, float]:
    """Ordinary least-squares fit: y = slope * x + intercept.

    Returns ``(slope, intercept)``.  Returns ``(0.0, 0.0)`` when the
    input is degenerate.
    """
    n = len(xs)
    if n != len(ys) or n < 2:
        return 0.0, 0.0

    mean_x = sum(xs) / n
    mean_y = sum(ys) / n

    ss_xx = sum((x - mean_x) ** 2 for x in xs)
    if ss_xx == 0:
        return 0.0, mean_y

    ss_xy = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys))
    slope = ss_xy / ss_xx
    intercept = mean_y - slope * mean_x
    return slope, intercept
