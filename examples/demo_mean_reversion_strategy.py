from __future__ import annotations

import json
from statistics import mean
from typing import Dict, List

from datamodel import Order, TradingState


class Trader:
    """Small review-friendly strategy for exercising the public backtester.

    This is not a competition submission. It is a compact example that shows
    the Trader interface, state persistence, order generation and fill/PnL
    handling on the synthetic sample data in this repository.
    """

    PRODUCT = "DEMO_PEARLS"
    POSITION_LIMIT = 20
    WINDOW = 5
    EDGE = 1.0
    ORDER_SIZE = 4

    def run(self, state: TradingState):
        product = self.PRODUCT
        depth = state.order_depths.get(product)
        if depth is None or not depth.buy_orders or not depth.sell_orders:
            return {}, 0, state.traderData

        best_bid = max(depth.buy_orders)
        best_ask = min(depth.sell_orders)
        mid = (best_bid + best_ask) / 2.0

        saved = self.load_state(state.traderData)
        history = saved.setdefault("mid_history", [])
        fair = mean(history[-self.WINDOW :]) if len(history) >= self.WINDOW else mid

        position = state.position.get(product, 0)
        orders: List[Order] = []

        if best_ask <= fair - self.EDGE and position < self.POSITION_LIMIT:
            buy_qty = min(self.ORDER_SIZE, self.POSITION_LIMIT - position)
            orders.append(Order(product, best_ask, buy_qty))

        if best_bid >= fair + self.EDGE and position > -self.POSITION_LIMIT:
            sell_qty = min(self.ORDER_SIZE, self.POSITION_LIMIT + position)
            orders.append(Order(product, best_bid, -sell_qty))

        history.append(mid)
        saved["mid_history"] = history[-50:]

        return {product: orders}, 0, json.dumps(saved, separators=(",", ":"))

    @staticmethod
    def load_state(trader_data: str) -> Dict[str, object]:
        if not trader_data:
            return {}
        try:
            parsed = json.loads(trader_data)
            return parsed if isinstance(parsed, dict) else {}
        except json.JSONDecodeError:
            return {}
