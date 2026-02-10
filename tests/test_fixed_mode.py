"""Tests for fixed-value scenario mode: ParameterSource and deterministic draws."""
import unittest

from src.core.config import FixedScenarioConfig
from src.core.rng import SeededRNG
from src.market.matching import ParameterSource, generate_buyers, generate_sellers
from src.core.config import MarketConfig


class TestParameterSourceScalar(unittest.TestCase):

    def test_fixed_scalar_always_same(self):
        src = ParameterSource(fixed_value=42.0)
        rng = SeededRNG(1)
        draws = [src.draw(rng) for _ in range(10)]
        self.assertTrue(all(d == 42.0 for d in draws))

    def test_distribution_when_no_fixed(self):
        src = ParameterSource(dist_min=10.0, dist_max=20.0)
        rng = SeededRNG(1)
        draws = [src.draw(rng) for _ in range(50)]
        self.assertTrue(all(10.0 <= d <= 20.0 for d in draws))
        self.assertGreater(len(set(draws)), 1, "should produce varied draws")

    def test_is_int_flag(self):
        src = ParameterSource(fixed_value=5, is_int=True)
        rng = SeededRNG(1)
        val = src.draw(rng)
        self.assertIsInstance(val, int)
        self.assertEqual(val, 5)


class TestParameterSourceEnumerated(unittest.TestCase):

    def test_cycle_deterministic(self):
        """Cycle mode should produce a predictable round-robin sequence."""
        src = ParameterSource(fixed_value=[10, 20, 30], selection="cycle")
        rng = SeededRNG(99)
        draws = [src.draw(rng) for _ in range(5)]
        self.assertEqual(draws, [10.0, 20.0, 30.0, 10.0, 20.0])

    def test_random_selection_deterministic_with_seed(self):
        """Random selection should be deterministic given same seed."""
        def _draw_5(seed):
            src = ParameterSource(fixed_value=[60, 70, 80], selection="random")
            rng = SeededRNG(seed)
            return [src.draw(rng) for _ in range(5)]

        a = _draw_5(42)
        b = _draw_5(42)
        self.assertEqual(a, b)
        # all values from the allowed set
        for v in a:
            self.assertIn(v, [60.0, 70.0, 80.0])

    def test_single_element_list(self):
        src = ParameterSource(fixed_value=[100])
        rng = SeededRNG(1)
        draws = [src.draw(rng) for _ in range(3)]
        self.assertEqual(draws, [100.0, 100.0, 100.0])


class TestFixedModeGenerators(unittest.TestCase):

    def test_generate_buyers_fixed(self):
        fixed = FixedScenarioConfig(
            buyer_value=120.0, buyer_budget=130.0, buyer_patience=5,
        )
        cfg = MarketConfig()
        rng = SeededRNG(42)
        buyers = generate_buyers(rng, 3, 0, cfg, fixed)
        self.assertEqual(len(buyers), 3)
        for b in buyers:
            self.assertEqual(b.value, 120.0)
            self.assertEqual(b.budget, 130.0)
            self.assertEqual(b.patience, 5)

    def test_generate_sellers_fixed(self):
        fixed = FixedScenarioConfig(
            seller_cost=80.0, seller_target_margin=0.15, seller_patience=5,
        )
        cfg = MarketConfig()
        rng = SeededRNG(42)
        sellers = generate_sellers(rng, 3, 0, cfg, fixed)
        self.assertEqual(len(sellers), 3)
        for s in sellers:
            self.assertEqual(s.cost, 80.0)
            self.assertAlmostEqual(s.target_margin, 0.15, places=4)
            self.assertEqual(s.patience, 5)

    def test_generate_buyers_enumerated_cycle(self):
        fixed = FixedScenarioConfig(
            buyer_value=[90, 100, 110], buyer_budget=130.0, buyer_patience=5,
            selection="cycle",
        )
        cfg = MarketConfig()
        rng = SeededRNG(42)
        buyers = generate_buyers(rng, 6, 0, cfg, fixed)
        values = [b.value for b in buyers]
        self.assertEqual(values, [90.0, 100.0, 110.0, 90.0, 100.0, 110.0])

    def test_generate_buyers_none_fixed_uses_distribution(self):
        """When fixed is passed but fields are None, fall back to distribution."""
        fixed = FixedScenarioConfig()  # all None
        cfg = MarketConfig()
        rng = SeededRNG(42)
        buyers = generate_buyers(rng, 10, 0, cfg, fixed)
        values = [b.value for b in buyers]
        self.assertGreater(len(set(values)), 1)
        for v in values:
            self.assertGreaterEqual(v, cfg.buyer_value_min)
            self.assertLessEqual(v, cfg.buyer_value_max)


if __name__ == "__main__":
    unittest.main()
