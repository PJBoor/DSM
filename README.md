# DSM — Analyse statistique de tirages de loto et martingales

Outil d'analyse statistique de tirages de loto (grille 5 numéros parmi 49 + numéro Chance, format CSV `date;n1;n2;n3;n4;n5;chance`) accompagné de simulations de martingales.

**Avertissement important :** les tirages de loto sont des événements aléatoires indépendants et uniformes. Aucun outil statistique — martingale ou autre — ne peut prédire les numéros gagnants d'un tirage futur. Ce projet ne produit **aucune prédiction de numéros gagnants** ; il analyse les tirages passés et démontre mathématiquement pourquoi aucune stratégie ne bat le loto. Jouez de façon responsable (18+ uniquement) : ne misez jamais plus que ce que vous pouvez perdre. En France, le service [Joueurs Info Service](https://www.joueurs-info-service.fr) (09 74 75 13 13, appel non surtaxé) peut aider en cas de difficulté avec le jeu.

## Pourquoi aucune prédiction n'est possible

- Chaque numéro a à chaque tirage la même probabilité `1/49` (et `1/10` pour la Chance), indépendamment des tirages précédents : P(numéro n au tirage t+1 | historique) = 1/49.
- Une **martingale** (au sens probabiliste) est un processus tel que E[X(n+1) | F(n)] = X(n) : la meilleure prédiction du prochain état connaissant le passé est l'état présent. C'est une propriété d'équité, **pas une méthode de prédiction**. Appliquée aux tirages de loto, elle dit simplement que l'espérance conditionnelle d'un tirage futur ne dépend pas du passé.
- La « stratégie martingale » de mise (doubler sa mise après chaque perte) ne change pas l'espérance du jeu : si p est la probabilité de gain d'une partie et le gain payé 1:1, l'espérance par partie est `2p − 1`, négative dès que `p < 0.5` (roulette européenne : p = 18/37). Les limites de table et le capital fini rendent en plus la ruine certaine à long terme.

## Installation et usage

Python ≥ 3.10, aucune dépendance externe (bibliothèque standard uniquement).

```bash
python3 -m dsm.cli sample --out data/sample_draws.csv --n 520 --seed 42   # CSV de tirages synthétiques
python3 -m dsm.cli analyze data/sample_draws.csv                            # analyse statistique
python3 -m dsm.cli martingale --paths 20000 --rounds 100                    # propriété de martingale + doublage
python3 -m dsm.cli ev --jackpot 15000000 --price 2.2                        # espérance d'un billet
python3 -m unittest discover -s tests                                       # tests
```

Pour analyser de vrais tirages, remplacez `data/sample_draws.csv` par votre propre CSV au format `date;n1;n2;n3;n4;n5;chance` (options `--balls`, `--max`, `--extra-max` pour d'autres grilles).

## Ce que fait chaque commande

- `analyze` : fréquences par numéro, test du chi² d'uniformité, écarts depuis la dernière apparition, loi de la somme des numéros (moyenne/variance théoriques d'un échantillon sans remise), autocorrélation lag-1 et test des runs. Verdict : les données sont-elles compatibles avec des tirages uniformes indépendants ?
- `martingale` : vérification numérique que E[X(n+1) − X(n) | F(n)] ≈ 0 pour une marche aléatoire symétrique, puis simulation de la stratégie de doublage (solde moyen, médian, P(ruine), P(limite de table), P(profit)). Résultat typique : forte probabilité de petit profit, mais solde moyen inférieur au capital initial et espérance négative.
- `ev` : espérance nette d'un billet = Σ probabilité(rang) × gain(rang) − prix. Pour un jackpot de 15 M€ et un billet à 2,20 €, l'espérance nette vaut environ −1,41 € (jackpot 1 sur 19 068 840 = C(49,5) × 10).

## Structure

```
dsm/
  draws.py       chargement/validation de CSV de tirages, génération de données synthétiques
dsm/
  stats.py       chi², fréquences, écarts, moments de la somme, autocorrélation, test des runs
dsm/
  martingale.py  propriété de martingale, stratégie de doublage, probabilités de la grille, espérance du billet
dsm/
  cli.py         interface en ligne de commande
tests/
  test_dsm.py    tests unitaires (python3 -m unittest discover -s tests)
data/
  sample_draws.csv  520 tirages synthétiques (seed=42)
```
