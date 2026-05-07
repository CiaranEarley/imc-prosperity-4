from __future__ import annotations

import argparse
import contextlib
import copy
import csv
import importlib.util
import io
import json
import math
import shutil
import statistics
import sys
import tempfile
import traceback
import uuid
import zipfile
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

from datamodel import Listing, Observation, Order, OrderDepth, Trade, TradingState


ROOT = Path(__file__).resolve().parent
DEFAULT_DATA_DIR = ROOT / "Price & Trade Data"
DEFAULT_OUT_DIR = ROOT / "Runs"
DAY_TIMESTAMP_STRIDE = 1_000_000

DEFAULT_LIMITS = {
    "HYDROGEL_PACK": 200,
    "VELVETFRUIT_EXTRACT": 200,
    "VEV_4000": 300,
    "VEV_4500": 300,
    "VEV_5000": 300,
    "VEV_5100": 300,
    "VEV_5200": 300,
    "VEV_5300": 300,
    "VEV_5400": 300,
    "VEV_5500": 300,
    "VEV_6000": 300,
    "VEV_6500": 300,
}

PRICE_HEADER = [
    "day",
    "timestamp",
    "product",
    "bid_price_1",
    "bid_volume_1",
    "bid_price_2",
    "bid_volume_2",
    "bid_price_3",
    "bid_volume_3",
    "ask_price_1",
    "ask_volume_1",
    "ask_price_2",
    "ask_volume_2",
    "ask_price_3",
    "ask_volume_3",
    "mid_price",
    "profit_and_loss",
]


@dataclass
class PriceRow:
    raw: Dict[str, str]
    day: int
    timestamp: int
    product: str
    mid_price: float


@dataclass
class Fill:
    timestamp: int
    symbol: str
    price: float
    quantity: int
    side: str
    liquidity: str


def parse_float(value: str) -> Optional[float]:
    if value is None or value == "":
        return None
    return float(value)


def parse_int(value: str) -> Optional[int]:
    if value is None or value == "":
        return None
    return int(float(value))


def format_number(value: Optional[float]) -> str:
    if value is None:
        return ""
    if abs(value - round(value)) < 1e-9:
        return str(int(round(value)))
    return str(value)


def load_price_rows(path: Path) -> List[PriceRow]:
    rows: List[PriceRow] = []
    with path.open("r", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f, delimiter=";")
        for raw in reader:
            rows.append(
                PriceRow(
                    raw=raw,
                    day=int(raw["day"]),
                    timestamp=int(raw["timestamp"]),
                    product=raw["product"],
                    mid_price=float(raw["mid_price"]),
                )
            )
    return rows


def load_market_trades(path: Path) -> Dict[int, Dict[str, List[Trade]]]:
    trades_by_time: Dict[int, Dict[str, List[Trade]]] = {}
    if not path.exists():
        return trades_by_time
    with path.open("r", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f, delimiter=";")
        for row in reader:
            ts = int(row["timestamp"])
            symbol = row["symbol"]
            trade = Trade(
                symbol=symbol,
                price=float(row["price"]),
                quantity=int(float(row["quantity"])),
                buyer=row.get("buyer", "") or "",
                seller=row.get("seller", "") or "",
                timestamp=ts,
            )
            trades_by_time.setdefault(ts, {}).setdefault(symbol, []).append(trade)
    return trades_by_time


def group_prices_by_time(rows: Iterable[PriceRow]) -> Dict[int, Dict[str, PriceRow]]:
    grouped: Dict[int, Dict[str, PriceRow]] = {}
    for row in rows:
        grouped.setdefault(row.timestamp, {})[row.product] = row
    return grouped


def build_order_depth(row: PriceRow) -> OrderDepth:
    depth = OrderDepth()
    for level in (1, 2, 3):
        bid_price = parse_int(row.raw.get(f"bid_price_{level}", ""))
        bid_volume = parse_int(row.raw.get(f"bid_volume_{level}", ""))
        if bid_price is not None and bid_volume is not None and bid_volume > 0:
            depth.buy_orders[bid_price] = bid_volume

        ask_price = parse_int(row.raw.get(f"ask_price_{level}", ""))
        ask_volume = parse_int(row.raw.get(f"ask_volume_{level}", ""))
        if ask_price is not None and ask_volume is not None and ask_volume > 0:
            depth.sell_orders[ask_price] = -ask_volume
    return depth


