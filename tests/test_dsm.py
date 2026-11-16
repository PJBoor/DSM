import math
import os
import tempfile
import unittest

from dsm.draws import Draw, generate_sample, load_draws
from dsm.martingale import (combinations, doubling_strategy, loto_grid_probabilities,
                            martingale_increment_check, ticket_expected_value)
from dsm.stats import (analyze, autocorr_lag1, chi2_sf, chi2_uniformity, gap_analysis,
                       number_frequencies, runs_test, theoretical_sum_moments)


class TestChi2(unittest.TestCase):
    def test_known_quantiles(self):
        self.assertAlmostEqual(chi2_sf(3.841458820694124, 1), 0.05, places=6)
        self.assertAlmostEqual(chi2_sf(6.634896601021213, 1), 0.01, places=6)
        self.assertEqual(chi2_sf(0.0, 5), 1.0)

    def test_uniform_frequencies_give_high_p(self):
        freqs = {i: 100 for i in range(1, 50)}
        chi2, dof, p = chi2_uniformity(freqs)
        self.assertAlmostEqual(chi2, 0.0)
        self.assertEqual(dof, 48)
        self.assertAlmostEqual(p, 1.0)

    def test_biased_frequencies_give_low_p(self):
        freqs = {i: (1000 if i == 1 else 50) for i in range(1, 50)}
        _, _, p = chi2_uniformity(freqs)
        self.assertLess(p, 1e-10)


class TestDraws(unittest.TestCase):
    def test_roundtrip_and_order(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "draws.csv")
            generate_sample(path, n_draws=50, seed=1)
            draws = load_draws(path)
            self.assertEqual(len(draws), 50)
            self.assertEqual(draws, sorted(draws, key=lambda d: d.date))
            for d in draws:
                self.assertEqual(len(d.numbers), 5)
                self.assertEqual(len(set(d.numbers)), 5)
                self.assertTrue(all(1 <= n <= 49 for n in d.numbers))
                self.assertTrue(1 <= d.extra <= 10)

    def test_deterministic_seed(self):
        with tempfile.TemporaryDirectory() as tmp:
            p1 = os.path.join(tmp, "a.csv")
            p2 = os.path.join(tmp, "b.csv")
            generate_sample(p1, n_draws=20, seed=99)
            generate_sample(p2, n_draws=20, seed=99)
            self.assertEqual(load_draws(p1), load_draws(p2))

    def test_validation_rejects_bad_rows(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "bad.csv")
            with open(path, "w", encoding="utf-8") as fh:
                fh.write("date;n1;n2;n3;n4;n5;chance\n")
                fh.write("2024-01-01;1;2;3;4;50;5\n")
            with self.assertRaises(ValueError):
                load_draws(path)
            with open(path, "w", encoding="utf-8") as fh:
                fh.write("date;n1;n2;n3;n4;n5;chance\n")
                fh.write("2024-01-01;1;2;3;4;4;5\n")
            with self.assertRaises(ValueError):
                load_draws(path)


class TestStats(unittest.TestCase):
    def setUp(self):
        self.draws = [
            Draw("2024-01-01", (1, 2, 3, 4, 5), 1),
            Draw("2024-01-08", (6, 7, 8, 9, 10), 2),
            Draw("2024-01-15", (1, 6, 11, 16, 21), 3),
        ]

    def test_frequencies(self):
        freqs = number_frequencies(self.draws, 49)
        self.assertEqual(freqs[1], 2)
        self.assertEqual(freqs[49], 0)
        self.assertEqual(sum(freqs.values()), 15)

    def test_gaps(self):
        gaps = gap_analysis(self.draws, 49)
        self.assertEqual(gaps[1], 0)
        self.assertEqual(gaps[6], 0)
        self.assertEqual(gaps[2], 2)
        self.assertEqual(gaps[49], 3)

    def test_sum_moments(self):
        mean, var = theoretical_sum_moments(5, 49)
        self.assertAlmostEqual(mean, 125.0)
        self.assertGreater(var, 0)

    def test_autocorr_constant_series(self):
        self.assertTrue(math.isnan(autocorr_lag1([1.0, 1.0, 1.0])))

    def test_runs_test(self):
        res = runs_test([True, False, True, False, True, False])
        self.assertEqual(res["runs"], 6.0)
        self.assertLess(abs(res["z"]), 5.0)

    def test_analyze_synthetic_consistent(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "s.csv")
            draws = generate_sample(path, n_draws=1000, seed=3)
            report = analyze(load_draws(path), n_balls=5, max_number=49)
            self.assertEqual(report.n_draws, 1000)
            self.assertTrue(report.is_consistent_with_random())


class TestMartingale(unittest.TestCase):
    def test_increment_check_zero(self):
        check = martingale_increment_check(n_paths=2000, n_steps=100, seed=5)
        self.assertAlmostEqual(check["mean_increment"], 0.0, delta=0.05)
        self.assertAlmostEqual(check["mean_increment_given_positive"], 0.0, delta=0.15)
        self.assertAlmostEqual(check["mean_increment_given_negative"], 0.0, delta=0.15)
        self.assertAlmostEqual(check["var_final"], check["expected_var_final"], delta=check["expected_var_final"] * 0.2)

    def test_doubling_has_negative_expectation(self):
        res = doubling_strategy(p_win=18 / 37, base_bet=1.0, table_limit=1023.0,
                                start_balance=1e9, n_rounds=50, n_paths=5000, seed=2)
        self.assertLess(res.expected_gain_per_round, 0.0)
        self.assertLess(res.mean_final, res.start_balance)

    def test_doubling_fair_game_is_breakeven(self):
        res = doubling_strategy(p_win=0.5, base_bet=1.0, table_limit=1e9,
                                start_balance=1e9, n_rounds=20, n_paths=3000, seed=4)
        self.assertAlmostEqual(res.expected_gain_per_round, 0.0, places=12)
        self.assertAlmostEqual(res.mean_final, res.start_balance, delta=res.start_balance * 0.02)

    def test_table_limit_and_ruin_occur(self):
        res = doubling_strategy(p_win=18 / 37, base_bet=1.0, table_limit=255.0,
                                start_balance=500.0, n_rounds=200, n_paths=5000, seed=8)
        self.assertGreater(res.p_ruin + res.p_table_limit, 0.0)
        self.assertGreater(res.p_table_limit, 0.0)
        self.assertLess(res.mean_final, res.start_balance)
        self.assertGreater(res.p_profit, 0.0)

    def test_grid_probabilities_sum_to_one(self):
        probs = loto_grid_probabilities(5, 49, 10)
        self.assertAlmostEqual(sum(probs.values()), 1.0, places=12)
        self.assertAlmostEqual(probs[(5, 1)], 1.0 / (math.comb(49, 5) * 10), places=15)

    def test_ev(self):
        total = combinations(49, 5) * 10
        ev = ticket_expected_value(price=2.2, prizes={(5, 1): float(total * 2.2)})
        self.assertAlmostEqual(ev["net_expected_value"], 0.0, places=9)
        ev2 = ticket_expected_value(price=2.2, prizes={(5, 1): 15_000_000.0})
        self.assertAlmostEqual(ev2["jackpot_probability"], 1.0 / total, places=15)
        self.assertLess(ev2["net_expected_value"], 0.0)


if __name__ == "__main__":
    unittest.main()
