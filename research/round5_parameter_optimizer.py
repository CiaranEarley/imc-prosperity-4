from __future__ import annotations

import csv
import importlib.util
import json
import math
import statistics
import sys
from copy import deepcopy
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple


ROOT = Path(__file__).resolve().parent
REPO_ROOT = ROOT.parents[1]
BACKTESTER = REPO_ROOT / "tools" / "backtester"
DATA_DIR = BACKTESTER / "Price & Trade Data"
BASE_STRATEGY = REPO_ROOT / "prosperity4" / "strategies" / "round5_dynamic_multi_asset_market_maker.py"
OUT_DIR = ROOT / "optimizer_reports"
OUT_DIR.mkdir(exist_ok=True)

WINDOWS = (20, 50, 100, 250, 500, 1000, 2000)
MIN_SAMPLES = {20: 5, 50: 12, 100: 25, 250: 62, 500: 125, 1000: 250, 2000: 500}
LIMIT = 10
MIN_SPREAD = 2
OFFSET = 1
INV_SKEW = 0.15


OVERLAY_PARAMS = {
    "GALAXY_SOUNDS_PLANETARY_RINGS": ("rings", 200, 1200, 1.5, 0.375, 10, 1, 200, 0),
    "PANEL_1X4": ("p14", 100, 600, 1.5, 0.375, 7, 1, 400, 600),
    "PANEL_2X4": ("p24", 200, 1200, 1.0, 0.25, 7, -1, 400, 600),
}


