from __future__ import annotations

import csv
import random
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Draw:
    date: str
    numbers: tuple[int, ...]
    extra: int | None = None


def _validate(date: str, nums: list[int], extra: int | None, max_number: int, extra_max: int | None) -> None:
    if not date:
        raise ValueError("date vide")
    if len(nums) == 0:
        raise ValueError(f"tirage du {date} sans numéros")
    if len(set(nums)) != len(nums):
        raise ValueError(f"tirage du {date} avec des numéros en double: {nums}")
    for n in nums:
        if not 1 <= n <= max_number:
            raise ValueError(f"tirage du {date}: numéro {n} hors de 1..{max_number}")
    if extra_max is not None:
        if extra is None:
            raise ValueError(f"tirage du {date}: numéro chance manquant")
        if not 1 <= extra <= extra_max:
            raise ValueError(f"tirage du {date}: chance {extra} hors de 1..{extra_max}")


def load_draws(path: str | Path, n_balls: int = 5, max_number: int = 49, extra_max: int | None = 10) -> list[Draw]:
    draws: list[Draw] = []
    with open(path, newline="", encoding="utf-8") as fh:
        sample = fh.read(4096)
        fh.seek(0)
        try:
            dialect = csv.Sniffer().sniff(sample, delimiters=";,\t")
        except csv.Error:
            dialect = csv.excel
        reader = csv.reader(fh, dialect)
        for row in reader:
            cells = [c.strip() for c in row if c.strip() != ""]
            if not cells or cells[0].startswith("#"):
                continue
            if cells[0].lower() in {"date", "jour"}:
                continue
            date = cells[0]
            try:
                nums = sorted(int(c) for c in cells[1 : 1 + n_balls])
                extra = int(cells[1 + n_balls]) if extra_max is not None and len(cells) > 1 + n_balls else None
            except (ValueError, IndexError) as exc:
                raise ValueError(f"ligne illisible pour le tirage du {date}: {row}") from exc
            _validate(date, nums, extra, max_number, extra_max)
            draws.append(Draw(date, tuple(nums), extra))
    if not draws:
        raise ValueError(f"aucun tirage trouvé dans {path}")
    draws.sort(key=lambda d: d.date)
    return draws


def generate_sample(path: str | Path, n_draws: int = 520, n_balls: int = 5, max_number: int = 49,
                    extra_max: int | None = 10, seed: int = 42, start_date: str = "2015-01-07") -> list[Draw]:
    rng = random.Random(seed)
    year, month, day = (int(p) for p in start_date.split("-"))
    from datetime import date, timedelta

    d = date(year, month, day)
    draws: list[Draw] = []
    for _ in range(n_draws):
        nums = tuple(sorted(rng.sample(range(1, max_number + 1), n_balls)))
        extra = rng.randint(1, extra_max) if extra_max is not None else None
        draws.append(Draw(d.isoformat(), nums, extra))
        d += timedelta(days=7)
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    header = ["date"] + [f"n{i + 1}" for i in range(n_balls)] + (["chance"] if extra_max is not None else [])
    with open(path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh, delimiter=";")
        writer.writerow(header)
        for dr in draws:
            row = [dr.date, *dr.numbers] + ([dr.extra] if dr.extra is not None else [])
            writer.writerow(row)
    return draws
