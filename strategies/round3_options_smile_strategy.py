from datamodel import Order, OrderDepth, TradingState
from typing import Dict, List, Optional, Tuple
import json
import math


class Trader:
    UNDERLYING = "VELVETFRUIT_EXTRACT"
    OPTIONS = {
        "VEV_4000": 4000,
        "VEV_4500": 4500,
        "VEV_5000": 5000,
        "VEV_5100": 5100,
        "VEV_5200": 5200,
        "VEV_5300": 5300,
        "VEV_5400": 5400,
        "VEV_5500": 5500,
        "VEV_6000": 6000,
        "VEV_6500": 6500,
    }
    PRODUCTS = [UNDERLYING] + list(OPTIONS)
    POSITION_LIMITS = {UNDERLYING: 200, **{product: 300 for product in OPTIONS}}

    ENABLE_ZERO_BID = True
    ENABLE_SMILE_PASSIVE = True
    ENABLE_SMILE_ACTIVE = False
    ENABLE_UNDERLYING_MR = False
    ENABLE_PASSIVE_MM = True
    ENABLE_DELTA_SKEW = True
    ENABLE_RESIDUAL_Z_FILTER = True
    ENABLE_DYNAMIC_SMILE_SIZE = True
    ENABLE_IV_CARRY = True
    ENABLE_DELTA_REBALANCE = False
    ENABLE_RESEARCH_LOGS = True
    ENABLE_PUBLIC_FLOW_LOGS = False
    ENABLE_DEAD_QUOTE_FILTER = True
    ENABLE_MICROSTRUCTURE_SCALP = True

    # Live Round 3 TTE is explicitly 5 days. Round 4/5 should become 4/3 days.
    # AUTO_TTE is useful for local research, where provided days map to 8/7/6.
    LIVE_TTE_DAYS = 5.0
    AUTO_TTE = False
    HISTORICAL_DAY0_TTE = 8.0
    DAY_TIMESTAMP_STRIDE = 1_000_000.0
    TTE_CANDIDATES = (5.0, 6.0, 7.0, 8.0)
    SMILE_PRODUCTS = ("VEV_5000", "VEV_5100", "VEV_5200", "VEV_5300", "VEV_5400", "VEV_5500")

    ZERO_BID_PRODUCTS = ("VEV_6000", "VEV_6500")
    ZERO_BID_SIZE = 40
    ZERO_BID_MAX_POS = 300
    ZERO_ASK_SIZE = 30

    # Structural market-making sleeves. These use only current book/fair-value
    # relationships, avoiding absolute price anchors.
    MM_CONFIG = {
        UNDERLYING: {
            "size": 12,
            "soft": 90,
            "hard": 160,
            "min_spread": 2,
            "min_edge": 1.0,
            "skew": 0.025,
            "fair": "wall_mid",
        },
        "VEV_4000": {
            "size": 14,
            "soft": 145,
            "hard": 240,
            "min_spread": 4,
            "min_edge": 2.0,
            "skew": 0.035,
            "fair": "parity",
        },
        "VEV_5300": {
            "enabled": False,
            "size": 4,
            "soft": 55,
            "hard": 95,
            "min_spread": 1,
            "min_edge": 0.4,
            "skew": 0.020,
            "fair": "book_mid",
        },
        "VEV_5400": {
            "enabled": False,
            "size": 5,
            "soft": 80,
            "hard": 125,
            "min_spread": 1,
            "min_edge": 0.4,
            "skew": 0.018,
            "fair": "book_mid",
        },
        "VEV_5500": {
            "enabled": False,
            "size": 5,
            "soft": 80,
            "hard": 125,
            "min_spread": 1,
            "min_edge": 0.4,
            "skew": 0.018,
            "fair": "book_mid",
        },
    }

    SCALP_PRODUCTS = ("VEV_5300", "VEV_5500")
    WATCH_PRODUCTS = ("VEV_5000", "VEV_5100", "VEV_5200", "VEV_5400")
    FILTERED_SMILE_TRADE_PRODUCTS = ()
    ACTIVE_PRODUCTS = ("VEV_5000", "VEV_5100", "VEV_5200", "VEV_5300", "VEV_5400", "VEV_5500")
    PASSIVE_BASE_SIZE = {
        "VEV_5000": 8,
        "VEV_5100": 10,
        "VEV_5200": 8,
        "VEV_5300": 10,
        "VEV_5400": 8,
        "VEV_5500": 14,
    }
    ACTIVE_BASE_SIZE = {
        "VEV_5000": 4,
        "VEV_5100": 4,
        "VEV_5200": 5,
        "VEV_5300": 4,
        "VEV_5400": 5,
        "VEV_5500": 6,
    }
    LONG_TARGET = {
        "VEV_5000": 40,
        "VEV_5100": 50,
        "VEV_5200": 40,
        "VEV_5300": 70,
        "VEV_5400": 45,
        "VEV_5500": 90,
    }
    SHORT_TARGET = {
        "VEV_5000": 20,
        "VEV_5100": 25,
        "VEV_5200": 35,
        "VEV_5300": 25,
        "VEV_5400": 35,
        "VEV_5500": 30,
    }
    MIN_MODEL_EDGE = {
        "VEV_5000": 5.0,
        "VEV_5100": 4.0,
        "VEV_5200": 3.2,
        "VEV_5300": 2.2,
        "VEV_5400": 2.0,
        "VEV_5500": 1.2,
    }
    ACTIVE_EDGE_MULT = 1.65
    EXIT_EDGE = {
        "VEV_5000": 1.5,
        "VEV_5100": 1.2,
        "VEV_5200": 0.8,
        "VEV_5300": 0.7,
        "VEV_5400": 0.5,
        "VEV_5500": 0.4,
    }

    UNDERLYING_EMA_ALPHA = 0.035
    UNDERLYING_ENTRY_DEV = 7.5
    UNDERLYING_EXIT_DEV = 1.5
    UNDERLYING_TARGET = 60
    UNDERLYING_MAX_TRADE = 15
    DELTA_SKEW_CAP = 250.0
    RESIDUAL_HISTORY_MIN = 12
    RESIDUAL_Z_ENTRY = 1.15
    RESIDUAL_Z_STRONG = 2.25
    IV_Z_ENTRY = 1.20
    DELTA_REBALANCE_THRESHOLD = 55.0
    DELTA_REBALANCE_URGENT = 140.0
    DELTA_REBALANCE_TARGET = 25.0
    DELTA_REBALANCE_MAX_TRADE = 12
    DELTA_HEDGE_FRACTION = 0.55

    HISTORY_LIMIT = 80
    MICRO_HISTORY_LIMIT = 12
    MICRO_PRODUCTS = ("VEV_5400", "VEV_5500")
    MICRO_CONFIG = {
        "VEV_5400": {
            "size": 4,
            "soft": 45,
            "hard": 80,
            "min_spread": 1,
            "min_signal": 0.62,
            "shift": 1.2,
            "min_edge": 0.4,
            "ret1_weight": -0.45,
            "ret5_weight": 0.00,
            "residual_weight": 0.35,
            "imbalance_weight": -0.35,
            "smile_guard": 0.8,
        },
        "VEV_5500": {
            "size": 5,
            "soft": 55,
            "hard": 90,
            "min_spread": 1,
            "min_signal": 0.60,
            "shift": 1.2,
            "min_edge": 0.4,
            "ret1_weight": -0.35,
            "ret5_weight": -0.25,
            "residual_weight": 0.30,
            "imbalance_weight": -0.30,
            "smile_guard": 0.8,
        },
    }

    def run(self, state: TradingState):
        saved = self.load_trader_data(state.traderData)
        result: Dict[str, List[Order]] = {}
        snapshots = self.build_snapshots(state.order_depths)
        orders_by_product: Dict[str, List[Tuple[Order, str, dict]]] = {product: [] for product in self.PRODUCTS}

        underlying = snapshots.get(self.UNDERLYING)
        spot = underlying["mid"] if underlying and underlying["mid"] is not None else None

        smile = self.fit_best_smile(snapshots, spot, state.timestamp)
        if smile is not None:
            self.annotate_smile_state(saved, snapshots, smile)

        if self.ENABLE_PUBLIC_FLOW_LOGS:
            self.log_public_flow(state, snapshots, smile)

        if self.ENABLE_PASSIVE_MM:
            self.trade_passive_market_making(state, snapshots, smile, orders_by_product)

        if self.ENABLE_MICROSTRUCTURE_SCALP:
            self.trade_microstructure_scalp(state, snapshots, saved, smile, orders_by_product)

        if smile is not None:
            if self.ENABLE_SMILE_PASSIVE or self.ENABLE_SMILE_ACTIVE:
                self.trade_smile_residuals(state, snapshots, smile, orders_by_product)
            if self.ENABLE_ZERO_BID:
                self.trade_zero_bid_lottery(state, snapshots, smile, orders_by_product)
            if self.ENABLE_IV_CARRY:
                self.trade_iv_carry(state, snapshots, smile, orders_by_product)

        if self.ENABLE_DELTA_REBALANCE and smile is not None:
            self.trade_delta_rebalance(state, snapshots, smile, orders_by_product)

        if self.ENABLE_UNDERLYING_MR:
            self.trade_underlying_mean_reversion(state, snapshots, saved, orders_by_product)

        flat_orders: Dict[str, List[Order]] = {}
        for product, detailed_orders in orders_by_product.items():
            if not detailed_orders:
                continue
            clipped_details = self.net_and_clip_detailed_orders(product, detailed_orders, state.position.get(product, 0))
            if clipped_details:
                flat_orders[product] = [item[0] for item in clipped_details]
                self.log_orders(state.timestamp, product, clipped_details, snapshots.get(product), smile)

        for product in self.PRODUCTS:
            result[product] = flat_orders.get(product, [])

        trader_data = self.make_trader_data(saved, snapshots, smile)
        return result, 0, trader_data

    def log_public_flow(self, state: TradingState, snapshots: Dict[str, dict], smile) -> None:
        if not self.ENABLE_RESEARCH_LOGS:
            return

        flow_rows = []
        spot = smile.get("spot") if smile is not None else None
        for product, trades in state.market_trades.items():
            if product not in self.PRODUCTS or not trades:
                continue
            snap = snapshots.get(product)
            if snap is None or snap.get("mid") is None:
                continue
            model = None
            if smile is not None:
                model = smile.get("loo_models", smile.get("models", {})).get(product)
            if model is None:
                model = snap.get("wall_mid") if snap.get("wall_mid") is not None else snap.get("mid")

            for trade in trades:
                side = self.classify_public_trade_side(trade, snap)
                strike = self.OPTIONS.get(product)
                is_otm = bool(strike is not None and spot is not None and strike > spot)
                edge_to_model = None
                if model is not None:
                    edge_to_model = model - trade.price if side == "BUY" else trade.price - model
                flow_rows.append({
                    "product": product,
                    "side": side,
                    "price": trade.price,
                    "qty": trade.quantity,
                    "qty_bucket": self.quantity_bucket(trade.quantity),
                    "buyer": trade.buyer,
                    "seller": trade.seller,
                    "bid": snap.get("bid"),
                    "ask": snap.get("ask"),
                    "mid": snap.get("mid"),
                    "wall_mid": snap.get("wall_mid"),
                    "model": model,
                    "edge_to_model": edge_to_model,
                    "strike": strike,
                    "is_otm": is_otm,
                    "flow_key": f"{product}:{side}:{'OTM' if is_otm else 'ITM_OR_UNDERLYING'}:{self.quantity_bucket(trade.quantity)}",
                    "residual_z": smile.get("residual_z", {}).get(product) if smile is not None else None,
                    "iv_z": smile.get("iv_z", {}).get(product) if smile is not None else None,
                })

        if not flow_rows:
            return

        payload = {
            "kind": "public_flow",
            "timestamp": state.timestamp,
            "markout_windows": [10, 50, 100],
            "trades": flow_rows,
        }
        print(json.dumps(payload, separators=(",", ":")))

    def classify_public_trade_side(self, trade, snap: dict) -> str:
        ask = snap.get("ask")
        bid = snap.get("bid")
        mid = snap.get("mid")
        if ask is not None and trade.price >= ask:
            return "BUY"
        if bid is not None and trade.price <= bid:
            return "SELL"
        if mid is not None and trade.price >= mid:
            return "BUY"
        return "SELL"

    def quantity_bucket(self, quantity: int) -> str:
        qty = abs(int(quantity))
        if qty <= 5:
            return "small"
        if qty <= 20:
            return "medium"
        return "large"

    def trade_microstructure_scalp(self, state, snapshots, saved, smile, orders_by_product) -> None:
        for product, config in self.MICRO_CONFIG.items():
            snap = snapshots.get(product)
            if snap is None or snap["bid"] is None or snap["ask"] is None or snap["mid"] is None:
                continue
            spread = snap["ask"] - snap["bid"]
            if spread < config["min_spread"]:
                continue

            signal, features = self.micro_signal(product, snap, saved, config)
            if signal is None or abs(signal) < config["min_signal"]:
                continue

            position = state.position.get(product, 0)
            hard = int(config["hard"])
            soft = int(config["soft"])
            base_size = int(config["size"])
            shift = float(config["shift"])
            min_edge = float(config["min_edge"])
            model = snap["wall_mid"] if snap["wall_mid"] is not None else snap["mid"]
            micro_model = model + signal * shift
            smile_model = None
            if smile is not None:
                smile_model = smile.get("loo_models", smile.get("models", {})).get(product)

            signal_strength = min(1.0, abs(signal))
            extra_size = 1 + int(signal_strength >= 0.70)
            if signal > 0:
                if not self.micro_smile_guard_allows(product, True, snap, smile_model, config):
                    continue
                qty = self.inventory_scaled_size(base_size + extra_size, position, soft, hard, is_buy=True)
                qty = min(qty, hard - position)
                price = self.passive_bid_price(snap, micro_model, min_edge)
                if qty > 0 and price is not None:
                    meta = self.quote_meta(product, "micro_pca_buy", price, qty, snap, micro_model, smile, {
                        "micro_signal": signal,
                        "micro_model": micro_model,
                        "micro_ret1": features["ret1"],
                        "micro_ret5": features["ret5"],
                        "micro_residual": features["residual"],
                        "micro_imbalance": features["imbalance"],
                        "smile_model": smile_model,
                    })
                    orders_by_product[product].append((Order(product, price, qty), "micro_pca_buy", meta))
            else:
                if not self.micro_smile_guard_allows(product, False, snap, smile_model, config):
                    continue
                qty = self.inventory_scaled_size(base_size + extra_size, position, soft, hard, is_buy=False)
                qty = min(qty, hard + position)
                price = self.passive_ask_price(snap, micro_model, min_edge)
                if qty > 0 and price is not None:
                    meta = self.quote_meta(product, "micro_pca_sell", price, -qty, snap, micro_model, smile, {
                        "micro_signal": signal,
                        "micro_model": micro_model,
                        "micro_ret1": features["ret1"],
                        "micro_ret5": features["ret5"],
                        "micro_residual": features["residual"],
                        "micro_imbalance": features["imbalance"],
                        "smile_model": smile_model,
                    })
                    orders_by_product[product].append((Order(product, price, -qty), "micro_pca_sell", meta))

    def micro_signal(self, product: str, snap: dict, saved: dict, config: dict):
        wall_mid = snap["wall_mid"] if snap["wall_mid"] is not None else snap["mid"]
        if wall_mid is None:
            return None, {}
        spread = max(1.0, snap["ask"] - snap["bid"])
        history = saved.get(f"micro_wall_{product}", [])
        ret1 = 0.0
        ret5 = 0.0
        if history:
            ret1 = wall_mid - float(history[-1])
            lookback = min(5, len(history))
            ret5 = wall_mid - float(history[-lookback])

        residual = 0.0
        if snap["mid"] is not None and snap["wall_mid"] is not None:
            residual = snap["mid"] - snap["wall_mid"]
        imbalance = self.top_depth_imbalance(snap)

        normalized_ret1 = self.clamp(ret1 / spread, -1.0, 1.0)
        normalized_ret5 = self.clamp(ret5 / max(1.0, spread * 3.0), -1.0, 1.0)
        normalized_residual = self.clamp(residual / spread, -1.0, 1.0)
        normalized_imbalance = self.clamp(imbalance, -1.0, 1.0)

        signal = (
            float(config["ret1_weight"]) * normalized_ret1
            + float(config["ret5_weight"]) * normalized_ret5
            + float(config["residual_weight"]) * normalized_residual
            + float(config["imbalance_weight"]) * normalized_imbalance
        )
        return self.clamp(signal, -1.0, 1.0), {
            "ret1": ret1,
            "ret5": ret5,
            "residual": residual,
            "imbalance": imbalance,
        }

    def top_depth_imbalance(self, snap: dict) -> float:
        if not snap.get("bids") or not snap.get("asks"):
            return 0.0
        bid_qty = float(snap["bids"][0][1])
        ask_qty = float(snap["asks"][0][1])
        denom = bid_qty + ask_qty
        if denom <= 0:
            return 0.0
        return (bid_qty - ask_qty) / denom

    def micro_smile_guard_allows(self, product: str, is_buy: bool, snap: dict, smile_model, config: dict) -> bool:
        guard = float(config.get("smile_guard", 0.0))
        if guard <= 0 or smile_model is None:
            return True
        if is_buy:
            return snap["bid"] <= smile_model + guard
        return snap["ask"] >= smile_model - guard

    def clamp(self, value: float, low: float, high: float) -> float:
        return max(low, min(high, value))

    def trade_passive_market_making(self, state, snapshots, smile, orders_by_product) -> None:
        for product, config in self.MM_CONFIG.items():
            if config.get("enabled") is False:
                continue
            snap = snapshots.get(product)
            if snap is None or snap["bid"] is None or snap["ask"] is None or snap["mid"] is None:
                continue
            spread = snap["ask"] - snap["bid"]
            if spread < config["min_spread"]:
                continue

            fair = self.market_making_fair(product, snap, snapshots, smile, config)
            if fair is None:
                continue

            position = state.position.get(product, 0)
            hard = int(config["hard"])
            soft = int(config["soft"])
            base_size = int(config["size"])
            skew = float(config["skew"])
            min_edge = float(config["min_edge"])

            skew_position = self.inventory_skew_position(product, position, state, smile)
            skewed_fair = fair - skew_position * skew
            bid_qty = self.inventory_scaled_size(base_size, position, soft, hard, is_buy=True)
            ask_qty = self.inventory_scaled_size(base_size, position, soft, hard, is_buy=False)
            bid_price = self.market_making_bid_price(snap, skewed_fair, min_edge)
            ask_price = self.market_making_ask_price(snap, skewed_fair, min_edge)

            if bid_qty > 0 and position < hard and bid_price is not None:
                orders_by_product[product].append((
                    Order(product, bid_price, min(bid_qty, hard - position)),
                    "passive_mm_bid",
                    self.quote_meta(product, "passive_mm_bid", bid_price, min(bid_qty, hard - position), snap, fair, smile, {"delta_exposure": skew_position}),
                ))
            if ask_qty > 0 and position > -hard and ask_price is not None:
                orders_by_product[product].append((
                    Order(product, ask_price, -min(ask_qty, hard + position)),
                    "passive_mm_ask",
                    self.quote_meta(product, "passive_mm_ask", ask_price, -min(ask_qty, hard + position), snap, fair, smile, {"delta_exposure": skew_position}),
                ))

    def inventory_skew_position(self, product: str, position: int, state, smile) -> float:
        if product != self.UNDERLYING or not self.ENABLE_DELTA_SKEW or smile is None:
            return float(position)

        exposure = float(state.position.get(self.UNDERLYING, 0))
        deltas = smile.get("deltas", {})
        for option in self.OPTIONS:
            exposure += state.position.get(option, 0) * deltas.get(option, 0.0)
        return max(-self.DELTA_SKEW_CAP, min(self.DELTA_SKEW_CAP, exposure))

    def market_making_fair(self, product: str, snap: dict, snapshots: Dict[str, dict], smile, config: dict) -> Optional[float]:
        source = config.get("fair")
        if source == "wall_mid":
            return snap.get("wall_mid") if snap.get("wall_mid") is not None else snap["mid"]
        if source == "parity":
            underlying = snapshots.get(self.UNDERLYING)
            if underlying is None or underlying.get("mid") is None:
                return snap["mid"]
            strike = self.OPTIONS.get(product)
            if strike is None:
                return snap["mid"]
            parity = max(underlying["mid"] - strike, 0.0)
            if snap["mid"] is None:
                return parity
            return 0.65 * parity + 0.35 * snap["mid"]
        if source == "smile" and smile is not None:
            return smile.get("loo_models", smile.get("models", {})).get(product, snap["mid"])
        return snap["mid"]

    def inventory_scaled_size(self, base_size: int, position: int, soft: int, hard: int, is_buy: bool) -> int:
        if is_buy:
            if position >= hard:
                return 0
            if position >= soft:
                return max(1, base_size // 3)
            if position <= -soft:
                return base_size + max(1, base_size // 2)
            return base_size

        if position <= -hard:
            return 0
        if position <= -soft:
            return max(1, base_size // 3)
        if position >= soft:
            return base_size + max(1, base_size // 2)
        return base_size

    def market_making_bid_price(self, snap, fair: float, min_edge: float) -> Optional[int]:
        bid = int(snap["bid"])
        ask = int(snap["ask"])
        price = bid
        improved = bid + 1
        if improved < ask and fair - improved >= min_edge:
            price = improved
        if price < ask and fair - price >= min_edge:
            return max(0, price)
        return None

    def market_making_ask_price(self, snap, fair: float, min_edge: float) -> Optional[int]:
        bid = int(snap["bid"])
        ask = int(snap["ask"])
        price = ask
        improved = ask - 1
        if improved > bid and improved - fair >= min_edge:
            price = improved
        if price > bid and price - fair >= min_edge:
            return max(1, price)
        return None

    def quote_meta(self, product: str, reason: str, price: int, quantity: int, snap: dict, model: Optional[float], smile, extra: Optional[dict] = None) -> dict:
        side = "BUY" if quantity > 0 else "SELL"
        fair = model if model is not None else snap.get("mid")
        edge_to_model = None
        if fair is not None:
            edge_to_model = fair - price if side == "BUY" else price - fair

        strike = self.OPTIONS.get(product)
        spot = None
        if smile is not None:
            spot = smile.get("spot")
        moneyness = None
        is_otm = None
        if strike is not None and spot is not None and spot > 0:
            is_otm = strike > spot
            try:
                moneyness = math.log(strike / spot) / math.sqrt(max(smile.get("t", 0.0), 1e-9))
            except Exception:
                moneyness = None

        abs_qty = abs(quantity)
        if product == "VEV_4000":
            size_bucket = "small" if abs_qty <= 8 else "medium" if abs_qty <= 14 else "large"
        else:
            size_bucket = "small" if abs_qty <= 5 else "medium" if abs_qty <= 12 else "large"

        meta = {
            "reason": reason,
            "side": side,
            "quote_price": int(price),
            "quote_qty": int(abs_qty),
            "size_bucket": size_bucket,
            "model": fair,
            "edge_to_model": edge_to_model,
            "residual": snap.get("mid") - fair if fair is not None and snap.get("mid") is not None else None,
            "spread": snap.get("spread"),
            "bid": snap.get("bid"),
            "ask": snap.get("ask"),
            "mid": snap.get("mid"),
            "wall_mid": snap.get("wall_mid"),
            "strike": strike,
            "is_otm": is_otm,
            "moneyness": moneyness,
        }
        if smile is not None:
            meta.update({
                "tte": smile.get("tte"),
                "smile_score": smile.get("score"),
                "residual_z": smile.get("residual_z", {}).get(product),
                "iv": smile.get("ivs", {}).get(product),
                "fair_iv": smile.get("fair_ivs", {}).get(product),
                "iv_z": smile.get("iv_z", {}).get(product),
                "delta": smile.get("deltas", {}).get(product),
                "vega": smile.get("vegas", {}).get(product),
                "gamma": smile.get("gammas", {}).get(product),
                "theta": smile.get("thetas", {}).get(product),
            })
        if extra:
            meta.update(extra)
        return meta

    def trade_smile_residuals(self, state, snapshots, smile, orders_by_product) -> None:
        if self.ENABLE_DEAD_QUOTE_FILTER:
            products = self.FILTERED_SMILE_TRADE_PRODUCTS
        else:
            products = self.WATCH_PRODUCTS + self.SCALP_PRODUCTS

        for product in products:
            snap = snapshots.get(product)
            model = smile.get("loo_models", smile["models"]).get(product)
            if snap is None or model is None:
                continue
            if snap["bid"] is None or snap["ask"] is None or snap["mid"] is None:
                continue

            position = state.position.get(product, 0)
            spread = max(1.0, snap["ask"] - snap["bid"])
            edge = self.MIN_MODEL_EDGE.get(product, 2.0)
            residual = snap["mid"] - model
            long_cap = self.LONG_TARGET.get(product, 60)
            short_cap = self.SHORT_TARGET.get(product, 0)
            residual_z = smile.get("residual_z", {}).get(product)
            delta = smile.get("deltas", {}).get(product, 0.0)
            vega = smile.get("vegas", {}).get(product, 0.0)
            gamma = smile.get("gammas", {}).get(product, 0.0)
            theta = smile.get("thetas", {}).get(product, 0.0)
            buy_edge = model - snap["ask"]
            sell_edge = snap["bid"] - model
            buy_signal = self.signal_allows_buy(residual_z, buy_edge, edge)
            sell_signal = self.signal_allows_sell(residual_z, sell_edge, edge)

            active_edge = max(edge * self.ACTIVE_EDGE_MULT, spread + 0.5)
            if self.ENABLE_SMILE_ACTIVE and product in self.ACTIVE_PRODUCTS and buy_edge >= active_edge and position < long_cap and buy_signal:
                qty = self.dynamic_smile_size(product, self.ACTIVE_BASE_SIZE.get(product, 5), long_cap - position, residual_z, buy_edge, spread)
                order = Order(product, int(snap["ask"]), qty)
                orders_by_product[product].append((order, "smile_take_buy", self.quote_meta(product, "smile_take_buy", int(snap["ask"]), qty, snap, model, smile)))
                continue

            if self.ENABLE_SMILE_ACTIVE and product in self.ACTIVE_PRODUCTS and sell_edge >= active_edge and position > -short_cap and sell_signal:
                qty = self.dynamic_smile_size(product, self.ACTIVE_BASE_SIZE.get(product, 5), position + short_cap, residual_z, sell_edge, spread)
                order = Order(product, int(snap["bid"]), -qty)
                orders_by_product[product].append((order, "smile_take_sell", self.quote_meta(product, "smile_take_sell", int(snap["bid"]), -qty, snap, model, smile)))
                continue

            exit_edge = self.EXIT_EDGE.get(product, 0.5)
            if position > 0 and residual >= -exit_edge:
                qty = min(abs(position), self.PASSIVE_BASE_SIZE.get(product, 10))
                price = self.passive_ask_price(snap, model, min_edge=0.0)
                if qty > 0 and price is not None:
                    orders_by_product[product].append((Order(product, price, -qty), "smile_exit_long", self.quote_meta(product, "smile_exit_long", price, -qty, snap, model, smile)))
                continue

            if position < 0 and residual <= exit_edge:
                qty = min(abs(position), self.PASSIVE_BASE_SIZE.get(product, 10))
                price = self.passive_bid_price(snap, model, min_edge=0.0)
                if qty > 0 and price is not None:
                    orders_by_product[product].append((Order(product, price, qty), "smile_exit_short", self.quote_meta(product, "smile_exit_short", price, qty, snap, model, smile)))
                continue

            if self.ENABLE_SMILE_PASSIVE and model - snap["bid"] >= edge and position < long_cap and buy_signal:
                qty = self.dynamic_smile_size(product, self.PASSIVE_BASE_SIZE.get(product, 10), long_cap - position, residual_z, model - snap["bid"], spread)
                price = self.passive_bid_price(snap, model, edge)
                if qty > 0 and price is not None:
                    orders_by_product[product].append((Order(product, price, qty), "smile_passive_buy", self.quote_meta(product, "smile_passive_buy", price, qty, snap, model, smile)))

            if self.ENABLE_SMILE_PASSIVE and short_cap > 0 and snap["ask"] - model >= edge and position > -short_cap and sell_signal:
                qty = self.dynamic_smile_size(product, self.PASSIVE_BASE_SIZE.get(product, 10), position + short_cap, residual_z, snap["ask"] - model, spread)
                price = self.passive_ask_price(snap, model, edge)
                if qty > 0 and price is not None:
                    orders_by_product[product].append((Order(product, price, -qty), "smile_passive_sell", self.quote_meta(product, "smile_passive_sell", price, -qty, snap, model, smile)))

    def signal_allows_buy(self, residual_z: Optional[float], edge_to_model: float, min_edge: float) -> bool:
        if not self.ENABLE_RESIDUAL_Z_FILTER or residual_z is None:
            return True
        if residual_z <= -self.RESIDUAL_Z_ENTRY:
            return True
        return edge_to_model >= min_edge * 2.4

    def signal_allows_sell(self, residual_z: Optional[float], edge_to_model: float, min_edge: float) -> bool:
        if not self.ENABLE_RESIDUAL_Z_FILTER or residual_z is None:
            return True
        if residual_z >= self.RESIDUAL_Z_ENTRY:
            return True
        return edge_to_model >= min_edge * 2.4

    def dynamic_smile_size(self, product: str, base_size: int, remaining_capacity: int, residual_z: Optional[float], edge_to_model: float, spread: float) -> int:
        if remaining_capacity <= 0:
            return 0
        if not self.ENABLE_DYNAMIC_SMILE_SIZE:
            return min(base_size, remaining_capacity)

        multiplier = 1.0
        if residual_z is not None:
            abs_z = abs(residual_z)
            if abs_z >= self.RESIDUAL_Z_STRONG:
                multiplier += 1.0
            elif abs_z >= self.RESIDUAL_Z_ENTRY:
                multiplier += 0.5

        edge_ratio = edge_to_model / max(1.0, spread)
        if edge_ratio >= 3.0:
            multiplier += 0.75
        elif edge_ratio >= 2.0:
            multiplier += 0.4

        # Keep experimental bursts bounded; we want to test stronger conviction
        # without letting one noisy smile point consume the entire option limit.
        cap = max(base_size, int(base_size * 2.75))
        return max(1, min(int(round(base_size * multiplier)), cap, remaining_capacity))

    def trade_zero_bid_lottery(self, state, snapshots, smile, orders_by_product) -> None:
        for product in self.ZERO_BID_PRODUCTS:
            snap = snapshots.get(product)
            if snap is None or snap["ask"] is None:
                continue
            position = state.position.get(product, 0)
            model = smile["models"].get(product)

            if position < self.ZERO_BID_MAX_POS and snap["ask"] >= 1:
                qty = min(self.ZERO_BID_SIZE, self.ZERO_BID_MAX_POS - position)
                if qty > 0:
                    orders_by_product[product].append((Order(product, 0, qty), "zero_bid_lottery", self.quote_meta(product, "zero_bid_lottery", 0, qty, snap, model, smile)))

            if position > 0 and snap["ask"] is not None:
                ask_price = max(1, int(snap["ask"]))
                qty = min(position, self.ZERO_ASK_SIZE)
                if qty > 0:
                    orders_by_product[product].append((Order(product, ask_price, -qty), "zero_bid_take_profit", self.quote_meta(product, "zero_bid_take_profit", ask_price, -qty, snap, model, smile)))

    def trade_iv_carry(self, state, snapshots, smile, orders_by_product) -> None:
        iv_zs = smile.get("iv_z", {})
        fair_ivs = smile.get("fair_ivs", {})
        market_ivs = smile.get("ivs", {})
        for product in self.SMILE_PRODUCTS:
            snap = snapshots.get(product)
            model = smile.get("loo_models", smile["models"]).get(product)
            iv_z = iv_zs.get(product)
            if snap is None or model is None or iv_z is None:
                continue
            if snap["bid"] is None or snap["ask"] is None or snap["mid"] is None:
                continue

            position = state.position.get(product, 0)
            spread = max(1.0, snap["ask"] - snap["bid"])
            min_edge = max(self.MIN_MODEL_EDGE.get(product, 2.0), spread * 0.7)
            residual = snap["mid"] - model
            delta = smile.get("deltas", {}).get(product, 0.0)
            vega = smile.get("vegas", {}).get(product, 0.0)
            gamma = smile.get("gammas", {}).get(product, 0.0)
            theta = smile.get("thetas", {}).get(product, 0.0)
            meta = {
                "model": model,
                "residual": residual,
                "residual_z": smile.get("residual_z", {}).get(product),
                "iv": market_ivs.get(product),
                "fair_iv": fair_ivs.get(product),
                "iv_z": iv_z,
                "tte": smile["tte"],
                "delta": delta,
                "vega": vega,
                "gamma": gamma,
                "theta": theta,
            }

            if iv_z <= -self.IV_Z_ENTRY and model - snap["bid"] >= min_edge:
                long_cap = self.LONG_TARGET.get(product, 50)
                if position < long_cap:
                    qty = min(4, long_cap - position)
                    price = self.passive_bid_price(snap, model, min_edge)
                    if qty > 0 and price is not None:
                        orders_by_product[product].append((Order(product, price, qty), "iv_carry_buy", meta))

            if iv_z >= self.IV_Z_ENTRY and snap["ask"] - model >= min_edge:
                short_cap = self.SHORT_TARGET.get(product, 0)
                if short_cap > 0 and position > -short_cap:
                    qty = min(4, position + short_cap)
                    price = self.passive_ask_price(snap, model, min_edge)
                    if qty > 0 and price is not None:
                        orders_by_product[product].append((Order(product, price, -qty), "iv_carry_sell", meta))

    def trade_delta_rebalance(self, state, snapshots, smile, orders_by_product) -> None:
        snap = snapshots.get(self.UNDERLYING)
        if snap is None or snap["bid"] is None or snap["ask"] is None or snap["mid"] is None:
            return

        greeks = self.portfolio_greeks(state, smile)
        exposure = greeks["delta"]
        if abs(exposure) <= self.DELTA_REBALANCE_THRESHOLD:
            return

        underlying_position = state.position.get(self.UNDERLYING, 0)
        target_delta = math.copysign(self.DELTA_REBALANCE_TARGET, exposure)
        desired_position = underlying_position + int(round((target_delta - exposure) * self.DELTA_HEDGE_FRACTION))
        limit = self.POSITION_LIMITS[self.UNDERLYING]
        desired_position = max(-limit, min(limit, desired_position))
        diff = desired_position - underlying_position
        if diff == 0:
            return

        qty = min(abs(diff), self.DELTA_REBALANCE_MAX_TRADE)
        fair = snap.get("wall_mid") if snap.get("wall_mid") is not None else snap["mid"]
        spread = snap["ask"] - snap["bid"]
        urgent = abs(exposure) >= self.DELTA_REBALANCE_URGENT and spread <= 2
        meta = {
            "model": fair,
            "residual": snap["mid"] - fair,
            "delta_exposure": exposure,
            "portfolio_delta": greeks["delta"],
            "portfolio_gamma": greeks["gamma"],
            "portfolio_vega": greeks["vega"],
            "portfolio_theta": greeks["theta"],
        }

        if diff > 0:
            price = int(snap["ask"]) if urgent else int(snap["bid"])
            if price < snap["ask"] or urgent:
                orders_by_product[self.UNDERLYING].append((Order(self.UNDERLYING, price, qty), "delta_rebalance_buy", meta))
        else:
            price = int(snap["bid"]) if urgent else int(snap["ask"])
            if price > snap["bid"] or urgent:
                orders_by_product[self.UNDERLYING].append((Order(self.UNDERLYING, price, -qty), "delta_rebalance_sell", meta))

    def trade_underlying_mean_reversion(self, state, snapshots, saved, orders_by_product) -> None:
        snap = snapshots.get(self.UNDERLYING)
        if snap is None or snap["mid"] is None or snap["bid"] is None or snap["ask"] is None:
            return

        mid = snap["mid"]
        previous = saved.get("velvet_ema")
        ema = mid if previous is None else self.UNDERLYING_EMA_ALPHA * mid + (1.0 - self.UNDERLYING_EMA_ALPHA) * float(previous)
        saved["velvet_ema_next"] = ema
        dev = mid - ema
        position = state.position.get(self.UNDERLYING, 0)

        target = position
        reason = None
        if dev <= -self.UNDERLYING_ENTRY_DEV:
            target = self.UNDERLYING_TARGET
            reason = "underlying_mr_buy"
        elif dev >= self.UNDERLYING_ENTRY_DEV:
            target = -self.UNDERLYING_TARGET
            reason = "underlying_mr_sell"
        elif abs(dev) <= self.UNDERLYING_EXIT_DEV:
            target = 0
            reason = "underlying_mr_exit"

        diff = target - position
        if diff > 0:
            qty = min(diff, self.UNDERLYING_MAX_TRADE, self.POSITION_LIMITS[self.UNDERLYING] - position)
            if qty > 0:
                orders_by_product[self.UNDERLYING].append((Order(self.UNDERLYING, int(snap["ask"]), qty), reason or "underlying_mr_buy", {"ema": ema, "dev": dev}))
        elif diff < 0:
            qty = min(-diff, self.UNDERLYING_MAX_TRADE, self.POSITION_LIMITS[self.UNDERLYING] + position)
            if qty > 0:
                orders_by_product[self.UNDERLYING].append((Order(self.UNDERLYING, int(snap["bid"]), -qty), reason or "underlying_mr_sell", {"ema": ema, "dev": dev}))

    def fit_best_smile(self, snapshots, spot, timestamp: int):
        if spot is None or spot <= 0:
            return None

        best = None
        candidates, tte_source = self.get_tte_candidates(timestamp)
        for tte_days in candidates:
            t = tte_days / 365.0
            points = []
            all_ivs = {}
            for product in self.SMILE_PRODUCTS:
                snap = snapshots.get(product)
                if snap is None or snap["mid"] is None or snap["spread"] is None:
                    continue
                strike = self.OPTIONS[product]
                intrinsic = max(spot - strike, 0.0)
                extrinsic = snap["mid"] - intrinsic
                if extrinsic < 0.5:
                    continue
                iv = self.implied_vol(snap["mid"], spot, strike, t)
                if iv is None:
                    continue
                moneyness = math.log(strike / spot) / math.sqrt(t)
                vega = self.bs_vega(spot, strike, t, iv)
                weight = max(1.0, math.sqrt(max(vega, 0.0)))
                points.append((moneyness, iv, weight, product))
                all_ivs[product] = iv

            if len(points) < 4:
                continue

            coef = self.weighted_quadratic_fit(points)
            if coef is None:
                continue

            models = {}
            deltas = {}
            vegas = {}
            gammas = {}
            thetas = {}
            fair_ivs = {}
            score = 0.0
            count = 0
            for product in self.OPTIONS:
                snap = snapshots.get(product)
                if snap is None or snap["mid"] is None:
                    continue
                strike = self.OPTIONS[product]
                moneyness = math.log(strike / spot) / math.sqrt(t)
                fair_iv = max(0.0001, self.eval_quadratic(coef, moneyness))
                model = self.bs_call_price(spot, strike, t, fair_iv)
                models[product] = model
                fair_ivs[product] = fair_iv
                deltas[product] = self.bs_delta(spot, strike, t, fair_iv)
                vegas[product] = self.bs_vega(spot, strike, t, fair_iv)
                gammas[product] = self.bs_gamma(spot, strike, t, fair_iv)
                thetas[product] = self.bs_theta_per_day(spot, strike, t, fair_iv)
                if product in self.SMILE_PRODUCTS and snap["spread"] is not None:
                    denom = max(1.0, snap["spread"])
                    score += ((snap["mid"] - model) / denom) ** 2
                    count += 1

            if count == 0:
                continue
            loo_models = self.build_leave_one_out_models(points, snapshots, spot, t)
            score /= count
            candidate = {
                "tte": tte_days,
                "tte_source": tte_source,
                "t": t,
                "spot": spot,
                "coef": coef,
                "models": models,
                "loo_models": loo_models,
                "deltas": deltas,
                "vegas": vegas,
                "gammas": gammas,
                "thetas": thetas,
                "fair_ivs": fair_ivs,
                "score": score,
                "ivs": all_ivs,
            }
            if best is None or candidate["score"] < best["score"]:
                best = candidate

        return best

    def annotate_smile_state(self, saved: dict, snapshots: Dict[str, dict], smile: dict) -> None:
        residual_z = {}
        residual_mean = {}
        residual_std = {}
        iv_z = {}
        iv_mean = {}
        iv_std = {}
        iv_residuals = {}

        models = smile.get("loo_models", smile.get("models", {}))
        for product in self.SMILE_PRODUCTS:
            snap = snapshots.get(product)
            model = models.get(product)
            if snap is None or model is None or snap.get("mid") is None:
                continue

            residual = snap["mid"] - model
            z, mean, std = self.history_zscore(saved.get(f"resid_{product}", []), residual)
            if z is not None:
                residual_z[product] = z
                residual_mean[product] = mean
                residual_std[product] = std

            market_iv = smile.get("ivs", {}).get(product)
            fair_iv = smile.get("fair_ivs", {}).get(product)
            if market_iv is not None and fair_iv is not None:
                iv_residual = market_iv - fair_iv
                iv_residuals[product] = iv_residual
                z, mean, std = self.history_zscore(saved.get(f"iv_resid_{product}", []), iv_residual)
                if z is not None:
                    iv_z[product] = z
                    iv_mean[product] = mean
                    iv_std[product] = std

        smile["residual_z"] = residual_z
        smile["residual_mean"] = residual_mean
        smile["residual_std"] = residual_std
        smile["iv_z"] = iv_z
        smile["iv_mean"] = iv_mean
        smile["iv_std"] = iv_std
        smile["iv_residuals"] = iv_residuals

    def history_zscore(self, history: List[float], value: float) -> Tuple[Optional[float], Optional[float], Optional[float]]:
        if len(history) < self.RESIDUAL_HISTORY_MIN:
            return None, None, None
        mean = sum(history) / len(history)
        variance = sum((item - mean) ** 2 for item in history) / max(1, len(history) - 1)
        std = math.sqrt(variance)
        if std <= 1e-9:
            return None, mean, std
        return (value - mean) / std, mean, std

    def portfolio_greeks(self, state, smile) -> Dict[str, float]:
        greeks = {
            "delta": float(state.position.get(self.UNDERLYING, 0)),
            "gamma": 0.0,
            "vega": 0.0,
            "theta": 0.0,
        }
        if smile is None:
            return greeks

        deltas = smile.get("deltas", {})
        gammas = smile.get("gammas", {})
        vegas = smile.get("vegas", {})
        thetas = smile.get("thetas", {})
        for option in self.OPTIONS:
            qty = state.position.get(option, 0)
            greeks["delta"] += qty * deltas.get(option, 0.0)
            greeks["gamma"] += qty * gammas.get(option, 0.0)
            greeks["vega"] += qty * vegas.get(option, 0.0)
            greeks["theta"] += qty * thetas.get(option, 0.0)
        return greeks

    def build_leave_one_out_models(self, points, snapshots, spot: float, t: float) -> Dict[str, float]:
        models: Dict[str, float] = {}
        for product in self.SMILE_PRODUCTS:
            filtered = [point for point in points if point[3] != product]
            if len(filtered) < 4:
                continue
            coef = self.weighted_quadratic_fit(filtered)
            if coef is None:
                continue
            strike = self.OPTIONS[product]
            moneyness = math.log(strike / spot) / math.sqrt(t)
            fair_iv = max(0.0001, self.eval_quadratic(coef, moneyness))
            models[product] = self.bs_call_price(spot, strike, t, fair_iv)
        return models

    def get_tte_candidates(self, timestamp: int) -> Tuple[Tuple[float, ...], str]:
        if self.AUTO_TTE:
            return self.TTE_CANDIDATES, "auto"

        if abs(timestamp) >= 1_000_000:
            day_index = int(timestamp // 1_000_000)
            day_fraction = (timestamp % int(self.DAY_TIMESTAMP_STRIDE)) / self.DAY_TIMESTAMP_STRIDE
            return (max(0.01, self.HISTORICAL_DAY0_TTE - day_index - day_fraction),), "global_timestamp"

        live_fraction = max(0.0, timestamp) / self.DAY_TIMESTAMP_STRIDE
        return (max(0.01, self.LIVE_TTE_DAYS - live_fraction),), "live"

    def passive_bid_price(self, snap, model: float, min_edge: float) -> Optional[int]:
        if snap["bid"] is None or snap["ask"] is None:
            return None
        price = int(snap["bid"])
        improved = price + 1
        if improved < snap["ask"] and model - improved >= min_edge + 1.0:
            price = improved
        if price < snap["ask"] and model - price >= min_edge:
            return max(0, price)
        return None

    def passive_ask_price(self, snap, model: float, min_edge: float) -> Optional[int]:
        if snap["bid"] is None or snap["ask"] is None:
            return None
        price = int(snap["ask"])
        improved = price - 1
        if improved > snap["bid"] and improved - model >= min_edge + 1.0:
            price = improved
        if price > snap["bid"] and price - model >= min_edge:
            return max(1, price)
        return None

    def build_snapshots(self, order_depths: Dict[str, OrderDepth]) -> Dict[str, dict]:
        snapshots = {}
        for product, depth in order_depths.items():
            bids = sorted([(price, volume) for price, volume in depth.buy_orders.items() if volume > 0], reverse=True)
            asks = sorted([(price, -volume) for price, volume in depth.sell_orders.items() if volume < 0])
            bid = bids[0][0] if bids else None
            ask = asks[0][0] if asks else None
            if bid is not None and ask is not None:
                mid = (bid + ask) / 2.0
                spread = ask - bid
            elif bid is not None:
                mid = float(bid)
                spread = None
            elif ask is not None:
                mid = float(ask)
                spread = None
            else:
                mid = None
                spread = None
            wall_mid = None
            if bids and asks:
                wall_mid = (bids[-1][0] + asks[-1][0]) / 2.0
            snapshots[product] = {
                "bids": bids,
                "asks": asks,
                "bid": bid,
                "ask": ask,
                "mid": mid,
                "wall_mid": wall_mid,
                "spread": spread,
            }
        return snapshots

    def net_and_clip_orders(self, product: str, orders: List[Order], position: int) -> List[Order]:
        if not orders:
            return []
        limit = self.POSITION_LIMITS.get(product, 300)
        buy_capacity = max(0, limit - position)
        sell_capacity = max(0, limit + position)
        clipped = []
        used_buy = 0
        used_sell = 0
        for order in orders:
            if order.quantity > 0:
                qty = min(order.quantity, buy_capacity - used_buy)
                if qty > 0:
                    clipped.append(Order(product, int(order.price), int(qty)))
                    used_buy += qty
            elif order.quantity < 0:
                qty = min(-order.quantity, sell_capacity - used_sell)
                if qty > 0:
                    clipped.append(Order(product, int(order.price), -int(qty)))
                    used_sell += qty
        return clipped

    def net_and_clip_detailed_orders(self, product: str, detailed_orders: List[Tuple[Order, str, dict]], position: int) -> List[Tuple[Order, str, dict]]:
        if not detailed_orders:
            return []
        limit = self.POSITION_LIMITS.get(product, 300)
        buy_capacity = max(0, limit - position)
        sell_capacity = max(0, limit + position)
        clipped: List[Tuple[Order, str, dict]] = []
        used_buy = 0
        used_sell = 0
        for order, reason, meta in detailed_orders:
            if order.quantity > 0:
                qty = min(order.quantity, buy_capacity - used_buy)
                if qty > 0:
                    clipped_order = Order(product, int(order.price), int(qty))
                    clipped_meta = dict(meta)
                    clipped_meta["submitted_qty"] = int(qty)
                    clipped.append((clipped_order, reason, clipped_meta))
                    used_buy += qty
            elif order.quantity < 0:
                qty = min(-order.quantity, sell_capacity - used_sell)
                if qty > 0:
                    clipped_order = Order(product, int(order.price), -int(qty))
                    clipped_meta = dict(meta)
                    clipped_meta["submitted_qty"] = -int(qty)
                    clipped.append((clipped_order, reason, clipped_meta))
                    used_sell += qty
        return clipped

    def norm_cdf(self, x: float) -> float:
        return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))

    def norm_pdf(self, x: float) -> float:
        return math.exp(-0.5 * x * x) / math.sqrt(2.0 * math.pi)

    def bs_call_price(self, spot: float, strike: float, t: float, sigma: float) -> float:
        intrinsic = max(spot - strike, 0.0)
        if t <= 0 or sigma <= 1e-9:
            return intrinsic
        vol_sqrt_t = sigma * math.sqrt(t)
        if vol_sqrt_t <= 0:
            return intrinsic
        d1 = (math.log(spot / strike) + 0.5 * sigma * sigma * t) / vol_sqrt_t
        d2 = d1 - vol_sqrt_t
        return spot * self.norm_cdf(d1) - strike * self.norm_cdf(d2)

    def bs_vega(self, spot: float, strike: float, t: float, sigma: float) -> float:
        if t <= 0 or sigma <= 1e-9:
            return 0.0
        vol_sqrt_t = sigma * math.sqrt(t)
        if vol_sqrt_t <= 0:
            return 0.0
        d1 = (math.log(spot / strike) + 0.5 * sigma * sigma * t) / vol_sqrt_t
        return spot * self.norm_pdf(d1) * math.sqrt(t)

    def bs_delta(self, spot: float, strike: float, t: float, sigma: float) -> float:
        if t <= 0 or sigma <= 1e-9:
            return 1.0 if spot > strike else 0.0
        vol_sqrt_t = sigma * math.sqrt(t)
        if vol_sqrt_t <= 0:
            return 1.0 if spot > strike else 0.0
        d1 = (math.log(spot / strike) + 0.5 * sigma * sigma * t) / vol_sqrt_t
        return self.norm_cdf(d1)

    def bs_gamma(self, spot: float, strike: float, t: float, sigma: float) -> float:
        if spot <= 0 or t <= 0 or sigma <= 1e-9:
            return 0.0
        vol_sqrt_t = sigma * math.sqrt(t)
        if vol_sqrt_t <= 0:
            return 0.0
        d1 = (math.log(spot / strike) + 0.5 * sigma * sigma * t) / vol_sqrt_t
        return self.norm_pdf(d1) / (spot * vol_sqrt_t)

    def bs_theta_per_day(self, spot: float, strike: float, t: float, sigma: float) -> float:
        if t <= 0 or sigma <= 1e-9:
            return 0.0
        vol_sqrt_t = sigma * math.sqrt(t)
        if vol_sqrt_t <= 0:
            return 0.0
        d1 = (math.log(spot / strike) + 0.5 * sigma * sigma * t) / vol_sqrt_t
        annual_theta = -(spot * self.norm_pdf(d1) * sigma) / (2.0 * math.sqrt(t))
        return annual_theta / 365.0

    def implied_vol(self, mid: float, spot: float, strike: float, t: float) -> Optional[float]:
        if spot <= 0 or strike <= 0 or t <= 0:
            return None
        intrinsic = max(spot - strike, 0.0)
        if mid <= intrinsic + 1e-6 or mid >= spot:
            return None
        lo = 1e-5
        hi = 6.0
        if self.bs_call_price(spot, strike, t, hi) < mid:
            return None
        for _ in range(60):
            sigma = (lo + hi) / 2.0
            price = self.bs_call_price(spot, strike, t, sigma)
            if price < mid:
                lo = sigma
            else:
                hi = sigma
        return (lo + hi) / 2.0

    def weighted_quadratic_fit(self, points) -> Optional[Tuple[float, float, float]]:
        matrix = [[0.0 for _ in range(3)] for _ in range(3)]
        vector = [0.0 for _ in range(3)]
        for x, y, weight, _ in points:
            features = [x * x, x, 1.0]
            w = weight * weight
            for i in range(3):
                vector[i] += w * features[i] * y
                for j in range(3):
                    matrix[i][j] += w * features[i] * features[j]
        return self.solve_3x3(matrix, vector)

    def solve_3x3(self, matrix, vector) -> Optional[Tuple[float, float, float]]:
        a = [row[:] + [vector[i]] for i, row in enumerate(matrix)]
        n = 3
        for col in range(n):
            pivot = max(range(col, n), key=lambda r: abs(a[r][col]))
            if abs(a[pivot][col]) < 1e-12:
                return None
            if pivot != col:
                a[col], a[pivot] = a[pivot], a[col]
            divisor = a[col][col]
            for k in range(col, n + 1):
                a[col][k] /= divisor
            for r in range(n):
                if r == col:
                    continue
                factor = a[r][col]
                for k in range(col, n + 1):
                    a[r][k] -= factor * a[col][k]
        return a[0][3], a[1][3], a[2][3]

    def eval_quadratic(self, coef, x: float) -> float:
        return coef[0] * x * x + coef[1] * x + coef[2]

    def load_trader_data(self, trader_data: str) -> dict:
        if not trader_data:
            return {}
        try:
            return json.loads(trader_data)
        except Exception:
            return {}

    def remember(self, saved: dict, key: str, value: float, limit: int) -> None:
        history = saved.setdefault(key, [])
        history.append(float(value))
        if len(history) > limit:
            del history[:-limit]

    def make_trader_data(self, saved: dict, snapshots: Dict[str, dict], smile) -> str:
        underlying = snapshots.get(self.UNDERLYING)
        if underlying and underlying["mid"] is not None:
            ema = saved.get("velvet_ema_next", underlying["mid"])
            saved["velvet_ema"] = float(ema)
            saved.pop("velvet_ema_next", None)
            self.remember(saved, "velvet_mid_history", underlying["mid"], self.HISTORY_LIMIT)
        for product in self.MICRO_PRODUCTS:
            snap = snapshots.get(product)
            if snap is not None:
                wall_mid = snap.get("wall_mid") if snap.get("wall_mid") is not None else snap.get("mid")
                if wall_mid is not None:
                    self.remember(saved, f"micro_wall_{product}", wall_mid, self.MICRO_HISTORY_LIMIT)
        if smile is not None:
            saved["last_smile_tte"] = smile["tte"]
            saved["last_smile_score"] = smile["score"]
            models = smile.get("loo_models", smile.get("models", {}))
            for product in self.SMILE_PRODUCTS:
                snap = snapshots.get(product)
                model = models.get(product)
                if snap is not None and model is not None and snap.get("mid") is not None:
                    self.remember(saved, f"resid_{product}", snap["mid"] - model, self.HISTORY_LIMIT)
                iv_residual = smile.get("iv_residuals", {}).get(product)
                if iv_residual is not None:
                    self.remember(saved, f"iv_resid_{product}", iv_residual, self.HISTORY_LIMIT)
        return json.dumps(saved, separators=(",", ":"))

    def log_orders(self, timestamp: int, product: str, detailed_orders, snapshot, smile) -> None:
        if not self.ENABLE_RESEARCH_LOGS:
            return
        orders = [item[0] for item in detailed_orders]
        reasons = [item[1] for item in detailed_orders]
        meta = detailed_orders[0][2] if detailed_orders else {}

        def compact_value(value):
            if isinstance(value, float):
                return round(value, 4)
            return value

        detail_keys = (
            "quote_qty",
            "size_bucket",
            "model",
            "edge_to_model",
            "residual",
            "residual_z",
            "iv_z",
            "delta_exposure",
            "micro_signal",
            "micro_model",
            "micro_ret1",
            "micro_ret5",
            "micro_residual",
            "micro_imbalance",
            "smile_model",
            "submitted_qty",
        )
        order_details = []
        for order, reason, item_meta in detailed_orders:
            detail = {
                "reason": reason,
                "price": order.price,
                "quantity": order.quantity,
                "side": "BUY" if order.quantity > 0 else "SELL",
            }
            for key in detail_keys:
                value = item_meta.get(key)
                if value is not None:
                    detail[key] = compact_value(value)
            order_details.append(detail)
        payload = {
            "kind": "quotes",
            "timestamp": timestamp,
            "product": product,
            "bid": snapshot.get("bid") if snapshot else None,
            "ask": snapshot.get("ask") if snapshot else None,
            "mid": snapshot.get("mid") if snapshot else None,
            "reason": "+".join(reasons),
            "smile_tte": smile.get("tte") if smile else None,
            "tte_source": smile.get("tte_source") if smile else None,
            "smile_score": compact_value(smile.get("score")) if smile else None,
            "model": compact_value(meta.get("model")),
            "residual": compact_value(meta.get("residual")),
            "residual_z": compact_value(meta.get("residual_z")),
            "iv_z": compact_value(meta.get("iv_z")),
            "delta_exposure": compact_value(meta.get("delta_exposure")),
            "micro_signal": compact_value(meta.get("micro_signal")),
            "micro_model": compact_value(meta.get("micro_model")),
            "micro_ret1": compact_value(meta.get("micro_ret1")),
            "micro_ret5": compact_value(meta.get("micro_ret5")),
            "micro_residual": compact_value(meta.get("micro_residual")),
            "micro_imbalance": compact_value(meta.get("micro_imbalance")),
            "smile_model": compact_value(meta.get("smile_model")),
            "orders": [[order.price, order.quantity] for order in orders],
            "order_details": order_details,
        }
        print(json.dumps(payload, separators=(",", ":")))
