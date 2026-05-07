from __future__ import annotations

import argparse
import csv
import json
import math
import statistics
import uuid
from collections import Counter, defaultdict
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple


ROOT = Path(__file__).resolve().parent
DEFAULT_DATA_DIR = ROOT / "Price & Trade Data"
DEFAULT_REPORT_DIR = ROOT / "Reports"
PRODUCT = "HYDROGEL_PACK"
DAY_STRIDE = 1_000_000


def parse_float(value: str) -> Optional[float]:
    if value is None or value == "":
        return None
    return float(value)


def percentile(values: List[float], pct: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    rank = (len(ordered) - 1) * pct
    low = math.floor(rank)
    high = math.ceil(rank)
    if low == high:
        return ordered[low]
    weight = rank - low
    return ordered[low] * (1.0 - weight) + ordered[high] * weight


def corr(xs: List[float], ys: List[float]) -> float:
    if len(xs) < 3 or len(xs) != len(ys):
        return 0.0
    mx = statistics.mean(xs)
    my = statistics.mean(ys)
    vx = sum((x - mx) ** 2 for x in xs)
    vy = sum((y - my) ** 2 for y in ys)
    if vx <= 1e-12 or vy <= 1e-12:
        return 0.0
    return sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / math.sqrt(vx * vy)


def mean(values: Iterable[float]) -> float:
    data = list(values)
    return statistics.mean(data) if data else 0.0


def summarize_values(values: List[float]) -> Dict[str, float]:
    if not values:
        return {}
    return {
        "n": len(values),
        "mean": statistics.mean(values),
        "stdev": statistics.pstdev(values) if len(values) > 1 else 0.0,
        "min": min(values),
        "p01": percentile(values, 0.01),
        "p05": percentile(values, 0.05),
        "p10": percentile(values, 0.10),
        "p25": percentile(values, 0.25),
        "median": percentile(values, 0.50),
        "p75": percentile(values, 0.75),
        "p90": percentile(values, 0.90),
        "p95": percentile(values, 0.95),
        "p99": percentile(values, 0.99),
        "max": max(values),
    }


def price_levels(row: Dict[str, str]) -> Tuple[List[Tuple[float, float]], List[Tuple[float, float]]]:
    bids: List[Tuple[float, float]] = []
    asks: List[Tuple[float, float]] = []
    for level in (1, 2, 3):
        bid_price = parse_float(row.get(f"bid_price_{level}", ""))
        bid_volume = parse_float(row.get(f"bid_volume_{level}", ""))
        ask_price = parse_float(row.get(f"ask_price_{level}", ""))
        ask_volume = parse_float(row.get(f"ask_volume_{level}", ""))
        if bid_price is not None and bid_volume is not None:
            bids.append((bid_price, bid_volume))
        if ask_price is not None and ask_volume is not None:
            asks.append((ask_price, ask_volume))
    return bids, asks


def row_features(row: Dict[str, str]) -> Optional[Dict[str, float]]:
    bids, asks = price_levels(row)
    if not bids or not asks:
        return None
    best_bid = bids[0][0]
    best_ask = asks[0][0]
    top_mid = float(row["mid_price"])
    wall_mid = (min(price for price, _ in bids) + max(price for price, _ in asks)) / 2.0
    bid_volume = sum(volume for _, volume in bids)
    ask_volume = sum(volume for _, volume in asks)
    top_imbalance = 0.0
    if bids[0][1] + asks[0][1] > 0:
        top_imbalance = (bids[0][1] - asks[0][1]) / (bids[0][1] + asks[0][1])
    book_imbalance = 0.0
    if bid_volume + ask_volume > 0:
        book_imbalance = (bid_volume - ask_volume) / (bid_volume + ask_volume)
    return {
        "day": float(row["day"]),
        "timestamp": float(row["timestamp"]),
        "top_mid": top_mid,
        "wall_mid": wall_mid,
        "mid_minus_wall": top_mid - wall_mid,
        "top_spread": best_ask - best_bid,
        "wall_spread": max(price for price, _ in asks) - min(price for price, _ in bids),
        "bid_volume": bid_volume,
        "ask_volume": ask_volume,
        "top_imbalance": top_imbalance,
        "book_imbalance": book_imbalance,
        "best_bid": best_bid,
        "best_ask": best_ask,
    }


def load_price_series(data_dir: Path) -> Dict[int, List[Dict[str, float]]]:
    by_day: Dict[int, List[Dict[str, float]]] = defaultdict(list)
    for path in sorted(data_dir.glob("prices_round_*_day_*.csv")):
        with path.open("r", newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f, delimiter=";")
            for row in reader:
                if row["product"] != PRODUCT:
                    continue
                features = row_features(row)
                if features is None:
                    continue
                by_day[int(features["day"])].append(features)
    for rows in by_day.values():
        rows.sort(key=lambda item: item["timestamp"])
    return dict(by_day)


def load_all_product_walls(data_dir: Path) -> Dict[str, Dict[int, List[float]]]:
    values: Dict[str, Dict[int, List[Tuple[int, float]]]] = defaultdict(lambda: defaultdict(list))
    for path in sorted(data_dir.glob("prices_round_*_day_*.csv")):
        with path.open("r", newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f, delimiter=";")
            for row in reader:
                features = row_features(row)
                if features is None:
                    continue
                values[row["product"]][int(row["day"])].append((int(row["timestamp"]), features["wall_mid"]))
    out: Dict[str, Dict[int, List[float]]] = {}
    for product, by_day in values.items():
        out[product] = {}
        for day, rows in by_day.items():
            out[product][day] = [value for _, value in sorted(rows)]
    return out


def load_trades(data_dir: Path, price_by_day: Dict[int, List[Dict[str, float]]]) -> List[Dict[str, float]]:
    price_lookup: Dict[Tuple[int, int], Dict[str, float]] = {}
    for day, rows in price_by_day.items():
        for row in rows:
            price_lookup[(day, int(row["timestamp"]))] = row

    trades: List[Dict[str, float]] = []
    for path in sorted(data_dir.glob("trades_round_*_day_*.csv")):
        day_text = path.stem.rsplit("_day_", 1)[-1]
        day = int(day_text)
        with path.open("r", newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f, delimiter=";")
            for row in reader:
                if row["symbol"] != PRODUCT:
                    continue
                timestamp = int(float(row["timestamp"]))
                price_row = price_lookup.get((day, timestamp))
                if price_row is None:
                    continue
                price = float(row["price"])
                wall_mid = price_row["wall_mid"]
                top_mid = price_row["top_mid"]
                side = "buy_pressure" if price >= top_mid else "sell_pressure"
                if price >= price_row["best_ask"]:
                    side = "buy_pressure"
                elif price <= price_row["best_bid"]:
                    side = "sell_pressure"
                trades.append(
                    {
                        "day": day,
                        "timestamp": timestamp,
                        "global_timestamp": day * DAY_STRIDE + timestamp,
                        "price": price,
                        "quantity": int(float(row["quantity"])),
                        "wall_mid": wall_mid,
                        "top_mid": top_mid,
                        "price_minus_wall": price - wall_mid,
                        "side": side,
                    }
                )
    return trades


def future_move_tables(price_by_day: Dict[int, List[Dict[str, float]]]) -> Dict[str, object]:
    horizons = [10, 50, 100, 250, 500, 1000]
    thresholds = [
        ("low_9900", lambda value: value <= 9900, 1),
        ("low_9915", lambda value: value <= 9915, 1),
        ("low_9930", lambda value: value <= 9930, 1),
        ("high_10020", lambda value: value >= 10020, -1),
        ("high_10030", lambda value: value >= 10030, -1),
        ("high_10040", lambda value: value >= 10040, -1),
        ("high_10050", lambda value: value >= 10050, -1),
    ]
    table: Dict[str, Dict[str, Dict[str, float]]] = {}
    for horizon in horizons:
        horizon_key = f"{horizon}_samples"
        table[horizon_key] = {}
        for label, predicate, direction in thresholds:
            moves: List[float] = []
            for rows in price_by_day.values():
                walls = [row["wall_mid"] for row in rows]
                for idx, value in enumerate(walls[:-horizon]):
                    if predicate(value):
                        moves.append(direction * (walls[idx + horizon] - value))
            if moves:
                table[horizon_key][label] = {
                    "n": len(moves),
                    "mean_reversion": statistics.mean(moves),
                    "win_rate": sum(move > 0 for move in moves) / len(moves) * 100.0,
                    "p05": percentile(moves, 0.05),
                    "p50": percentile(moves, 0.50),
                    "p95": percentile(moves, 0.95),
                }
    return table


def run_lengths(price_by_day: Dict[int, List[Dict[str, float]]]) -> Dict[str, Dict[str, float]]:
    conditions = {
        "low_9915": lambda value: value <= 9915,
        "high_10020": lambda value: value >= 10020,
        "high_10030": lambda value: value >= 10030,
        "high_10040": lambda value: value >= 10040,
        "high_10050": lambda value: value >= 10050,
    }
    output: Dict[str, Dict[str, float]] = {}
    for name, predicate in conditions.items():
        runs: List[int] = []
        for rows in price_by_day.values():
            current = 0
            for row in rows:
                if predicate(row["wall_mid"]):
                    current += 1
                elif current:
                    runs.append(current)
                    current = 0
            if current:
                runs.append(current)
        output[name] = {
            "count": len(runs),
            "mean": statistics.mean(runs) if runs else 0.0,
            "median": statistics.median(runs) if runs else 0.0,
            "p90": percentile(runs, 0.90) if runs else 0.0,
            "max": max(runs) if runs else 0.0,
            "top_5": sorted(runs, reverse=True)[:5],
        }
    return output


def feature_correlations(price_by_day: Dict[int, List[Dict[str, float]]]) -> Dict[str, Dict[str, float]]:
    horizons = [10, 50, 100, 250, 500]
    features = ["mid_minus_wall", "top_imbalance", "book_imbalance", "top_spread", "wall_spread"]
    output: Dict[str, Dict[str, float]] = {}
    for horizon in horizons:
        y: List[float] = []
        xs: Dict[str, List[float]] = {feature: [] for feature in features}
        for rows in price_by_day.values():
            walls = [row["wall_mid"] for row in rows]
            for idx, row in enumerate(rows[:-horizon]):
                y.append(walls[idx + horizon] - walls[idx])
                for feature in features:
                    xs[feature].append(row[feature])
        output[f"{horizon}_samples"] = {feature: corr(xs[feature], y) for feature in features}
    return output


def momentum_tables(price_by_day: Dict[int, List[Dict[str, float]]]) -> Dict[str, object]:
    lookbacks = [10, 50, 100, 250]
    horizons = [50, 100, 250, 500]
    output: Dict[str, Dict[str, Dict[str, float]]] = {}
    for lookback in lookbacks:
        for horizon in horizons:
            key = f"lookback_{lookback}_horizon_{horizon}"
            buckets = {
                "high_up_momentum": [],
                "high_down_or_flat_momentum": [],
                "low_down_momentum": [],
                "low_up_or_flat_momentum": [],
            }
            for rows in price_by_day.values():
                walls = [row["wall_mid"] for row in rows]
                for idx in range(lookback, len(walls) - horizon):
                    current = walls[idx]
                    recent = current - walls[idx - lookback]
                    if current >= 10020:
                        reversion = current - walls[idx + horizon]
                        if recent > 0:
                            buckets["high_up_momentum"].append(reversion)
                        else:
                            buckets["high_down_or_flat_momentum"].append(reversion)
                    if current <= 9915:
                        reversion = walls[idx + horizon] - current
                        if recent < 0:
                            buckets["low_down_momentum"].append(reversion)
                        else:
                            buckets["low_up_or_flat_momentum"].append(reversion)
            output[key] = {
                name: {
                    "n": len(values),
                    "mean_reversion": statistics.mean(values) if values else 0.0,
                    "win_rate": sum(value > 0 for value in values) / len(values) * 100.0 if values else 0.0,
                    "p05": percentile(values, 0.05) if values else 0.0,
                    "p50": percentile(values, 0.50) if values else 0.0,
                }
                for name, values in buckets.items()
            }
    return output


def trade_tables(
    trades: List[Dict[str, float]],
    price_by_day: Dict[int, List[Dict[str, float]]],
) -> Dict[str, object]:
    rows_by_day = {day: rows for day, rows in price_by_day.items()}
    index_by_day_ts = {
        day: {int(row["timestamp"]): idx for idx, row in enumerate(rows)}
        for day, rows in rows_by_day.items()
    }
    horizons = [10, 50, 100, 250, 500]
    output: Dict[str, object] = {
        "count": len(trades),
        "quantity_counts": dict(Counter(int(trade["quantity"]) for trade in trades).most_common()),
        "side_counts": dict(Counter(str(trade["side"]) for trade in trades)),
        "price_minus_wall": summarize_values([trade["price_minus_wall"] for trade in trades]),
        "future_by_side": {},
        "future_by_gap_bucket": {},
        "running_extrema_hits": {},
    }

    for horizon in horizons:
        by_side: Dict[str, List[float]] = defaultdict(list)
        by_gap: Dict[str, List[float]] = defaultdict(list)
        for trade in trades:
            day = int(trade["day"])
            idx = index_by_day_ts.get(day, {}).get(int(trade["timestamp"]))
            rows = rows_by_day.get(day, [])
            if idx is None or idx + horizon >= len(rows):
                continue
            future = rows[idx + horizon]["wall_mid"] - trade["wall_mid"]
            by_side[str(trade["side"])].append(future)
            gap = trade["price_minus_wall"]
            if gap >= 7:
                bucket = "high_print_gap_ge_7"
            elif gap <= -7:
                bucket = "low_print_gap_le_-7"
            else:
                bucket = "inside_gap"
            by_gap[bucket].append(future)
        output["future_by_side"][f"{horizon}_samples"] = {
            side: {
                "n": len(values),
                "mean_future_move": statistics.mean(values) if values else 0.0,
                "win_up_pct": sum(value > 0 for value in values) / len(values) * 100.0 if values else 0.0,
            }
            for side, values in by_side.items()
        }
        output["future_by_gap_bucket"][f"{horizon}_samples"] = {
            bucket: {
                "n": len(values),
                "mean_future_move": statistics.mean(values) if values else 0.0,
                "win_up_pct": sum(value > 0 for value in values) / len(values) * 100.0 if values else 0.0,
            }
            for bucket, values in by_gap.items()
        }

    extrema = {
        "buy_pressure_at_running_low": 0,
        "sell_pressure_at_running_high": 0,
        "buy_pressure_at_running_high": 0,
        "sell_pressure_at_running_low": 0,
    }
    for day, rows in rows_by_day.items():
        running_low: Dict[int, float] = {}
        running_high: Dict[int, float] = {}
        low = float("inf")
        high = float("-inf")
        for row in rows:
            low = min(low, row["wall_mid"])
            high = max(high, row["wall_mid"])
            running_low[int(row["timestamp"])] = low
            running_high[int(row["timestamp"])] = high
        for trade in [item for item in trades if int(item["day"]) == day]:
            ts = int(trade["timestamp"])
            wall = trade["wall_mid"]
            at_low = wall <= running_low[ts] + 0.5
            at_high = wall >= running_high[ts] - 0.5
            side = str(trade["side"])
            if side == "buy_pressure" and at_low:
                extrema["buy_pressure_at_running_low"] += 1
            if side == "sell_pressure" and at_high:
                extrema["sell_pressure_at_running_high"] += 1
            if side == "buy_pressure" and at_high:
                extrema["buy_pressure_at_running_high"] += 1
            if side == "sell_pressure" and at_low:
                extrema["sell_pressure_at_running_low"] += 1
    output["running_extrema_hits"] = extrema
    return output


def cross_product_correlations(data_dir: Path) -> Dict[str, Dict[str, float]]:
    walls = load_all_product_walls(data_dir)
    hydro = walls.get(PRODUCT, {})
    output: Dict[str, Dict[str, float]] = {}
    for product, by_day in walls.items():
        if product == PRODUCT:
            continue
        current_returns: List[float] = []
        future_hydro: List[float] = []
        same_returns: List[float] = []
        for day, product_values in by_day.items():
            hydro_values = hydro.get(day)
            if not hydro_values or len(product_values) != len(hydro_values):
                continue
            for idx in range(1, len(product_values) - 50):
                current_returns.append(product_values[idx] - product_values[idx - 1])
                same_returns.append(hydro_values[idx] - hydro_values[idx - 1])
                future_hydro.append(hydro_values[idx + 50] - hydro_values[idx])
        if current_returns:
            output[product] = {
                "same_step_corr": corr(current_returns, same_returns),
                "lead_50_sample_corr_with_future_hydro": corr(current_returns, future_hydro),
            }
    return output


def format_table(rows: List[List[object]]) -> str:
    if not rows:
        return ""
    widths = [max(len(str(row[idx])) for row in rows) for idx in range(len(rows[0]))]
    return "\n".join(
        "  ".join(str(value).rjust(widths[idx]) for idx, value in enumerate(row))
        for row in rows
    )


def build_text_report(report: Dict[str, object]) -> str:
    lines: List[str] = []
    lines.append("HYDROGEL_PACK Structural Signal Research")
    lines.append("=" * 42)
    dist = report["wall_mid_distribution"]
    lines.append(
        f"Wall mid: n={dist['n']} mean={dist['mean']:.2f} stdev={dist['stdev']:.2f} "
        f"p05={dist['p05']:.2f} median={dist['median']:.2f} p95={dist['p95']:.2f} "
        f"min={dist['min']:.2f} max={dist['max']:.2f}"
    )
    lines.append("")

    lines.append("Extreme Reversion")
    for horizon in ["50_samples", "100_samples", "250_samples", "500_samples"]:
        table = [["bucket", "n", "mean_rev", "win%", "p05", "p50", "p95"]]
        for bucket, values in report["future_move_tables"].get(horizon, {}).items():
            table.append(
                [
                    bucket,
                    values["n"],
                    f"{values['mean_reversion']:.2f}",
                    f"{values['win_rate']:.1f}",
                    f"{values['p05']:.2f}",
                    f"{values['p50']:.2f}",
                    f"{values['p95']:.2f}",
                ]
            )
        lines.append(f"\n{horizon}")
        lines.append(format_table(table))

    lines.append("\nExtreme Run Lengths")
    table = [["bucket", "count", "mean", "median", "p90", "max", "top5"]]
    for bucket, values in report["run_lengths"].items():
        table.append(
            [
                bucket,
                values["count"],
                f"{values['mean']:.1f}",
                f"{values['median']:.1f}",
                f"{values['p90']:.1f}",
                values["max"],
                values["top_5"],
            ]
        )
    lines.append(format_table(table))

    lines.append("\nFeature Correlations With Future Wall-Mid Move")
    table = [["horizon", "mid-wall", "top_imb", "book_imb", "top_spread", "wall_spread"]]
    for horizon, values in report["feature_correlations"].items():
        table.append(
            [
                horizon,
                f"{values['mid_minus_wall']:.4f}",
                f"{values['top_imbalance']:.4f}",
                f"{values['book_imbalance']:.4f}",
                f"{values['top_spread']:.4f}",
                f"{values['wall_spread']:.4f}",
            ]
        )
    lines.append(format_table(table))

    lines.append("\nMomentum At Extremes")
    preferred_keys = [
        "lookback_50_horizon_250",
        "lookback_100_horizon_250",
        "lookback_50_horizon_500",
        "lookback_100_horizon_500",
    ]
    for key in preferred_keys:
        values = report["momentum_tables"].get(key, {})
        table = [["bucket", "n", "mean_rev", "win%", "p05", "p50"]]
        for bucket, stats in values.items():
            table.append(
                [
                    bucket,
                    stats["n"],
                    f"{stats['mean_reversion']:.2f}",
                    f"{stats['win_rate']:.1f}",
                    f"{stats['p05']:.2f}",
                    f"{stats['p50']:.2f}",
                ]
            )
        lines.append(f"\n{key}")
        lines.append(format_table(table))

    trades = report["trade_tables"]
    lines.append("\nPublic Trade Signals")
    lines.append(
        f"Hydrogel public trades={trades['count']} side_counts={trades['side_counts']} "
        f"price_minus_wall_mean={trades['price_minus_wall']['mean']:.2f}"
    )
    lines.append(f"Quantity counts={trades['quantity_counts']}")
    lines.append(f"Running extrema hits={trades['running_extrema_hits']}")
    for horizon in ["50_samples", "100_samples", "250_samples", "500_samples"]:
        table = [["bucket", "n", "mean_future", "up%"]]
        for bucket, values in trades["future_by_gap_bucket"].get(horizon, {}).items():
            table.append(
                [
                    bucket,
                    values["n"],
                    f"{values['mean_future_move']:.2f}",
                    f"{values['win_up_pct']:.1f}",
                ]
            )
        lines.append(f"\nTrade gap future move {horizon}")
        lines.append(format_table(table))

    lines.append("\nCross Product Correlations")
    table = [["product", "same_step", "lead50_to_hydro"]]
    for product, values in sorted(report["cross_product_correlations"].items()):
        table.append(
            [
                product,
                f"{values['same_step_corr']:.4f}",
                f"{values['lead_50_sample_corr_with_future_hydro']:.4f}",
            ]
        )
    lines.append(format_table(table))

    return "\n".join(lines) + "\n"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Research structural HYDROGEL_PACK signals from historical data.")
    parser.add_argument("--data-dir", type=Path, default=DEFAULT_DATA_DIR)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_REPORT_DIR)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    data_dir = args.data_dir.resolve()
    out_dir = args.out_dir.resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    price_by_day = load_price_series(data_dir)
    all_walls = [row["wall_mid"] for rows in price_by_day.values() for row in rows]
    trades = load_trades(data_dir, price_by_day)

    report = {
        "run_id": f"hydrogel_signal_research_{uuid.uuid4().hex[:8]}",
        "product": PRODUCT,
        "wall_mid_distribution": summarize_values(all_walls),
        "future_move_tables": future_move_tables(price_by_day),
        "run_lengths": run_lengths(price_by_day),
        "feature_correlations": feature_correlations(price_by_day),
        "momentum_tables": momentum_tables(price_by_day),
        "trade_tables": trade_tables(trades, price_by_day),
        "cross_product_correlations": cross_product_correlations(data_dir),
    }

    json_path = out_dir / f"{report['run_id']}.json"
    text_path = out_dir / f"{report['run_id']}.txt"
    json_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    text = build_text_report(report)
    text_path.write_text(text, encoding="utf-8")
    print(text)
    print(f"Wrote {json_path}")
    print(f"Wrote {text_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
