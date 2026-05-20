from datamodel import Order, OrderDepth, TradingState
from typing import Dict, List, Optional, Tuple
import json
import math


class Trader:
    """Clean public version of the Round 1 dynamic strategy.

    The original live file contained more parameter sweeps and diagnostics. This
    version preserves the core logic: dynamic fair value, inventory-aware market
    making, volatility-aware sizing and regression-based drift detection.
    """

    OSMIUM = "ASH_COATED_OSMIUM"
    PEPPER = "INTARIAN_PEPPER_ROOT"
    POSITION_LIMITS = {OSMIUM: 80, PEPPER: 80}

    OSMIUM_STATIC_CENTER = 10000.0
    OSMIUM_HISTORY_LIMIT = 250
    OSMIUM_SHORT_WINDOW = 8
    OSMIUM_LONG_WINDOW = 40
    OSMIUM_BOOK_WEIGHT = 0.30
    OSMIUM_CENTER_PULL = 0.16
    OSMIUM_IMBALANCE_WEIGHT = 1.0
    OSMIUM_TAKE_EDGE = 0.25
    OSMIUM_INVENTORY_SKEW = 0.012
    OSMIUM_VOL_WINDOW = 20

    PEPPER_HISTORY_LIMIT = 220
    PEPPER_REGRESSION_WINDOW = 140
    PEPPER_MIN_POINTS = 30
    PEPPER_EXPECTED_SLOPE = 0.10
    PEPPER_STRONG_SLOPE_MIN = 0.085
    PEPPER_STRONG_SLOPE_MAX = 0.115
    PEPPER_STRONG_R2_MIN = 0.60
    PEPPER_MID_SLOPE_MIN = 0.03
    PEPPER_MID_R2_MIN = 0.35

    def run(self, state: TradingState):
        saved = self.load_state(state.traderData)
        result: Dict[str, List[Order]] = {}

        for product, depth in state.order_depths.items():
            if product not in self.POSITION_LIMITS:
                continue

            snap = self.snapshot(depth)
            if snap["mid"] is None:
                result[product] = []
                continue

            position = state.position.get(product, 0)

            if product == self.OSMIUM:
                self.remember(saved, "osmium_mid", snap["mid"], self.OSMIUM_HISTORY_LIMIT)
                orders = self.trade_osmium(saved, depth, snap, position)
            else:
                tick = int(round(state.timestamp / 100))
                saved.setdefault("pepper_history", []).append({"tick": tick, "mid": snap["mid"]})
                saved["pepper_history"] = saved["pepper_history"][-self.PEPPER_HISTORY_LIMIT:]
                fair, slope, r2, regime = self.pepper_fair_value(saved, tick)
                saved["last_pepper_regime"] = regime
                saved["last_pepper_slope"] = slope
                saved["last_pepper_r2"] = r2
                orders = self.trade_pepper(depth, snap, position, fair, regime)

            result[product] = self.merge_orders(orders)

        return result, 0, json.dumps(saved, separators=(",", ":"))

    def trade_osmium(self, saved: dict, depth: OrderDepth, snap: dict, position: int) -> List[Order]:
        fair = self.osmium_fair_value(saved, depth, snap)
        vol = self.recent_abs_change(saved.get("osmium_mid", []), self.OSMIUM_VOL_WINDOW)
        half_spread = 2 if vol > 2.0 else 1
        passive_size = 16 if vol > 2.0 else 24 if vol > 1.0 else 30

        inventory_penalty = max(0.0, (abs(position) - 20) / 60.0) * 0.60
        buy_edge = self.OSMIUM_TAKE_EDGE + (inventory_penalty if position > 0 else 0.0)
        sell_edge = self.OSMIUM_TAKE_EDGE + (inventory_penalty if position < 0 else 0.0)

        orders: List[Order] = []
        est_position = position

        for ask_price, ask_qty in snap["asks"]:
            if ask_price > fair - buy_edge:
                break
            qty = min(ask_qty, self.room_to_buy(self.OSMIUM, est_position))
            if qty <= 0:
                break
            orders.append(Order(self.OSMIUM, ask_price, qty))
            est_position += qty

        for bid_price, bid_qty in snap["bids"]:
            if bid_price < fair + sell_edge:
                break
            qty = min(bid_qty, self.room_to_sell(self.OSMIUM, est_position))
            if qty <= 0:
                break
            orders.append(Order(self.OSMIUM, bid_price, -qty))
            est_position -= qty

        skewed_fair = fair - self.clamp(est_position * self.OSMIUM_INVENTORY_SKEW, -1.0, 1.0)
        if est_position < 35:
            bid = min(int(math.floor(skewed_fair - half_spread)), snap["ask"] - 1)
            qty = min(passive_size, self.room_to_buy(self.OSMIUM, est_position))
            if qty > 0:
                orders.append(Order(self.OSMIUM, bid, qty))
        if est_position > -35:
            ask = max(int(math.ceil(skewed_fair + half_spread)), snap["bid"] + 1)
            qty = min(passive_size, self.room_to_sell(self.OSMIUM, est_position))
            if qty > 0:
                orders.append(Order(self.OSMIUM, ask, -qty))

        return orders

    def osmium_fair_value(self, saved: dict, depth: OrderDepth, snap: dict) -> float:
        history = saved.get("osmium_mid", [])
        if len(history) < 2:
            base = snap["mid"]
        else:
            short_mean = self.mean(history[-self.OSMIUM_SHORT_WINDOW:])
            long_mean = self.mean(history[-self.OSMIUM_LONG_WINDOW:])
            base = (1.0 - self.OSMIUM_BOOK_WEIGHT) * long_mean + self.OSMIUM_BOOK_WEIGHT * snap["mid"]
            if len(history) >= self.OSMIUM_LONG_WINDOW:
                sigma = self.std(history[-self.OSMIUM_LONG_WINDOW:])
                if sigma > 1e-9:
                    z = (short_mean - long_mean) / sigma
                    base -= 0.16 * z

        imbalance = self.orderbook_imbalance(depth, levels=5)
        base += self.clamp(imbalance * self.OSMIUM_IMBALANCE_WEIGHT, -2.0, 2.0)
        return (1.0 - self.OSMIUM_CENTER_PULL) * base + self.OSMIUM_CENTER_PULL * self.OSMIUM_STATIC_CENTER

    def trade_pepper(
        self,
        depth: OrderDepth,
        snap: dict,
        position: int,
        fair: float,
        regime: str,
    ) -> List[Order]:
        orders: List[Order] = []
        est_position = position
        core_target = {
            "very_strong_drift": 80,
            "strong_drift": 80,
            "mid_drift": 60,
            "flat": 40,
        }[regime]

        if snap["ask"] is not None and est_position < core_target:
            qty = min(core_target - est_position, snap["ask_qty"], self.room_to_buy(self.PEPPER, est_position))
            if qty > 0:
                orders.append(Order(self.PEPPER, snap["ask"], qty))
                est_position += qty

        if regime in {"very_strong_drift", "strong_drift"}:
            sell_edge = 6.0 if regime == "very_strong_drift" else 5.0
            buy_edge = 1.4 if regime == "very_strong_drift" else 1.8
        elif regime == "mid_drift":
            sell_edge = 2.8
            buy_edge = 1.4
        else:
            sell_edge = 1.2
            buy_edge = 1.2

        if snap["bid"] is not None and snap["bid"] - fair >= sell_edge and est_position > core_target:
            qty = min(4, snap["bid_qty"], self.room_to_sell(self.PEPPER, est_position), est_position - core_target)
            if qty > 0:
                orders.append(Order(self.PEPPER, snap["bid"], -qty))
                est_position -= qty

        if snap["ask"] is not None and fair - snap["ask"] >= buy_edge:
            qty = min(6, snap["ask_qty"], self.room_to_buy(self.PEPPER, est_position))
            if qty > 0:
                orders.append(Order(self.PEPPER, snap["ask"], qty))
                est_position += qty

        bid_offset, ask_offset = self.pepper_passive_offsets(regime)
        if snap["bid"] is not None and est_position < core_target:
            bid_price = max(snap["bid"] + 1, int(math.floor(fair - bid_offset)))
            if bid_price < snap["ask"]:
                qty = min(6, core_target - est_position, self.room_to_buy(self.PEPPER, est_position))
                if qty > 0:
                    orders.append(Order(self.PEPPER, bid_price, qty))
        if snap["ask"] is not None and est_position > core_target:
            ask_price = min(snap["ask"] - 1, int(math.ceil(fair + ask_offset)))
            if ask_price > snap["bid"]:
                qty = min(6, est_position - core_target, self.room_to_sell(self.PEPPER, est_position))
                if qty > 0:
                    orders.append(Order(self.PEPPER, ask_price, -qty))

        return orders

    def pepper_fair_value(self, saved: dict, current_tick: int) -> Tuple[float, float, float, str]:
        history = saved.get("pepper_history", [])[-self.PEPPER_REGRESSION_WINDOW:]
        xs = [float(row["tick"]) for row in history]
        ys = [float(row["mid"]) for row in history]

        if len(xs) < self.PEPPER_MIN_POINTS:
            intercept = self.mean([y - self.PEPPER_EXPECTED_SLOPE * x for x, y in zip(xs, ys)]) if xs else 0.0
            return intercept + self.PEPPER_EXPECTED_SLOPE * current_tick, self.PEPPER_EXPECTED_SLOPE, 0.0, "strong_drift"

        slope, intercept, r2 = self.linear_regression(xs, ys)
        fair = intercept + slope * current_tick

        if slope >= 0.115 and r2 >= self.PEPPER_MID_R2_MIN:
            return fair, slope, r2, "very_strong_drift"
        if self.PEPPER_STRONG_SLOPE_MIN <= slope <= self.PEPPER_STRONG_SLOPE_MAX and r2 >= self.PEPPER_STRONG_R2_MIN:
            return fair, slope, r2, "strong_drift"
        if slope >= self.PEPPER_MID_SLOPE_MIN and r2 >= self.PEPPER_MID_R2_MIN:
            return fair, slope, r2, "mid_drift"
        return self.mean(ys[-20:]), slope, r2, "flat"

    def pepper_passive_offsets(self, regime: str) -> Tuple[float, float]:
        if regime == "very_strong_drift":
            return 2.8, 7.0
        if regime == "strong_drift":
            return 2.2, 6.0
        if regime == "mid_drift":
            return 1.6, 3.0
        return 1.0, 1.0

    def snapshot(self, depth: OrderDepth) -> dict:
        bids = sorted(((int(price), int(qty)) for price, qty in depth.buy_orders.items() if qty > 0), reverse=True)
        asks = sorted((int(price), abs(int(qty))) for price, qty in depth.sell_orders.items() if qty < 0)
        bid = bids[0][0] if bids else None
        ask = asks[0][0] if asks else None
        return {
            "bids": bids,
            "asks": asks,
            "bid": bid,
            "ask": ask,
            "bid_qty": bids[0][1] if bids else 0,
            "ask_qty": asks[0][1] if asks else 0,
            "mid": (bid + ask) / 2.0 if bid is not None and ask is not None else None,
        }

    def orderbook_imbalance(self, depth: OrderDepth, levels: int) -> float:
        bids = sorted((qty for _, qty in depth.buy_orders.items() if qty > 0), reverse=True)[:levels]
        asks = sorted((abs(qty) for _, qty in depth.sell_orders.items() if qty < 0), reverse=True)[:levels]
        bid_volume = sum(bids)
        ask_volume = sum(asks)
        total = bid_volume + ask_volume
        return 0.0 if total <= 0 else (bid_volume - ask_volume) / total

    def load_state(self, trader_data: str) -> dict:
        if not trader_data:
            return {}
        try:
            data = json.loads(trader_data)
            return data if isinstance(data, dict) else {}
        except Exception:
            return {}

    def remember(self, saved: dict, key: str, value: float, limit: int) -> None:
        values = saved.setdefault(key, [])
        values.append(float(value))
        if len(values) > limit:
            del values[:-limit]

    def room_to_buy(self, product: str, position: int) -> int:
        return self.POSITION_LIMITS[product] - position

    def room_to_sell(self, product: str, position: int) -> int:
        return self.POSITION_LIMITS[product] + position

    def merge_orders(self, orders: List[Order]) -> List[Order]:
        merged: Dict[Tuple[str, int], int] = {}
        for order in orders:
            key = (order.symbol, int(order.price))
            merged[key] = merged.get(key, 0) + int(order.quantity)
        return [Order(symbol, price, qty) for (symbol, price), qty in merged.items() if qty != 0]

    def recent_abs_change(self, values: List[float], window: int) -> float:
        if len(values) < 2:
            return 0.0
        changes = [abs(values[i] - values[i - 1]) for i in range(1, len(values))]
        return self.mean(changes[-window:])

    def linear_regression(self, xs: List[float], ys: List[float]) -> Tuple[float, float, float]:
        x_mean = self.mean(xs)
        y_mean = self.mean(ys)
        denom = sum((x - x_mean) ** 2 for x in xs)
        if denom <= 1e-12:
            return self.PEPPER_EXPECTED_SLOPE, y_mean - self.PEPPER_EXPECTED_SLOPE * x_mean, 0.0
        slope = sum((x - x_mean) * (y - y_mean) for x, y in zip(xs, ys)) / denom
        intercept = y_mean - slope * x_mean
        ss_tot = sum((y - y_mean) ** 2 for y in ys)
        ss_res = sum((y - (intercept + slope * x)) ** 2 for x, y in zip(xs, ys))
        r2 = 1.0 - ss_res / ss_tot if ss_tot > 1e-12 else 1.0
        return slope, intercept, r2

    def mean(self, values: List[float]) -> float:
        return sum(values) / len(values) if values else 0.0

    def std(self, values: List[float]) -> float:
        if len(values) < 2:
            return 0.0
        mu = self.mean(values)
        return math.sqrt(sum((value - mu) ** 2 for value in values) / len(values))

    def clamp(self, value: float, low: float, high: float) -> float:
        return max(low, min(high, value))
