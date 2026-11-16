from __future__ import annotations

import math
import random
from dataclasses import dataclass, field


def martingale_increment_check(n_paths: int = 4000, n_steps: int = 200, seed: int = 7) -> dict[str, float]:
    """Vérifie numériquement E[X(n+1) - X(n) | F(n)] = 0 pour une marche aléatoire symétrique."""
    rng = random.Random(seed)
    total_inc = 0.0
    total_inc_pos = 0.0
    count_pos = 0
    total_inc_neg = 0.0
    count_neg = 0
    finals: list[float] = []
    for _ in range(n_paths):
        x = 0.0
        for _ in range(n_steps):
            step = 1.0 if rng.random() < 0.5 else -1.0
            if x > 0:
                total_inc_pos += step
                count_pos += 1
            elif x < 0:
                total_inc_neg += step
                count_neg += 1
            total_inc += step
            x += step
        finals.append(x)
    mean_final = sum(finals) / len(finals)
    var_final = sum((f - mean_final) ** 2 for f in finals) / len(finals)
    return {
        "mean_increment": total_inc / (n_paths * n_steps),
        "mean_increment_given_positive": total_inc_pos / count_pos if count_pos else float("nan"),
        "mean_increment_given_negative": total_inc_neg / count_neg if count_neg else float("nan"),
        "mean_final": mean_final,
        "var_final": var_final,
        "expected_var_final": float(n_steps),
    }


@dataclass
class DoublingResult:
    n_paths: int
    n_rounds: int
    start_balance: float
    mean_final: float
    median_final: float
    p_ruin: float
    p_table_limit: float
    p_profit: float
    expected_gain_per_round: float
    details: list[float] = field(default_factory=list)


def doubling_strategy(p_win: float, base_bet: float = 1.0, table_limit: float = 1000.0,
                      start_balance: float = 1000.0, n_rounds: int = 100,
                      n_paths: int = 20000, seed: int = 11) -> DoublingResult:
    """Stratégie dite « martingale »: miser, doubler après chaque perte, revenir à la mise de base après un gain.

    Le jeu paie 1:1 avec probabilité p_win < 0.5 (ex: rouge à la roulette européenne, p = 18/37).
    """
    if not 0.0 < p_win < 1.0:
        raise ValueError("p_win doit être dans ]0, 1[")
    rng = random.Random(seed)
    finals: list[float] = []
    ruins = 0
    limits = 0
    profits = 0
    for _ in range(n_paths):
        balance = start_balance
        bet = base_bet
        for _ in range(n_rounds):
            if bet > table_limit:
                limits += 1
                break
            if bet > balance:
                ruins += 1
                balance = 0.0
                break
            balance -= bet
            if rng.random() < p_win:
                balance += 2.0 * bet
                bet = base_bet
            else:
                bet *= 2.0
        finals.append(balance)
        if balance > start_balance:
            profits += 1
    finals_sorted = sorted(finals)
    mid = len(finals_sorted) // 2
    median = finals_sorted[mid] if len(finals_sorted) % 2 else (finals_sorted[mid - 1] + finals_sorted[mid]) / 2.0
    return DoublingResult(
        n_paths=n_paths,
        n_rounds=n_rounds,
        start_balance=start_balance,
        mean_final=sum(finals) / len(finals),
        median_final=median,
        p_ruin=ruins / n_paths,
        p_table_limit=limits / n_paths,
        p_profit=profits / n_paths,
        expected_gain_per_round=p_win * 1.0 - (1.0 - p_win) * 1.0,
        details=finals,
    )


def combinations(n: int, k: int) -> int:
    return math.comb(n, k)


def loto_grid_probabilities(n_balls: int = 5, max_number: int = 49, extra_max: int = 10) -> dict[tuple[int, int], float]:
    """Probabilités exactes de chaque rang de gain (matches numéros, matches chance)."""
    total_main = combinations(max_number, n_balls)
    probs: dict[tuple[int, int], float] = {}
    for m in range(0, n_balls + 1):
        for c in (0, 1):
            favorable = combinations(n_balls, m) * combinations(max_number - n_balls, n_balls - m)
            p_main = favorable / total_main
            p_extra = (1.0 / extra_max) if c == 1 else (extra_max - 1.0) / extra_max
            probs[(m, c)] = p_main * p_extra
    return probs


def ticket_expected_value(price: float, prizes: dict[tuple[int, int], float],
                          n_balls: int = 5, max_number: int = 49, extra_max: int = 10) -> dict[str, float]:
    """Espérance de gain net d'un billet: somme des (probabilité x gain) moins le prix du billet."""
    probs = loto_grid_probabilities(n_balls, max_number, extra_max)
    gross = sum(probs.get(rank, 0.0) * gain for rank, gain in prizes.items())
    return {
        "price": price,
        "gross_expected_win": gross,
        "net_expected_value": gross - price,
        "total_combinations": combinations(max_number, n_balls) * extra_max,
        "jackpot_probability": probs.get((n_balls, 1), 0.0),
    }
