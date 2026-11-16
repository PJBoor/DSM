from __future__ import annotations

import math
from collections import Counter
from dataclasses import dataclass

from .draws import Draw


def _gammln(xx: float) -> float:
    cof = [76.18009172947146, -86.50532032941677, 24.01409824083091,
           -1.231739572450155, 0.1208650973866179e-2, -0.5395239384953e-5]
    y = xx
    tmp = xx + 5.5
    tmp -= (xx + 0.5) * math.log(tmp)
    ser = 1.000000000190015
    for c in cof:
        y += 1.0
        ser += c / y
    return -tmp + math.log(2.5066282746310005 * ser / xx)


def _gser(a: float, x: float) -> float:
    ap = a
    total = 1.0 / a
    delta = total
    for _ in range(500):
        ap += 1.0
        delta *= x / ap
        total += delta
        if abs(delta) < abs(total) * 1e-15:
            break
    return total * math.exp(-x + a * math.log(x) - _gammln(a))


def _gcf(a: float, x: float) -> float:
    b = x + 1.0 - a
    c = 1e30
    d = 1.0 / b
    h = d
    for i in range(1, 500):
        an = -i * (i - a)
        b += 2.0
        d = an * d + b
        if abs(d) < 1e-30:
            d = 1e-30
        c = b + an / c
        if abs(c) < 1e-30:
            c = 1e-30
        d = 1.0 / d
        delta = d * c
        h *= delta
        if abs(delta - 1.0) < 1e-15:
            break
    return math.exp(-x + a * math.log(x) - _gammln(a)) * h


def chi2_sf(x: float, dof: int) -> float:
    """Fonction de survie de la loi du chi2: P(X >= x) pour dof degrés de liberté."""
    if dof <= 0:
        raise ValueError("dof doit être positif")
    if x <= 0:
        return 1.0
    a = dof / 2.0
    xx = x / 2.0
    if xx < a + 1.0:
        return max(0.0, min(1.0, 1.0 - _gser(a, xx)))
    return max(0.0, min(1.0, _gcf(a, xx)))


def number_frequencies(draws: list[Draw], max_number: int, include_extra: bool = False) -> dict[int, int]:
    counts = Counter()
    for d in draws:
        for n in d.numbers:
            counts[n] += 1
        if include_extra and d.extra is not None:
            counts[d.extra] += 1
    return {n: counts.get(n, 0) for n in range(1, max_number + 1)}


def chi2_uniformity(freqs: dict[int, int]) -> tuple[float, int, float]:
    total = sum(freqs.values())
    k = len(freqs)
    if total == 0 or k < 2:
        raise ValueError("fréquences insuffisantes")
    expected = total / k
    chi2 = sum((o - expected) ** 2 / expected for o in freqs.values())
    dof = k - 1
    return chi2, dof, chi2_sf(chi2, dof)


def gap_analysis(draws: list[Draw], max_number: int) -> dict[int, int]:
    last_seen: dict[int, int] = {}
    for i, d in enumerate(draws):
        for n in d.numbers:
            last_seen[n] = i
    n = len(draws)
    return {num: (n - 1 - last_seen[num]) if num in last_seen else n for num in range(1, max_number + 1)}


def theoretical_sum_moments(n_balls: int, max_number: int) -> tuple[float, float]:
    mean = n_balls * (max_number + 1) / 2.0
    var = n_balls * (max_number - n_balls) / (max_number - 1) * (max_number * max_number - 1) / 12.0
    return mean, var


def sum_distribution(draws: list[Draw], n_balls: int, max_number: int) -> dict[str, float]:
    sums = [sum(d.numbers) for d in draws]
    n = len(sums)
    obs_mean = sum(sums) / n
    theo_mean, theo_var = theoretical_sum_moments(n_balls, max_number)
    z = (obs_mean - theo_mean) / math.sqrt(theo_var / n) if n > 0 else float("nan")
    return {
        "n": float(n),
        "obs_mean": obs_mean,
        "theo_mean": theo_mean,
        "obs_var": (sum((s - obs_mean) ** 2 for s in sums) / n) if n else float("nan"),
        "theo_var": theo_var,
        "z": z,
        "p_two_sided": chi2_sf(z * z, 1),
    }


def autocorr_lag1(series: list[float]) -> float:
    n = len(series)
    if n < 3:
        return float("nan")
    mean = sum(series) / n
    denom = sum((x - mean) ** 2 for x in series)
    if denom == 0:
        return float("nan")
    num = sum((series[i] - mean) * (series[i + 1] - mean) for i in range(n - 1))
    return num / denom


def runs_test(binary: list[bool]) -> dict[str, float]:
    n = len(binary)
    n1 = sum(1 for b in binary if b)
    n2 = n - n1
    if n1 == 0 or n2 == 0:
        return {"runs": 0.0, "z": float("nan"), "p_two_sided": float("nan")}
    runs = 1 + sum(1 for i in range(1, n) if binary[i] != binary[i - 1])
    mu = 2.0 * n1 * n2 / n + 1.0
    var = 2.0 * n1 * n2 * (2.0 * n1 * n2 - n) / (n * n * (n - 1))
    z = (runs - mu) / math.sqrt(var)
    return {"runs": float(runs), "expected_runs": mu, "z": z, "p_two_sided": chi2_sf(z * z, 1)}


@dataclass
class AnalysisReport:
    n_draws: int
    n_balls: int
    max_number: int
    chi2: float
    dof: int
    chi2_p: float
    min_freq: int
    max_freq: int
    max_gap: int
    mean_gap: float
    sum_stats: dict[str, float]
    autocorr_sums: float
    runs: dict[str, float]

    def is_consistent_with_random(self, alpha: float = 0.01) -> bool:
        return self.chi2_p >= alpha and self.sum_stats["p_two_sided"] >= alpha and self.runs["p_two_sided"] >= alpha


def analyze(draws: list[Draw], n_balls: int = 5, max_number: int = 49) -> AnalysisReport:
    freqs = number_frequencies(draws, max_number)
    chi2, dof, p = chi2_uniformity(freqs)
    gaps = gap_analysis(draws, max_number)
    sums = [sum(d.numbers) for d in draws]
    theo_mean, _ = theoretical_sum_moments(n_balls, max_number)
    binary = [s > theo_mean for s in sums]
    return AnalysisReport(
        n_draws=len(draws),
        n_balls=n_balls,
        max_number=max_number,
        chi2=chi2,
        dof=dof,
        chi2_p=p,
        min_freq=min(freqs.values()),
        max_freq=max(freqs.values()),
        max_gap=max(gaps.values()),
        mean_gap=sum(gaps.values()) / len(gaps),
        sum_stats=sum_distribution(draws, n_balls, max_number),
        autocorr_sums=autocorr_lag1(sums),
        runs=runs_test(binary),
    )