def book_mark(row: PriceRow, mode: str) -> float:
    if mode == "mid":
        return row.mid_price

    bid_prices: List[int] = []
    ask_prices: List[int] = []
    for level in (1, 2, 3):
        bid = parse_int(row.raw.get(f"bid_price_{level}", ""))
        ask = parse_int(row.raw.get(f"ask_price_{level}", ""))
        if bid is not None:
            bid_prices.append(bid)
        if ask is not None:
            ask_prices.append(ask)

    if mode == "wall-mid" and bid_prices and ask_prices:
        return (min(bid_prices) + max(ask_prices)) / 2
    return row.mid_price


def clone_market_trades(trades: Dict[str, List[Trade]], day: int = 0) -> Dict[str, List[Trade]]:
    cloned: Dict[str, List[Trade]] = {}
    for product, items in trades.items():
        cloned[product] = [
            Trade(
                symbol=trade.symbol,
                price=trade.price,
                quantity=trade.quantity,
                buyer=trade.buyer,
                seller=trade.seller,
                timestamp=to_global_timestamp(day, int(trade.timestamp)),
            )
            for trade in items
        ]
    return cloned


def import_trader(strategy_path: Path):
    module_name = f"strategy_{strategy_path.stem}_{uuid.uuid4().hex}"
    sys.path.insert(0, str(ROOT))
    sys.path.insert(1, str(strategy_path.parent))
    spec = importlib.util.spec_from_file_location(module_name, strategy_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load strategy from {strategy_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    if not hasattr(module, "Trader"):
        raise RuntimeError(f"{strategy_path} does not define a Trader class")
    trader = module.Trader()
    return trader


def infer_limits(trader, products: Iterable[str], cli_limits: Dict[str, int]) -> Dict[str, int]:
    limits = dict(DEFAULT_LIMITS)
    limits.update(cli_limits)

    product = getattr(trader, "PRODUCT", None)
    position_limit = getattr(trader, "POSITION_LIMIT", None)
    if isinstance(product, str) and isinstance(position_limit, int):
        limits[product] = position_limit

    for p in products:
        limits.setdefault(p, 1_000_000)
    return limits


def normalise_strategy_output(result) -> Dict[str, List[Order]]:
    if result is None:
        return {}
    if not isinstance(result, dict):
        return {}
    normalised: Dict[str, List[Order]] = {}
    for product, orders in result.items():
        if not orders:
            continue
        clean_orders: List[Order] = []
        for order in orders:
            if isinstance(order, Order):
                clean_orders.append(order)
            elif hasattr(order, "symbol") and hasattr(order, "price") and hasattr(order, "quantity"):
                clean_orders.append(Order(order.symbol, int(order.price), int(order.quantity)))
            elif isinstance(order, (list, tuple)) and len(order) >= 3:
                clean_orders.append(Order(str(order[0]), int(order[1]), int(order[2])))
        if clean_orders:
            normalised[product] = clean_orders
    return normalised


def limit_check(position: int, orders: List[Order], limit: int) -> bool:
    buy_qty = sum(order.quantity for order in orders if order.quantity > 0)
    sell_qty = sum(-order.quantity for order in orders if order.quantity < 0)
    return position + buy_qty <= limit and position - sell_qty >= -limit


def match_orders(
    timestamp: int,
    product: str,
    orders: List[Order],
    visible_depth: OrderDepth,
    public_trade_pool: List[Trade],
    fill_mode: str,
) -> Tuple[List[Fill], List[Order]]:
    depth = copy.deepcopy(visible_depth)
    fills: List[Fill] = []
    passive_orders: List[Order] = []

    for order in orders:
        if order.quantity == 0:
            continue
        remaining = abs(order.quantity)
        limit_price = int(order.price)

        if order.quantity > 0:
            for ask_price in sorted(depth.sell_orders):
                if remaining <= 0 or ask_price > limit_price:
                    break
                available = -depth.sell_orders[ask_price]
                if available <= 0:
                    continue
                qty = min(remaining, available)
                fills.append(Fill(timestamp, product, float(ask_price), qty, "BUY", "active"))
                remaining -= qty
                available -= qty
                depth.sell_orders[ask_price] = -available
            if remaining > 0:
                passive_orders.append(Order(product, limit_price, remaining))

        else:
            for bid_price in sorted(depth.buy_orders, reverse=True):
                if remaining <= 0 or bid_price < limit_price:
                    break
                available = depth.buy_orders[bid_price]
                if available <= 0:
                    continue
                qty = min(remaining, available)
                fills.append(Fill(timestamp, product, float(bid_price), qty, "SELL", "active"))
                remaining -= qty
                available -= qty
                depth.buy_orders[bid_price] = available
            if remaining > 0:
                passive_orders.append(Order(product, limit_price, -remaining))

    if fill_mode == "active":
        return fills, passive_orders

    trade_remaining = [trade.quantity for trade in public_trade_pool]
    for passive in passive_orders:
        remaining = abs(passive.quantity)
        if remaining <= 0:
            continue

        is_buy = passive.quantity > 0
        for idx, trade in enumerate(public_trade_pool):
            if remaining <= 0:
                break
            if trade_remaining[idx] <= 0:
                continue

            if fill_mode == "passive-cross":
                matches = trade.price < passive.price if is_buy else trade.price > passive.price
            else:
                matches = trade.price <= passive.price if is_buy else trade.price >= passive.price

            if not matches:
                continue

            qty = min(remaining, trade_remaining[idx])
            side = "BUY" if is_buy else "SELL"
            fills.append(Fill(timestamp, product, float(passive.price), qty, side, "passive"))
            remaining -= qty
            trade_remaining[idx] -= qty

    return fills, passive_orders


def fills_to_trades(fills: List[Fill]) -> Dict[str, List[Trade]]:
    own: Dict[str, List[Trade]] = {}
    for fill in fills:
        if fill.side == "BUY":
            trade = Trade(
                symbol=fill.symbol,
                price=fill.price,
                quantity=fill.quantity,
                buyer="SUBMISSION",
                seller="BOOK" if fill.liquidity == "active" else "MARKET",
                timestamp=fill.timestamp,
            )
        else:
            trade = Trade(
                symbol=fill.symbol,
                price=fill.price,
                quantity=fill.quantity,
                buyer="BOOK" if fill.liquidity == "active" else "MARKET",
                seller="SUBMISSION",
                timestamp=fill.timestamp,
            )
        own.setdefault(fill.symbol, []).append(trade)
    return own


def trade_to_history_row(trade: Trade) -> Dict[str, object]:
    return {
        "timestamp": trade.timestamp,
        "buyer": trade.buyer,
        "seller": trade.seller,
        "symbol": trade.symbol,
        "currency": "XIRECS",
        "price": trade.price,
        "quantity": trade.quantity,
    }


def apply_fills(
    fills: List[Fill],
    cash: Dict[str, float],
    position: Dict[str, int],
) -> None:
    for fill in fills:
        signed_qty = fill.quantity if fill.side == "BUY" else -fill.quantity
        position[fill.symbol] = position.get(fill.symbol, 0) + signed_qty
        cash.setdefault(fill.symbol, 0.0)
        cash[fill.symbol] -= signed_qty * fill.price


def write_activities_log(rows: List[Dict[str, object]]) -> str:
    out = io.StringIO()
    writer = csv.DictWriter(out, fieldnames=PRICE_HEADER, delimiter=";", lineterminator="\n")
    writer.writeheader()
    for row in rows:
        writer.writerow(row)
    return out.getvalue().rstrip("\n")


def write_graph_log(points: List[Tuple[int, float]]) -> str:
    out = io.StringIO()
    writer = csv.writer(out, delimiter=";", lineterminator="\n")
    writer.writerow(["timestamp", "value"])
    for ts, value in points:
        writer.writerow([ts, value])
    return out.getvalue().rstrip("\n")


def read_archive_payload(path: Path) -> dict:
    with zipfile.ZipFile(path, "r") as archive:
        log_entries = [entry for entry in archive.namelist() if entry.lower().endswith(".log")]
        json_entries = [
            entry
            for entry in archive.namelist()
            if entry.lower().endswith(".json") and not entry.lower().endswith("_summary.json")
        ]
        for entry in log_entries + json_entries:
            payload = json.loads(archive.read(entry).decode("utf-8", errors="replace"))
            if payload.get("activitiesLog"):
                return payload
    raise ValueError(f"No usable run payload found in {path}")


def to_global_timestamp(day: int, timestamp: int) -> int:
    if abs(timestamp) >= DAY_TIMESTAMP_STRIDE:
        return timestamp
    return day * DAY_TIMESTAMP_STRIDE + timestamp


def to_local_timestamp(timestamp: int) -> int:
    if abs(timestamp) >= DAY_TIMESTAMP_STRIDE:
        return timestamp % DAY_TIMESTAMP_STRIDE
    return timestamp


def adjust_lambda_log_timestamps(lambda_log: str, day: int) -> str:
    if not lambda_log:
        return lambda_log
    adjusted_lines: List[str] = []
    for line in lambda_log.splitlines():
        stripped = line.strip()
        if not stripped:
            adjusted_lines.append(line)
            continue
        try:
            parsed = json.loads(stripped)
        except Exception:
            adjusted_lines.append(line)
            continue
        if isinstance(parsed, dict) and parsed.get("timestamp") is not None:
            try:
                parsed["timestamp"] = to_global_timestamp(day, int(parsed["timestamp"]))
            except Exception:
                pass
            adjusted_lines.append(json.dumps(parsed, separators=(",", ":")))
        else:
            adjusted_lines.append(line)
    return "\n".join(adjusted_lines)


def combine_day_archives(
    day_summaries: List[Dict[str, object]],
    strategy_path: Path,
    out_dir: Path,
    fill_mode: str,
    mark_mode: str,
    copy_to_visualiser: Optional[Path],
) -> Dict[str, object]:
    if not day_summaries:
        raise ValueError("No day summaries to combine")

    activities: List[Dict[str, object]] = []
    graph_points: List[Tuple[int, float]] = []
    lambda_logs: List[Dict[str, object]] = []
    trade_history: List[Dict[str, object]] = []
    product_offsets: Dict[str, float] = defaultdict(float)
    total_offset = 0.0
    final_positions: List[Dict[str, object]] = []
    source_archives: List[str] = []

    for day_summary in day_summaries:
        archive_path = Path(str(day_summary["archive"]))
        source_archives.append(str(archive_path))
        payload = read_archive_payload(archive_path)

        raw_activities = payload.get("activitiesLog", "")
        activity_rows = list(csv.DictReader(raw_activities.splitlines(), delimiter=";")) if raw_activities else []
        if activity_rows:
            days = sorted({int(row["day"]) for row in activity_rows if row.get("day") not in (None, "")})
            day = days[0] if days else 0
        else:
            day = 0

        final_by_product: Dict[str, float] = {}
        for row in activity_rows:
            product = row.get("product", "")
            try:
                original_pnl = float(row.get("profit_and_loss", "0") or 0.0)
            except Exception:
                original_pnl = 0.0
            final_by_product[product] = original_pnl
            row["profit_and_loss"] = original_pnl + product_offsets[product]
            try:
                row["timestamp"] = to_local_timestamp(int(float(row.get("timestamp", 0))))
            except Exception:
                pass
            activities.append(row)
        for product, final_pnl in final_by_product.items():
            product_offsets[product] += final_pnl

        raw_graph = payload.get("graphLog", "")
        if isinstance(raw_graph, str) and raw_graph.strip():
            reader = csv.DictReader(raw_graph.splitlines(), delimiter=";")
            last_value = 0.0
            for row in reader:
                try:
                    ts = int(float(row["timestamp"]))
                    value = float(row["value"])
                except Exception:
                    continue
                last_value = value
                graph_points.append((to_global_timestamp(day, ts), total_offset + value))
            total_offset += last_value
        else:
            try:
                total_offset += float(payload.get("profit", 0.0) or 0.0)
            except Exception:
                pass

        for log_entry in payload.get("logs", []) or []:
            entry = dict(log_entry)
            try:
                entry["timestamp"] = to_global_timestamp(day, int(entry.get("timestamp", 0)))
            except Exception:
                pass
            entry["lambdaLog"] = adjust_lambda_log_timestamps(entry.get("lambdaLog", "") or "", day)
            lambda_logs.append(entry)

        for trade in payload.get("tradeHistory", []) or []:
            adjusted = dict(trade)
            try:
                adjusted["timestamp"] = to_global_timestamp(day, int(float(adjusted.get("timestamp", 0))))
            except Exception:
                pass
            trade_history.append(adjusted)

        final_positions = payload.get("positions", []) or final_positions

    graph_points.sort(key=lambda item: item[0])
    trade_history.sort(key=lambda item: (int(item.get("timestamp", 0)), str(item.get("symbol", "")), float(item.get("price", 0.0))))
    lambda_logs.sort(key=lambda item: int(item.get("timestamp", 0) or 0))

    activities_log = write_activities_log(activities)
    graph_log = write_graph_log(graph_points)
    profit = graph_points[-1][1] if graph_points else total_offset
    run_id = f"bt_{strategy_path.stem}_stitched_{uuid.uuid4().hex[:8]}"
    archive_path = out_dir / f"{run_id}.zip"

    stats = calculate_stats(graph_points, [], 0)
    run_json = {
        "round": "backtest",
        "status": "complete",
        "profit": profit,
        "activitiesLog": activities_log,
        "graphLog": graph_log,
        "positions": final_positions,
    }
    run_log = {
        "submissionId": run_id,
        "activitiesLog": activities_log,
        "graphLog": graph_log,
        "profit": profit,
        "positions": final_positions,
        "logs": lambda_logs,
        "tradeHistory": trade_history,
    }
    summary = {
        "run_id": run_id,
        "strategy": str(strategy_path),
        "source_archives": source_archives,
        "fill_mode": fill_mode,
        "mark_mode": mark_mode,
        "profit": profit,
        "positions": final_positions,
        "stats": stats,
        "stitching": "Historical days were simulated independently, then PnL/logs were stitched into one cumulative visualiser archive.",
        "notes": [
            "This is a replay backtest. It cannot perfectly model hidden bot flow after our orders.",
            "Day boundaries are shown using global timestamps: day * 1,000,000 + timestamp.",
            "Product PnL is cumulatively offset by day so stats and charts represent the stitched run.",
        ],
    }

    with zipfile.ZipFile(archive_path, "w", compression=zipfile.ZIP_DEFLATED) as z:
        z.writestr(f"{run_id}.json", json.dumps(run_json))
        z.writestr(f"{run_id}.log", json.dumps(run_log))
        z.writestr(f"{run_id}_summary.json", json.dumps(summary, indent=2))
        z.writestr(f"{strategy_path.name}", strategy_path.read_text(encoding="utf-8"))

    if copy_to_visualiser is not None:
        copy_to_visualiser.mkdir(parents=True, exist_ok=True)
        shutil.copy2(archive_path, copy_to_visualiser / archive_path.name)

    return {
        "run_id": run_id,
        "archive": str(archive_path),
        "visualiser_archive": str(copy_to_visualiser / archive_path.name) if copy_to_visualiser else "",
        "profit": profit,
        "stats": stats,
        "positions": final_positions,
    }


def calculate_stats(points: List[Tuple[int, float]], fills: List[Fill], quote_count: int) -> Dict[str, float]:
    if not points:
        return {}
    pnl = [value for _, value in points]
    diffs = [b - a for a, b in zip(pnl, pnl[1:])]
    nonzero = [x for x in diffs if abs(x) > 1e-9]
    wins = [x for x in nonzero if x > 0]
    losses = [x for x in nonzero if x < 0]

    mean = statistics.mean(diffs) if diffs else 0.0
    std = statistics.pstdev(diffs) if len(diffs) > 1 else 0.0
    downside = statistics.pstdev([min(0.0, x) for x in diffs]) if len(diffs) > 1 else 0.0
    sharpe = mean / std * math.sqrt(len(diffs)) if std > 1e-12 else 0.0
    sortino = mean / downside * math.sqrt(len(diffs)) if downside > 1e-12 else 0.0

    peak = pnl[0]
    max_dd = 0.0
    underwater = 0
    for value in pnl:
        if value >= peak:
            peak = value
        else:
            underwater += 1
            max_dd = max(max_dd, peak - value)

    total = pnl[-1]
    cvar_95 = 0.0
    if losses:
        sorted_losses = sorted(losses)
        tail_n = max(1, math.ceil(len(sorted_losses) * 0.05))
        cvar_95 = statistics.mean(sorted_losses[:tail_n])

    gross_profit = sum(wins)
    gross_loss = -sum(losses)
    profit_factor = gross_profit / gross_loss if gross_loss > 1e-12 else 0.0
    calmar = total / max_dd if max_dd > 1e-12 else 0.0

    return {
        "total_pnl": total,
        "sharpe": sharpe,
        "sortino": sortino,
        "calmar": calmar,
        "max_drawdown_abs": max_dd,
        "drawdown_time_pct": underwater / len(pnl) * 100,
        "win_rate_pct": len(wins) / len(nonzero) * 100 if nonzero else 0.0,
        "cvar_95": cvar_95,
        "profit_factor": profit_factor,
        "expectancy": statistics.mean(nonzero) if nonzero else 0.0,
        "best_step": max(diffs) if diffs else 0.0,
        "worst_step": min(diffs) if diffs else 0.0,
        "data_points": float(len(points)),
        "fills": float(len(fills)),
        "gross_volume": float(sum(fill.quantity for fill in fills)),
        "quotes": float(quote_count),
        "fill_quote_pct": len(fills) / quote_count * 100 if quote_count else 0.0,
    }


def load_limits(path: Optional[Path]) -> Dict[str, int]:
    if path is None:
        return {}
    with path.open("r", encoding="utf-8") as f:
        raw = json.load(f)
    return {str(k): int(v) for k, v in raw.items()}


def run_day(
    strategy_path: Path,
    price_path: Path,
    trade_path: Path,
    out_dir: Path,
    fill_mode: str,
    mark_mode: str,
    cli_limits: Dict[str, int],
    copy_to_visualiser: Optional[Path],
    max_steps: Optional[int] = None,
    progress: bool = False,
    day_index: int = 0,
    day_count: int = 1,
    include_all_products: bool = False,
) -> Dict[str, object]:
    price_rows = load_price_rows(price_path)
    if max_steps is not None:
        allowed_times = sorted({row.timestamp for row in price_rows})[:max_steps]
        allowed = set(allowed_times)
        price_rows = [row for row in price_rows if row.timestamp in allowed]

    by_time = group_prices_by_time(price_rows)
    market_trades_by_time = load_market_trades(trade_path)
    products = sorted({row.product for row in price_rows})
    day = price_rows[0].day if price_rows else 0
    trader = import_trader(strategy_path)
    limits = infer_limits(trader, products, cli_limits)

    listings = {product: Listing(product, product, "XIRECS") for product in products}
    position = {product: 0 for product in products}
    cash = {product: 0.0 for product in products}
    trader_data = ""
    last_own_trades = {product: [] for product in products}

    activity_rows: List[Dict[str, object]] = []
    graph_points: List[Tuple[int, float]] = []
    lambda_logs: List[Dict[str, object]] = []
    all_history: List[Dict[str, object]] = []
    all_fills: List[Fill] = []
    active_products = set()
    quote_count = 0

    last_mark = {product: 0.0 for product in products}
    timestamps = sorted(by_time)
    total_timestamps = max(1, len(timestamps))
    progress_every = max(1, total_timestamps // 100)

    for step_idx, ts in enumerate(timestamps, start=1):
        state_timestamp = to_global_timestamp(day, ts)
        price_at_time = by_time[ts]
        order_depths = {product: build_order_depth(row) for product, row in price_at_time.items()}
        for product, row in price_at_time.items():
            last_mark[product] = book_mark(row, mark_mode)

        market_trades = clone_market_trades(market_trades_by_time.get(ts, {}), day=day)
        state = TradingState(
            traderData=trader_data,
            timestamp=state_timestamp,
            listings=listings,
            order_depths=order_depths,
            own_trades=last_own_trades,
            market_trades=market_trades,
            position=dict(position),
            observations=Observation(),
        )

        sandbox_log = ""
        lambda_log = ""
        strategy_result: Dict[str, List[Order]] = {}
        conversions = 0

        stdout_buffer = io.StringIO()
        try:
            with contextlib.redirect_stdout(stdout_buffer):
                raw_result = trader.run(state)
            if isinstance(raw_result, tuple):
                if len(raw_result) >= 1:
                    strategy_result = normalise_strategy_output(raw_result[0])
                if len(raw_result) >= 2:
                    conversions = raw_result[1]
                if len(raw_result) >= 3:
                    trader_data = raw_result[2] or ""
            else:
                strategy_result = normalise_strategy_output(raw_result)
        except Exception:
            sandbox_log = traceback.format_exc()
            strategy_result = {}
        lambda_log = stdout_buffer.getvalue().strip()

        timestamp_fills: List[Fill] = []
        passive_orders: List[Order] = []
        for product, orders in strategy_result.items():
            if orders:
                active_products.add(product)
            quote_count += len(orders)
            limit = limits.get(product, 1_000_000)
            current_position = position.get(product, 0)
            if not limit_check(current_position, orders, limit):
                sandbox_log += (
                    f"\nPosition limit breach for {product}: "
                    f"position={current_position}, limit={limit}, orders={orders}. "
                    "Orders cancelled."
                )
                continue
            if product not in order_depths:
                continue
            product_fills, product_passive = match_orders(
                state_timestamp,
                product,
                orders,
                order_depths[product],
                market_trades.get(product, []),
                fill_mode,
            )
            timestamp_fills.extend(product_fills)
            passive_orders.extend(product_passive)

        apply_fills(timestamp_fills, cash, position)
        for fill in timestamp_fills:
            active_products.add(fill.symbol)
        last_own_trades = fills_to_trades(timestamp_fills)
        all_fills.extend(timestamp_fills)

        for product_trades in market_trades.values():
            for trade in product_trades:
                all_history.append(trade_to_history_row(trade))
        for product_trades in last_own_trades.values():
            for trade in product_trades:
                all_history.append(trade_to_history_row(trade))

        total_pnl = 0.0
        product_pnl = {}
        for product in products:
            pnl = cash.get(product, 0.0) + position.get(product, 0) * last_mark.get(product, 0.0)
            product_pnl[product] = pnl
            total_pnl += pnl
        graph_points.append((state_timestamp, total_pnl))

        for product in products:
            row = price_at_time.get(product)
            if row is None:
                continue
            activity = dict(row.raw)
            activity["timestamp"] = state_timestamp
            activity["profit_and_loss"] = product_pnl.get(product, 0.0)
            activity_rows.append(activity)

        lambda_logs.append(
            {
                "sandboxLog": sandbox_log.strip(),
                "lambdaLog": lambda_log,
                "timestamp": state_timestamp,
            }
        )

        if progress and (step_idx == 1 or step_idx == total_timestamps or step_idx % progress_every == 0):
            day_fraction = step_idx / total_timestamps
            overall_fraction = (day_index + day_fraction) / max(1, day_count)
            percent = 100.0 * overall_fraction
            print(
                f"PROGRESS|{percent:.2f}|day {day} {step_idx:,}/{total_timestamps:,} timestamps",
                flush=True,
            )

    for product, qty in position.items():
        if qty != 0:
            active_products.add(product)
    strategy_product = getattr(trader, "PRODUCT", None)
    if isinstance(strategy_product, str) and strategy_product in products:
        active_products.add(strategy_product)

    emitted_products = set(products) if include_all_products else set(active_products)
    if not emitted_products:
        emitted_products = set(products)
    compact_activity_rows = [row for row in activity_rows if row.get("product") in emitted_products]

    activities_log = write_activities_log(compact_activity_rows)
    graph_log = write_graph_log(graph_points)
    profit = graph_points[-1][1] if graph_points else 0.0
    positions = [
        {"symbol": product, "quantity": qty}
        for product, qty in sorted(position.items())
        if qty != 0
    ]

    run_id = f"bt_{strategy_path.stem}_day_{day}_{uuid.uuid4().hex[:8]}"
    out_dir.mkdir(parents=True, exist_ok=True)
    archive_path = out_dir / f"{run_id}.zip"
    stats = calculate_stats(graph_points, all_fills, quote_count)

    run_json = {
        "round": "backtest",
        "status": "complete",
        "profit": profit,
        "activitiesLog": activities_log,
        "graphLog": graph_log,
        "positions": positions,
    }
    run_log = {
        "submissionId": run_id,
        "activitiesLog": activities_log,
        "graphLog": graph_log,
        "profit": profit,
        "positions": positions,
        "logs": lambda_logs,
        "tradeHistory": sorted(all_history, key=lambda x: (x["timestamp"], x["symbol"], x["price"])),
    }
    summary = {
        "run_id": run_id,
        "strategy": str(strategy_path),
        "price_file": str(price_path),
        "trade_file": str(trade_path),
        "fill_mode": fill_mode,
        "mark_mode": mark_mode,
        "profit": profit,
        "positions": positions,
        "stats": stats,
        "emitted_products": sorted(emitted_products),
        "notes": [
            "This is a replay backtest. It cannot perfectly model hidden bot flow after our orders.",
            "Active fills match visible historical book liquidity.",
            "Passive fills are approximated from historical public trades according to fill_mode.",
            "By default, activitiesLog is compacted to products the strategy touched. Use --all-products to emit every product.",
        ],
    }

    with zipfile.ZipFile(archive_path, "w", compression=zipfile.ZIP_DEFLATED) as z:
        z.writestr(f"{run_id}.json", json.dumps(run_json))
        z.writestr(f"{run_id}.log", json.dumps(run_log))
        z.writestr(f"{run_id}_summary.json", json.dumps(summary, indent=2))
        z.writestr(f"{strategy_path.name}", strategy_path.read_text(encoding="utf-8"))

    if copy_to_visualiser is not None:
        copy_to_visualiser.mkdir(parents=True, exist_ok=True)
        shutil.copy2(archive_path, copy_to_visualiser / archive_path.name)

    return {
        "run_id": run_id,
        "archive": str(archive_path),
        "visualiser_archive": str(copy_to_visualiser / archive_path.name) if copy_to_visualiser else "",
        "profit": profit,
        "stats": stats,
        "positions": positions,
    }


def discover_day_files(data_dir: Path) -> List[Tuple[int, Path, Path]]:
    found: List[Tuple[int, Path, Path]] = []
    for price_path in sorted(data_dir.glob("prices_round_*_day_*.csv")):
        stem = price_path.stem
        day_text = stem.rsplit("_day_", 1)[-1]
        if not day_text.lstrip("-").isdigit():
            continue
        day = int(day_text)
        trade_path = price_path.with_name(price_path.name.replace("prices_", "trades_"))
        found.append((day, price_path, trade_path))
    return found


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Replay Prosperity strategies over historical price/trade CSVs.")
    parser.add_argument("--strategy", required=True, type=Path, help="Path to a Python file defining Trader.")
    parser.add_argument("--data-dir", type=Path, default=DEFAULT_DATA_DIR, help="Folder containing prices_*.csv and trades_*.csv.")
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR, help="Folder for generated run archives.")
    parser.add_argument("--days", nargs="*", type=int, help="Historical days to run. Defaults to all discovered days.")
    parser.add_argument("--limits", type=Path, help="Optional JSON file of product position limits.")
    parser.add_argument(
        "--fill-mode",
        choices=["active", "passive-cross", "passive-touch"],
        default="passive-cross",
        help="How to approximate leftover passive order fills.",
    )
    parser.add_argument(
        "--mark-mode",
        choices=["mid", "wall-mid"],
        default="wall-mid",
        help="Mark inventory to mid or wall-mid for PnL.",
    )
    parser.add_argument(
        "--copy-to-visualiser",
        type=Path,
        help="Optional visualiser Run Information folder to copy generated archives into.",
    )
    parser.add_argument("--max-steps", type=int, help="Debug only: run the first N timestamps per day.")
    parser.add_argument("--progress", action="store_true", help="Emit machine-readable progress lines for the UI.")
    parser.add_argument(
        "--separate-days",
        action="store_true",
        help="Write one archive per historical day instead of one stitched archive.",
    )
    parser.add_argument(
        "--all-products",
        action="store_true",
        help="Emit every product into activitiesLog. Default emits only products the strategy touched.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    strategy_path = args.strategy.resolve()
    data_dir = args.data_dir.resolve()
    out_dir = args.out_dir.resolve()
    copy_to_visualiser = args.copy_to_visualiser.resolve() if args.copy_to_visualiser else None

    cli_limits = load_limits(args.limits.resolve() if args.limits else None)
    day_files = discover_day_files(data_dir)
    if args.days:
        wanted = set(args.days)
        day_files = [item for item in day_files if item[0] in wanted]
    if not day_files:
        raise SystemExit(f"No price files found in {data_dir}")

    out_dir.mkdir(parents=True, exist_ok=True)

    if args.separate_days:
        summaries = []
        day_out_dir = out_dir
        day_copy_to_visualiser = copy_to_visualiser
    else:
        summaries = []
        temp_context = tempfile.TemporaryDirectory(prefix="stitch_parts_", dir=str(out_dir))
        day_out_dir = Path(temp_context.name)
        day_copy_to_visualiser = None

    try:
        for day_index, (day, price_path, trade_path) in enumerate(day_files):
            print(f"Running day {day}: {price_path.name}", flush=True)
            summary = run_day(
                strategy_path=strategy_path,
                price_path=price_path,
                trade_path=trade_path,
                out_dir=day_out_dir,
                fill_mode=args.fill_mode,
                mark_mode=args.mark_mode,
                cli_limits=cli_limits,
                copy_to_visualiser=day_copy_to_visualiser,
                max_steps=args.max_steps,
                progress=args.progress,
                day_index=day_index,
                day_count=len(day_files),
                include_all_products=args.all_products,
            )
            summaries.append(summary)
            stats = summary["stats"]
            print(
                f"  {summary['run_id']} profit={summary['profit']:.2f} "
                f"sharpe={stats.get('sharpe', 0.0):.3f} "
                f"max_dd={stats.get('max_drawdown_abs', 0.0):.2f} "
                f"archive={summary['archive']}",
                flush=True,
            )

        if args.separate_days:
            output_summaries = summaries
        else:
            print("Stitching days into one visualiser archive...", flush=True)
            stitched = combine_day_archives(
                day_summaries=summaries,
                strategy_path=strategy_path,
                out_dir=out_dir,
                fill_mode=args.fill_mode,
                mark_mode=args.mark_mode,
                copy_to_visualiser=copy_to_visualiser,
            )
            output_summaries = [stitched]
            stats = stitched["stats"]
            print(
                f"  {stitched['run_id']} profit={stitched['profit']:.2f} "
                f"sharpe={stats.get('sharpe', 0.0):.3f} "
                f"max_dd={stats.get('max_drawdown_abs', 0.0):.2f} "
                f"archive={stitched['archive']}",
                flush=True,
            )
    finally:
        if not args.separate_days:
            temp_context.cleanup()

    summary_path = out_dir / f"summary_{uuid.uuid4().hex[:8]}.json"
    summary_path.write_text(json.dumps(output_summaries, indent=2), encoding="utf-8")
    print(f"Summary written to {summary_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
