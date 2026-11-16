from __future__ import annotations

import argparse
import sys

from .draws import generate_sample, load_draws
from .martingale import doubling_strategy, martingale_increment_check, ticket_expected_value
from .stats import analyze


def _cmd_sample(args: argparse.Namespace) -> int:
    draws = generate_sample(args.out, n_draws=args.n, n_balls=args.balls, max_number=args.max,
                            extra_max=args.extra_max, seed=args.seed)
    print(f"{len(draws)} tirages synthétiques écrits dans {args.out} (seed={args.seed})")
    print("Données synthétiques générées pour tester le pipeline, pas des vrais tirages.")
    return 0


def _cmd_analyze(args: argparse.Namespace) -> int:
    draws = load_draws(args.path, n_balls=args.balls, max_number=args.max, extra_max=args.extra_max)
    report = analyze(draws, n_balls=args.balls, max_number=args.max)
    print(f"Tirages analysés: {report.n_draws} (grille {report.n_balls} numéros parmi {report.max_number})")
    print(f"Fréquences observées: min={report.min_freq}, max={report.max_freq}")
    print(f"Chi2 d'uniformité: chi2={report.chi2:.2f}, dof={report.dof}, p={report.chi2_p:.4f}")
    print(f"Écart (en tirages) depuis la dernière apparition: max={report.max_gap}, moyen={report.mean_gap:.2f}")
    s = report.sum_stats
    print(f"Somme des numéros: moyenne observée={s['obs_mean']:.2f} (théorique {s['theo_mean']:.2f}), z={s['z']:.3f}, p={s['p_two_sided']:.4f}")
    print(f"Autocorrélation lag-1 des sommes: {report.autocorr_sums:.4f}")
    print(f"Test des runs: z={report.runs['z']:.3f}, p={report.runs['p_two_sided']:.4f}")
    verdict = report.is_consistent_with_random()
    print(f"Verdict: données {'COMPATIBLES' if verdict else 'NON compatibles'} avec des tirages uniformes indépendants (alpha=0.01).")
    print("Conséquence: les numéros passés n'apportent aucune information sur les tirages futurs.")
    print("Aucune prédiction de numéros gagnants n'est produite par cet outil.")
    return 0


def _cmd_martingale(args: argparse.Namespace) -> int:
    check = martingale_increment_check()
    print("Propriété de martingale d'une marche aléatoire symétrique (E[X(n+1)-X(n) | F(n)] = 0):")
    print(f"  incrément moyen global: {check['mean_increment']:.5f}")
    print(f"  incrément moyen sachant X(n) > 0: {check['mean_increment_given_positive']:.5f}")
    print(f"  incrément moyen sachant X(n) < 0: {check['mean_increment_given_negative']:.5f}")
    print(f"  variance finale observée: {check['var_final']:.1f} (attendue: {check['expected_var_final']:.0f})")
    res = doubling_strategy(p_win=args.p_win, base_bet=args.base, table_limit=args.limit,
                            start_balance=args.balance, n_rounds=args.rounds,
                            n_paths=args.paths, seed=args.seed)
    print(f"\nStratégie de doublage (p_gain={args.p_win:.4f}, mise de base={args.base}, "
          f"limite de table={args.limit}, capital={args.balance}, {args.rounds} parties x {args.paths} simulations):")
    print(f"  espérance de gain par partie: {res.expected_gain_per_round:+.4f} (négative si p_gain < 0.5)")
    print(f"  solde final moyen: {res.mean_final:.2f} (capital initial: {res.start_balance:.2f})")
    print(f"  solde final médian: {res.median_final:.2f}")
    print(f"  P(ruine): {res.p_ruin:.3%}, P(limite de table atteinte): {res.p_table_limit:.3%}, P(profit): {res.p_profit:.3%}")
    print("Conclusion: doubler après une perte ne change pas l'espérance négative du jeu; la martingale de mise ne bat pas le loto.")
    return 0


def _cmd_ev(args: argparse.Namespace) -> int:
    prizes = {(args.balls, 1): args.jackpot}
    ev = ticket_expected_value(price=args.price, prizes=prizes, n_balls=args.balls,
                               max_number=args.max, extra_max=args.extra_max)
    print(f"Combinaisons possibles: {ev['total_combinations']:,}")
    print(f"Probabilité du jackpot (5+chance): 1 sur {1 / ev['jackpot_probability']:,.0f}")
    print(f"Prix du billet: {ev['price']:.2f} EUR")
    print(f"Espérance de gain brut (jackpot seul): {ev['gross_expected_win']:.4f} EUR")
    print(f"Espérance nette du billet: {ev['net_expected_value']:+.4f} EUR")
    print("À chaque tirage, un billet perd en moyenne la valeur de l'espérance nette; aucun système de mise ne change ce constat.")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="dsm", description="Analyse statistique de tirages de loto et martingales")
    sub = parser.add_subparsers(dest="command", required=True)

    p_sample = sub.add_parser("sample", help="génère un CSV de tirages synthétiques")
    p_sample.add_argument("--out", default="data/sample_draws.csv")
    p_sample.add_argument("--n", type=int, default=520)
    p_sample.add_argument("--balls", type=int, default=5)
    p_sample.add_argument("--max", type=int, default=49)
    p_sample.add_argument("--extra-max", type=int, default=10)
    p_sample.add_argument("--seed", type=int, default=42)
    p_sample.set_defaults(func=_cmd_sample)

    p_an = sub.add_parser("analyze", help="analyse statistique d'un CSV de tirages")
    p_an.add_argument("path")
    p_an.add_argument("--balls", type=int, default=5)
    p_an.add_argument("--max", type=int, default=49)
    p_an.add_argument("--extra-max", type=int, default=10)
    p_an.set_defaults(func=_cmd_analyze)

    p_mart = sub.add_parser("martingale", help="vérifie la propriété de martingale et simule la stratégie de doublage")
    p_mart.add_argument("--p-win", type=float, default=18 / 37)
    p_mart.add_argument("--base", type=float, default=1.0)
    p_mart.add_argument("--limit", type=float, default=1000.0)
    p_mart.add_argument("--balance", type=float, default=1000.0)
    p_mart.add_argument("--rounds", type=int, default=100)
    p_mart.add_argument("--paths", type=int, default=20000)
    p_mart.add_argument("--seed", type=int, default=11)
    p_mart.set_defaults(func=_cmd_martingale)

    p_ev = sub.add_parser("ev", help="espérance de gain d'un billet de loto")
    p_ev.add_argument("--jackpot", type=float, default=15_000_000.0)
    p_ev.add_argument("--price", type=float, default=2.2)
    p_ev.add_argument("--balls", type=int, default=5)
    p_ev.add_argument("--max", type=int, default=49)
    p_ev.add_argument("--extra-max", type=int, default=10)
    p_ev.set_defaults(func=_cmd_ev)

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
