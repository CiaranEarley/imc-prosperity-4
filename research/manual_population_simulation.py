from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

from manual_trading_decision_model import HIGH, LOW, STEP, TICK_BIDS, best_bid_pair, sequential_profit


N_TEAMS = 4_000
N_RUNS = 50_000
RNG = np.random.default_rng(20260425)


@dataclass(frozen=True)
class TypeSpec:
    name: str
    weight: float
    mean: float
    sigma: float


@dataclass(frozen=True)
class Scenario:
    name: str
    types: tuple[TypeSpec, ...]


AVG_GRID = np.arange(LOW, HIGH, STEP)
OPTIMAL_BY_AVG = {avg: best_bid_pair(float(avg), TICK_BIDS)[2] for avg in AVG_GRID}


SCENARIOS = (
    Scenario(
        "mostly_joint_optimizers",
        (
            TypeSpec("joint_opt", 0.70, 835, 8),
            TypeSpec("single_bid_opt", 0.20, 795, 12),
            TypeSpec("noise", 0.10, 825, 45),
        ),
    ),
    Scenario(
        "mostly_single_bid_thinkers",
        (
            TypeSpec("single_bid_opt", 0.70, 795, 12),
            TypeSpec("joint_opt", 0.20, 835, 8),
            TypeSpec("noise", 0.10, 820, 45),
        ),
    ),
    Scenario(
        "overbid_anchored",
        (
            TypeSpec("joint_opt", 0.35, 835, 10),
            TypeSpec("overbid", 0.45, 870, 18),
            TypeSpec("single_bid_opt", 0.20, 795, 12),
        ),
    ),
    Scenario(
        "confused_broad",
        (
            TypeSpec("low", 0.20, 760, 30),
            TypeSpec("single_bid_opt", 0.30, 795, 15),
            TypeSpec("joint_opt", 0.30, 835, 10),
            TypeSpec("high", 0.20, 875, 25),
        ),
    ),
    Scenario(
        "bad_low_population",
        (
            TypeSpec("low", 0.65, 760, 20),
            TypeSpec("single_bid_opt", 0.25, 795, 12),
            TypeSpec("joint_opt", 0.10, 835, 10),
        ),
    ),
    Scenario(
        "bad_high_population",
        (
            TypeSpec("joint_opt", 0.30, 835, 10),
            TypeSpec("high", 0.50, 885, 20),
            TypeSpec("max_anchor", 0.20, 910, 8),
        ),
    ),
)


def round_to_tick(values: np.ndarray) -> np.ndarray:
    rounded = np.rint(values / STEP) * STEP
    return np.clip(rounded, LOW, HIGH - STEP)


def simulate_population_average(scenario: Scenario) -> np.ndarray:
    weights = np.array([t.weight for t in scenario.types], dtype=float)
    weights = weights / weights.sum()
    counts = RNG.multinomial(N_TEAMS, weights, size=N_RUNS)

    sums = np.zeros(N_RUNS)
    for idx, spec in enumerate(scenario.types):
        count = counts[:, idx]
        # Sum of normals per type is normal with n*mean and sqrt(n)*sigma.
        type_sum = RNG.normal(count * spec.mean, np.sqrt(count) * spec.sigma)
        sums += type_sum

    return round_to_tick(sums / N_TEAMS)


def cvar_left(values: np.ndarray, pct: float = 0.05) -> float:
    threshold = np.quantile(values, pct)
    return float(values[values <= threshold].mean())


def evaluate_candidates(averages: np.ndarray, candidates: list[tuple[int, int]]) -> list[dict[str, float]]:
    optimal = np.array([OPTIMAL_BY_AVG[int(avg)] for avg in averages])
    rows = []
    for first_bid, second_bid in candidates:
        profit = np.array(
            [sequential_profit(first_bid, second_bid, float(avg)) for avg in averages]
        )
        regret = optimal - profit
        rows.append(
            {
                "first_bid": first_bid,
                "second_bid": second_bid,
                "mean_profit": float(profit.mean()),
                "p05_profit": float(np.quantile(profit, 0.05)),
                "cvar05_profit": cvar_left(profit),
                "mean_regret": float(regret.mean()),
                "p95_regret": float(np.quantile(regret, 0.95)),
                "worst_regret": float(regret.max()),
            }
        )
    return sorted(rows, key=lambda x: (x["mean_regret"], -x["cvar05_profit"]))


def print_scenario_summary() -> None:
    candidates = [
        (745, 825),
        (750, 830),
        (750, 835),
        (750, 840),
        (755, 840),
        (760, 850),
        (775, 880),
        (795, 795),
        (795, 835),
    ]

    aggregate_scores: dict[tuple[int, int], list[float]] = {candidate: [] for candidate in candidates}
    print("Scenario summaries use 4,000 teams and 50,000 Monte Carlo populations.")
    print()

    for scenario in SCENARIOS:
        averages = simulate_population_average(scenario)
        print(
            f"{scenario.name}: avg mean={averages.mean():.1f}, "
            f"p05={np.quantile(averages, 0.05):.0f}, "
            f"p95={np.quantile(averages, 0.95):.0f}"
        )
        all_rows = evaluate_candidates(averages, candidates)
        for row in all_rows:
            pair = (int(row["first_bid"]), int(row["second_bid"]))
            aggregate_scores[pair].append(row["mean_regret"])
        for row in all_rows[:5]:
            pair = (int(row["first_bid"]), int(row["second_bid"]))
            print(
                f"  {pair}: mean={row['mean_profit']:.1f}, "
                f"cvar05={row['cvar05_profit']:.1f}, "
                f"mean_regret={row['mean_regret']:.1f}, "
                f"p95_regret={row['p95_regret']:.1f}"
            )
        print()

    print("Cross-scenario average mean regret:")
    for pair, regrets in sorted(
        aggregate_scores.items(),
        key=lambda item: math.inf if not item[1] else sum(item[1]) / len(item[1]),
    ):
        if not regrets:
            continue
        print(f"  {pair}: {sum(regrets) / len(regrets):.1f}")


if __name__ == "__main__":
    print_scenario_summary()
