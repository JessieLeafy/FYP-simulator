"""Tests for pure-Python statistical helpers."""
import math
import unittest

from src.evaluation.stats import pearson_correlation, simple_linear_regression


class TestPearsonCorrelation(unittest.TestCase):

    def test_perfect_positive(self):
        xs = [1.0, 2.0, 3.0, 4.0, 5.0]
        ys = [2.0, 4.0, 6.0, 8.0, 10.0]
        r = pearson_correlation(xs, ys)
        self.assertAlmostEqual(r, 1.0, places=6)

    def test_perfect_negative(self):
        xs = [1.0, 2.0, 3.0, 4.0, 5.0]
        ys = [10.0, 8.0, 6.0, 4.0, 2.0]
        r = pearson_correlation(xs, ys)
        self.assertAlmostEqual(r, -1.0, places=6)

    def test_zero_correlation(self):
        xs = [1.0, 2.0, 3.0, 4.0, 5.0]
        ys = [5.0, 5.0, 5.0, 5.0, 5.0]
        r = pearson_correlation(xs, ys)
        self.assertEqual(r, 0.0)

    def test_short_input(self):
        self.assertEqual(pearson_correlation([1.0], [2.0]), 0.0)
        self.assertEqual(pearson_correlation([], []), 0.0)

    def test_mismatched_lengths(self):
        self.assertEqual(pearson_correlation([1.0, 2.0], [3.0]), 0.0)

    def test_known_value(self):
        xs = [1.0, 2.0, 3.0, 4.0]
        ys = [1.0, 3.0, 2.0, 4.0]
        r = pearson_correlation(xs, ys)
        # manual calculation: r ≈ 0.8
        self.assertGreater(r, 0.7)
        self.assertLess(r, 0.9)


class TestSimpleLinearRegression(unittest.TestCase):

    def test_perfect_fit(self):
        xs = [1.0, 2.0, 3.0, 4.0, 5.0]
        ys = [3.0, 5.0, 7.0, 9.0, 11.0]  # y = 2x + 1
        slope, intercept = simple_linear_regression(xs, ys)
        self.assertAlmostEqual(slope, 2.0, places=6)
        self.assertAlmostEqual(intercept, 1.0, places=6)

    def test_flat_line(self):
        xs = [1.0, 2.0, 3.0, 4.0]
        ys = [5.0, 5.0, 5.0, 5.0]
        slope, intercept = simple_linear_regression(xs, ys)
        self.assertAlmostEqual(slope, 0.0, places=6)
        self.assertAlmostEqual(intercept, 5.0, places=6)

    def test_short_input(self):
        self.assertEqual(simple_linear_regression([1.0], [2.0]), (0.0, 0.0))

    def test_zero_variance_x(self):
        xs = [3.0, 3.0, 3.0]
        ys = [1.0, 2.0, 3.0]
        slope, intercept = simple_linear_regression(xs, ys)
        self.assertEqual(slope, 0.0)
        self.assertAlmostEqual(intercept, 2.0, places=6)

    def test_negative_slope(self):
        xs = [1.0, 2.0, 3.0, 4.0]
        ys = [10.0, 8.0, 6.0, 4.0]  # y = -2x + 12
        slope, intercept = simple_linear_regression(xs, ys)
        self.assertAlmostEqual(slope, -2.0, places=6)
        self.assertAlmostEqual(intercept, 12.0, places=6)


if __name__ == "__main__":
    unittest.main()