def import_base():
    sys.path.insert(0, str(BACKTESTER))
    sys.path.insert(1, str(ROOT))
    spec = importlib.util.spec_from_file_location("razorgrid_base", BASE_STRATEGY)
    if spec is None or spec.loader is None:
        raise RuntimeError("Could not load RazorGrid.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules["razorgrid_base"] = module
    spec.loader.exec_module(module)
    return module.Trader


def as_int(value: str) -> Optional[int]:
    if value is None or value == "":
        return None
    return int(float(value))


def wall_mid(row: dict) -> float:
    bids = []
    asks = []
    for level in (1, 2, 3):
        b = as_int(row.get(f"bid_price_{level}", ""))
        a = as_int(row.get(f"ask_price_{level}", ""))
        if b is not None:
            bids.append(b)
        if a is not None:
            asks.append(a)
    if bids and asks:
        return (min(bids) + max(asks)) / 2.0
    return float(row["mid_price"])


def load_product_data() -> Dict[str, Dict[int, List[dict]]]:
    trades: Dict[Tuple[int, int, str], List[Tuple[float, int]]] = {}
    for trade_path in sorted(DATA_DIR.glob("trades_round_5_day_*.csv")):
        day = int(trade_path.stem.rsplit("_day_", 1)[-1])
        with trade_path.open("r", newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f, delimiter=";"):
                key = (day, int(row["timestamp"]), row["symbol"])
                trades.setdefault(key, []).append((float(row["price"]), int(float(row["quantity"]))))

    by_product: Dict[str, Dict[int, List[dict]]] = {}
    for price_path in sorted(DATA_DIR.glob("prices_round_5_day_*.csv")):
        day = int(price_path.stem.rsplit("_day_", 1)[-1])
        with price_path.open("r", newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f, delimiter=";"):
                product = row["product"]
                bid = as_int(row.get("bid_price_1", ""))
                ask = as_int(row.get("ask_price_1", ""))
                if bid is None or ask is None or bid >= ask:
                    continue
                rec = {
                    "day": day,
                    "ts": int(row["timestamp"]),
                    "bid": bid,
                    "ask": ask,
                    "bid_vol": max(0, int(float(row.get("bid_volume_1") or 0))),
                    "ask_vol": max(0, int(float(row.get("ask_volume_1") or 0))),
                    "mid": (bid + ask) / 2.0,
                    "spread": ask - bid,
                    "mark": wall_mid(row),
                    "trades": trades.get((day, int(row["timestamp"]), product), []),
                }
                by_product.setdefault(product, {}).setdefault(day, []).append(rec)
    return by_product


def simulate_passive_orders(
    rec: dict,
    position: int,
    cash: float,
    buy_price: Optional[int],
    buy_qty: int,
    sell_price: Optional[int],
    sell_qty: int,
) -> Tuple[int, float, int]:
    fills = 0
    trade_remaining = [qty for _, qty in rec["trades"]]
    orders = []
    if buy_price is not None and buy_qty > 0:
        orders.append((True, buy_price, buy_qty))
    if sell_price is not None and sell_qty > 0:
        orders.append((False, sell_price, sell_qty))

    for is_buy, price, qty in orders:
        remaining = qty
        for idx, (trade_price, _) in enumerate(rec["trades"]):
            if remaining <= 0:
                break
            if trade_remaining[idx] <= 0:
                continue
            matches = trade_price <= price if is_buy else trade_price >= price
            if not matches:
                continue
            fill_qty = min(remaining, trade_remaining[idx])
            signed = fill_qty if is_buy else -fill_qty
            position += signed
            cash -= signed * price
            remaining -= fill_qty
            trade_remaining[idx] -= fill_qty
            fills += fill_qty
    return position, cash, fills


def overlay_target(rec: dict, item: dict, state: dict, params: Tuple, seen: int) -> Optional[int]:
    key, fast, slow, entry, exit_level, size, mult, warmup, max_age = params
    score = mult * (float(item["fast"]) - float(item["slow"])) / max(4.0, float(item["dev"]))
    st_key = "overlay_" + key
    age_key = st_key + "_age"
    st = int(state.get(st_key, 0))
    old = st
    if seen >= warmup:
        if score > entry:
            st = 1
        elif score < -entry:
            st = -1
        elif abs(score) < exit_level:
            st = 0
    else:
        st = 0
    age = 0 if st == 0 else int(state.get(age_key, 0)) + 1 if st == old else 1
    if max_age and st and age > max_age:
        st = 0
        age = 0
    state[st_key] = st
    state[age_key] = age

    af = 2.0 / (fast + 1.0)
    aslow = 2.0 / (slow + 1.0)
    old_slow = float(item.get("slow", rec["mid"]))
    item["fast"] = af * rec["mid"] + (1.0 - af) * float(item.get("fast", rec["mid"]))
    item["slow"] = aslow * rec["mid"] + (1.0 - aslow) * old_slow
    item["dev"] = max(4.0, aslow * abs(rec["mid"] - old_slow) + (1.0 - aslow) * float(item.get("dev", 4.0)))
    return st * size if st else None


def simulate_product(product: str, config: dict, day_data: Dict[int, List[dict]], overlay: bool = True) -> dict:
    total = 0.0
    day_pnls = []
    stitched_points = []
    gross_volume = 0
    quote_count = 0
    for day in sorted(day_data):
        cash = 0.0
        pos = 0
        seen = 0
        n = 0
        ema: Dict[int, float] = {}
        overlay_state: Dict[str, float] = {}
        overlay_item = None
        if product in OVERLAY_PARAMS:
            first_mid = day_data[day][0]["mid"]
            overlay_item = {"fast": first_mid, "slow": first_mid, "dev": 4.0}
        graph = []
        for rec in day_data[day]:
            fair = None
            mode = config.get("mode", "off")
            if mode == "touch":
                fair = rec["mid"]
            elif mode == "fair":
                window = int(config["window"])
                if n >= MIN_SAMPLES[window] and window in ema:
                    fair = ema[window]

            buy_price = sell_price = None
            buy_qty = sell_qty = 0
            if fair is not None and rec["spread"] >= MIN_SPREAD:
                buy_price = min(rec["bid"] + int(config.get("offset", OFFSET)), rec["ask"] - 1)
                sell_price = max(rec["ask"] - int(config.get("offset", OFFSET)), rec["bid"] + 1)
                edge = float(config.get("edge", 0.0))
                soft = int(config.get("soft_limit", 0))
                size = int(config.get("size", 0))
                buy_edge = fair - buy_price
                sell_edge = sell_price - fair
                buy_threshold = edge + max(0, pos) * INV_SKEW
                sell_threshold = edge + max(0, -pos) * INV_SKEW
                buy_capacity = min(soft - pos, LIMIT - pos)
                sell_capacity = min(soft + pos, LIMIT + pos)
                if buy_capacity > 0 and buy_edge >= buy_threshold:
                    buy_qty = min(size, buy_capacity)
                    quote_count += 1
                else:
                    buy_price = None
                if sell_capacity > 0 and sell_edge >= sell_threshold:
                    sell_qty = min(size, sell_capacity)
                    quote_count += 1
                else:
                    sell_price = None

            # The real backtester cancels the whole product if the aggregate order batch breaches.
            batch_buy = buy_qty
            batch_sell = sell_qty
            active_delta = 0
            target = None
            if overlay and product in OVERLAY_PARAMS and overlay_item is not None:
                target = overlay_target(rec, overlay_item, overlay_state, OVERLAY_PARAMS[product], seen)
                if target is not None:
                    active_delta = max(-LIMIT, min(LIMIT, int(target))) - pos
                    if active_delta > 0:
                        batch_buy += min(active_delta, rec["ask_vol"], LIMIT - pos)
                    elif active_delta < 0:
                        batch_sell += min(-active_delta, rec["bid_vol"], LIMIT + pos)
            if pos + batch_buy <= LIMIT and pos - batch_sell >= -LIMIT:
                pos, cash, fills = simulate_passive_orders(rec, pos, cash, buy_price, buy_qty, sell_price, sell_qty)
                gross_volume += fills
                if target is not None:
                    delta = max(-LIMIT, min(LIMIT, int(target))) - pos
                    if delta > 0:
                        qty = min(delta, rec["ask_vol"], LIMIT - pos)
                        if qty > 0:
                            pos += qty
                            cash -= qty * rec["ask"]
                            gross_volume += qty
                            quote_count += 1
                    elif delta < 0:
                        qty = min(-delta, rec["bid_vol"], LIMIT + pos)
                        if qty > 0:
                            pos -= qty
                            cash += qty * rec["bid"]
                            gross_volume += qty
                            quote_count += 1

            if mode == "fair":
                for window in WINDOWS:
                    prev = ema.get(window)
                    if prev is None:
                        ema[window] = rec["mid"]
                    else:
                        alpha = 2.0 / (window + 1.0)
                        ema[window] = prev + alpha * (rec["mid"] - prev)
                n += 1

            pnl = cash + pos * rec["mark"]
            graph.append(pnl)
            stitched_points.append(total + pnl)
            seen += 1
        day_pnls.append(graph[-1] if graph else 0.0)
        total += day_pnls[-1]

    max_dd = 0.0
    peak = -1e100
    for pnl in stitched_points:
        peak = max(peak, pnl)
        max_dd = max(max_dd, peak - pnl)
    return {
        "product": product,
        "config": config,
        "total": total,
        "day_pnls": day_pnls,
        "min_day": min(day_pnls) if day_pnls else 0.0,
        "max_day": max(day_pnls) if day_pnls else 0.0,
        "stdev_day": statistics.pstdev(day_pnls) if len(day_pnls) > 1 else 0.0,
        "max_dd": max_dd,
        "gross_volume": gross_volume,
        "quote_count": quote_count,
    }


def score_result(result: dict) -> float:
    total = result["total"]
    min_day = result["min_day"]
    dd = result["max_dd"]
    stdev = result["stdev_day"]
    return total - 0.75 * max(0.0, -min_day) - 0.03 * dd - 0.10 * stdev


def candidate_configs(current: dict) -> List[dict]:
    candidates: List[dict] = [{"mode": "off", "soft_limit": 0, "size": 0}]
    for soft in (5, 7, 10):
        for size in (3, 5, 7, 10):
            if size <= soft:
                candidates.append({"mode": "touch", "soft_limit": soft, "size": size})
    for window in WINDOWS:
        for edge in (0.0, 1.0, 2.0, 4.0, 6.0, 8.0, 10.0, 12.0, 16.0, 20.0, 24.0, 32.0, 40.0):
            for soft, size in ((3, 3), (5, 5), (7, 7), (10, 10), (10, 7), (7, 5)):
                candidates.append({"mode": "fair", "window": window, "edge": edge, "soft_limit": soft, "size": size})
    # Preserve the exact current config even if it falls outside the grid.
    if current not in candidates:
        candidates.append(deepcopy(current))
    unique = []
    seen = set()
    for cfg in candidates:
        key = json.dumps(cfg, sort_keys=True)
        if key not in seen:
            seen.add(key)
            unique.append(cfg)
    return unique


def format_cfg(cfg: dict) -> str:
    if cfg.get("mode") == "off":
        return "off"
    if cfg.get("mode") == "touch":
        return f"touch s{cfg['soft_limit']} q{cfg['size']}"
    return f"fair w{cfg['window']} e{cfg['edge']} s{cfg['soft_limit']} q{cfg['size']}"


def optimise_products() -> None:
    Trader = import_base()
    base_config = deepcopy(Trader.PRODUCT_CONFIG)
    data = load_product_data()
    rows = []
    chosen = {}
    for idx, product in enumerate(sorted(base_config), start=1):
        if product not in data:
            continue
        current = simulate_product(product, base_config[product], data[product])
        best = current
        best_score = score_result(current)
        best_total = current
        for cfg in candidate_configs(base_config[product]):
            result = simulate_product(product, cfg, data[product])
            result_score = score_result(result)
            if result["total"] > best_total["total"]:
                best_total = result
            if result_score > best_score:
                best = result
                best_score = result_score
        chosen[product] = best["config"]
        rows.append({
            "product": product,
            "current_total": current["total"],
            "current_days": current["day_pnls"],
            "current_dd": current["max_dd"],
            "best_score_total": best["total"],
            "best_score_days": best["day_pnls"],
            "best_score_dd": best["max_dd"],
            "best_score_config": best["config"],
            "best_score_text": format_cfg(best["config"]),
            "best_raw_total": best_total["total"],
            "best_raw_days": best_total["day_pnls"],
            "best_raw_dd": best_total["max_dd"],
            "best_raw_config": best_total["config"],
            "best_raw_text": format_cfg(best_total["config"]),
            "delta_score_pick": best["total"] - current["total"],
            "delta_raw_pick": best_total["total"] - current["total"],
        })
        print(
            f"{idx:02d}/50 {product:34s} cur={current['total']:9.1f} "
            f"pick={best['total']:9.1f} {format_cfg(best['config'])}",
            flush=True,
        )

    report_path = OUT_DIR / "product_grid_report.json"
    report_path.write_text(json.dumps(rows, indent=2), encoding="utf-8")
    chosen_path = OUT_DIR / "chosen_config.json"
    chosen_path.write_text(json.dumps(chosen, indent=2), encoding="utf-8")
    print(f"Wrote {report_path}")
    print(f"Wrote {chosen_path}")


if __name__ == "__main__":
    optimise_products()
