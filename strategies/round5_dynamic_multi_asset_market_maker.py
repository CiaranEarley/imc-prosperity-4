from datamodel import Order, OrderDepth, TradingState
from typing import Dict, List, Optional, Tuple
import json


class Trader:
    POSITION_LIMIT = 10
    DEFAULT_WARMUP_FACTOR = 0.40
    WARMUP_FACTOR_BY_PRODUCT = {
        "GALAXY_SOUNDS_BLACK_HOLES": 1.25,
        "MICROCHIP_OVAL": 2.00,
        "MICROCHIP_RECTANGLE": 1.25,
        "PEBBLES_M": 1.50,
        "ROBOT_IRONING": 0.50,
        "SNACKPACK_VANILLA": 0.50,
        "TRANSLATOR_ASTRO_BLACK": 1.25,
        "UV_VISOR_RED": 0.50,
    }
    OPEN_OVERLAY_UNTIL = {
        "GALAXY_SOUNDS_DARK_MATTER": 1500,
        "SLEEP_POD_LAMB_WOOL": 1500,
    }

    # Started from the high-PnL historical grid, then pruned with the official
    # 549071 website log: products that finished negative there, plus one tiny
    # positive/high-drawdown product, are disabled to improve both PnL and DD.
    # - touch: quote one tick inside both sides, capped by soft_limit
    # - fair: quote one tick inside only when attractive versus a live EMA fair
    # - off: included in the product universe but skipped because every tested
    #   low-drawdown config was worse than cash.
    PRODUCT_CONFIG = {
        'GALAXY_SOUNDS_BLACK_HOLES': {'mode': 'fair', 'window': 20, 'edge': 40.0, 'soft_limit': 10, 'size': 10},
        'GALAXY_SOUNDS_DARK_MATTER': {'mode': 'fair', 'window': 1000, 'edge': 40.0, 'soft_limit': 10, 'size': 10},
        'GALAXY_SOUNDS_PLANETARY_RINGS': {'mode': 'fair', 'window': 100, 'edge': 10.0, 'soft_limit': 10, 'size': 10},
        'GALAXY_SOUNDS_SOLAR_FLAMES': {'mode': 'fair', 'window': 20, 'edge': 32.0, 'soft_limit': 10, 'size': 10},
        'GALAXY_SOUNDS_SOLAR_WINDS': {'mode': 'fair', 'window': 100, 'edge': 32.0, 'soft_limit': 10, 'size': 10},
        'MICROCHIP_CIRCLE': {'mode': 'fair', 'window': 50, 'edge': 1.0, 'soft_limit': 10, 'size': 10},
        'MICROCHIP_OVAL': {'mode': 'fair', 'window': 500, 'edge': 10.0, 'soft_limit': 10, 'size': 10},
        'MICROCHIP_RECTANGLE': {'mode': 'fair', 'window': 2000, 'edge': 32.0, 'soft_limit': 10, 'size': 10},
        'MICROCHIP_SQUARE': {'mode': 'touch', 'soft_limit': 5, 'size': 5},
        'MICROCHIP_TRIANGLE': {'mode': 'fair', 'window': 2000, 'edge': 0.0, 'soft_limit': 10, 'size': 10},
        'OXYGEN_SHAKE_CHOCOLATE': {'mode': 'fair', 'window': 100, 'edge': 10.0, 'soft_limit': 10, 'size': 10},
        'OXYGEN_SHAKE_EVENING_BREATH': {'mode': 'fair', 'window': 20, 'edge': 6.0, 'soft_limit': 10, 'size': 10},
        'OXYGEN_SHAKE_GARLIC': {'mode': 'fair', 'window': 500, 'edge': 0.0, 'soft_limit': 10, 'size': 10},
        'OXYGEN_SHAKE_MINT': {'mode': 'fair', 'window': 2000, 'edge': 40.0, 'soft_limit': 7, 'size': 7},
        'OXYGEN_SHAKE_MORNING_BREATH': {'mode': 'fair', 'window': 50, 'edge': 20.0, 'soft_limit': 10, 'size': 10},
        'PANEL_1X2': {'mode': 'fair', 'window': 20, 'edge': 24.0, 'soft_limit': 10, 'size': 10},
        'PANEL_1X4': {'mode': 'touch', 'soft_limit': 10, 'size': 3},
        'PANEL_2X2': {'mode': 'fair', 'window': 500, 'edge': 8.0, 'soft_limit': 5, 'size': 5},
        'PANEL_2X4': {'mode': 'fair', 'window': 50, 'edge': 2.0, 'soft_limit': 10, 'size': 10},
        'PANEL_4X4': {'mode': 'fair', 'window': 20, 'edge': 12.0, 'soft_limit': 10, 'size': 10},
        'PEBBLES_L': {'mode': 'fair', 'window': 250, 'edge': 32.0, 'soft_limit': 5, 'size': 5},
        'PEBBLES_M': {'mode': 'fair', 'window': 2000, 'edge': 24.0, 'soft_limit': 10, 'size': 10},
        'PEBBLES_S': {'mode': 'touch', 'soft_limit': 10, 'size': 10},
        'PEBBLES_XL': {'mode': 'fair', 'window': 100, 'edge': 10.0, 'soft_limit': 10, 'size': 10},
        'PEBBLES_XS': {'mode': 'fair', 'window': 50, 'edge': 1.0, 'soft_limit': 10, 'size': 10},
        'ROBOT_DISHES': {'mode': 'fair', 'window': 2000, 'edge': 32.0, 'soft_limit': 10, 'size': 10},
        'ROBOT_IRONING': {'mode': 'fair', 'window': 20, 'edge': 0.0, 'soft_limit': 10, 'size': 10},
        'ROBOT_LAUNDRY': {'mode': 'fair', 'window': 20, 'edge': 24.0, 'soft_limit': 10, 'size': 10},
        'ROBOT_MOPPING': {'mode': 'fair', 'window': 500, 'edge': 40.0, 'soft_limit': 10, 'size': 10},
        'ROBOT_VACUUMING': {'mode': 'fair', 'window': 250, 'edge': 20.0, 'soft_limit': 10, 'size': 10},
        'SLEEP_POD_COTTON': {'mode': 'fair', 'window': 50, 'edge': 6.0, 'soft_limit': 10, 'size': 10},
        'SLEEP_POD_LAMB_WOOL': {'mode': 'fair', 'window': 500, 'edge': 24.0, 'soft_limit': 10, 'size': 10},
        'SLEEP_POD_NYLON': {'mode': 'fair', 'window': 1000, 'edge': 10.0, 'soft_limit': 10, 'size': 10},
        'SLEEP_POD_POLYESTER': {'mode': 'fair', 'window': 250, 'edge': 24.0, 'soft_limit': 10, 'size': 10},
        'SLEEP_POD_SUEDE': {'mode': 'fair', 'window': 20, 'edge': 10.0, 'soft_limit': 10, 'size': 10},
        'SNACKPACK_CHOCOLATE': {'mode': 'fair', 'window': 2000, 'edge': 40.0, 'soft_limit': 10, 'size': 10},
        'SNACKPACK_PISTACHIO': {'mode': 'fair', 'window': 1000, 'edge': 32.0, 'soft_limit': 10, 'size': 10},
        'SNACKPACK_RASPBERRY': {'mode': 'fair', 'window': 1000, 'edge': 40.0, 'soft_limit': 10, 'size': 10},
        'SNACKPACK_STRAWBERRY': {'mode': 'fair', 'window': 20, 'edge': 6.0, 'soft_limit': 10, 'size': 10},
        'SNACKPACK_VANILLA': {'mode': 'fair', 'window': 2000, 'edge': 40.0, 'soft_limit': 10, 'size': 10},
        'TRANSLATOR_ASTRO_BLACK': {'mode': 'fair', 'window': 2000, 'edge': 40.0, 'soft_limit': 10, 'size': 10},
        'TRANSLATOR_ECLIPSE_CHARCOAL': {'mode': 'fair', 'window': 250, 'edge': 12.0, 'soft_limit': 10, 'size': 10},
        'TRANSLATOR_GRAPHITE_MIST': {'mode': 'fair', 'window': 1000, 'edge': 16.0, 'soft_limit': 10, 'size': 10},
        'TRANSLATOR_SPACE_GRAY': {'mode': 'fair', 'window': 20, 'edge': 24.0, 'soft_limit': 10, 'size': 10},
        'TRANSLATOR_VOID_BLUE': {'mode': 'fair', 'window': 20, 'edge': 10.0, 'soft_limit': 10, 'size': 10},
        'UV_VISOR_AMBER': {'mode': 'touch', 'soft_limit': 10, 'size': 5},
        'UV_VISOR_MAGENTA': {'mode': 'fair', 'window': 50, 'edge': 32.0, 'soft_limit': 10, 'size': 10},
        'UV_VISOR_ORANGE': {'mode': 'fair', 'window': 20, 'edge': 10.0, 'soft_limit': 10, 'size': 10},
        'UV_VISOR_RED': {'mode': 'fair', 'window': 2000, 'edge': 8.0, 'soft_limit': 10, 'size': 10},
        'UV_VISOR_YELLOW': {'mode': 'touch', 'soft_limit': 7, 'size': 5},
    }
    EARLY_PRODUCT_CONFIG = {
        'GALAXY_SOUNDS_BLACK_HOLES': {'mode': 'fair', 'window': 50, 'edge': 12.0, 'soft_limit': 7, 'size': 7},
        'GALAXY_SOUNDS_DARK_MATTER': {'mode': 'off', 'soft_limit': 0, 'size': 0},
        'GALAXY_SOUNDS_PLANETARY_RINGS': {'mode': 'off', 'soft_limit': 0, 'size': 0},
        'GALAXY_SOUNDS_SOLAR_FLAMES': {'mode': 'fair', 'window': 20, 'edge': 32.0, 'soft_limit': 3, 'size': 3},
        'GALAXY_SOUNDS_SOLAR_WINDS': {'mode': 'fair', 'window': 2000, 'edge': 10.0, 'soft_limit': 3, 'size': 3},
        'MICROCHIP_CIRCLE': {'mode': 'fair', 'window': 50, 'edge': 1.0, 'soft_limit': 10, 'size': 10},
        'MICROCHIP_OVAL': {'mode': 'touch', 'soft_limit': 10, 'size': 10},
        'MICROCHIP_RECTANGLE': {'mode': 'fair', 'window': 250, 'edge': 20.0, 'soft_limit': 7, 'size': 7},
        'MICROCHIP_SQUARE': {'mode': 'touch', 'soft_limit': 5, 'size': 5},
        'MICROCHIP_TRIANGLE': {'mode': 'fair', 'window': 2000, 'edge': 0.0, 'soft_limit': 10, 'size': 10},
        'OXYGEN_SHAKE_CHOCOLATE': {'mode': 'fair', 'window': 100, 'edge': 10.0, 'soft_limit': 10, 'size': 10},
        'OXYGEN_SHAKE_EVENING_BREATH': {'mode': 'off', 'soft_limit': 0, 'size': 0},
        'OXYGEN_SHAKE_GARLIC': {'mode': 'fair', 'window': 500, 'edge': 0.0, 'soft_limit': 10, 'size': 10},
        'OXYGEN_SHAKE_MINT': {'mode': 'off', 'soft_limit': 0, 'size': 0},
        'OXYGEN_SHAKE_MORNING_BREATH': {'mode': 'off', 'soft_limit': 0, 'size': 0},
        'PANEL_1X2': {'mode': 'fair', 'window': 20, 'edge': 24.0, 'soft_limit': 10, 'size': 10},
        'PANEL_1X4': {'mode': 'off', 'soft_limit': 0, 'size': 0},
        'PANEL_2X2': {'mode': 'off', 'soft_limit': 0, 'size': 0},
        'PANEL_2X4': {'mode': 'off', 'soft_limit': 0, 'size': 0},
        'PANEL_4X4': {'mode': 'off', 'soft_limit': 0, 'size': 0},
        'PEBBLES_L': {'mode': 'fair', 'window': 20, 'edge': 0.0, 'soft_limit': 7, 'size': 7},
        'PEBBLES_M': {'mode': 'fair', 'window': 100, 'edge': 12.0, 'soft_limit': 3, 'size': 3},
        'PEBBLES_S': {'mode': 'touch', 'soft_limit': 10, 'size': 10},
        'PEBBLES_XL': {'mode': 'fair', 'window': 100, 'edge': 10.0, 'soft_limit': 10, 'size': 10},
        'PEBBLES_XS': {'mode': 'fair', 'window': 50, 'edge': 1.0, 'soft_limit': 7, 'size': 7},
        'ROBOT_DISHES': {'mode': 'fair', 'window': 2000, 'edge': 32.0, 'soft_limit': 10, 'size': 10},
        'ROBOT_IRONING': {'mode': 'fair', 'window': 50, 'edge': 4.0, 'soft_limit': 10, 'size': 10},
        'ROBOT_LAUNDRY': {'mode': 'off', 'soft_limit': 0, 'size': 0},
        'ROBOT_MOPPING': {'mode': 'off', 'soft_limit': 0, 'size': 0},
        'ROBOT_VACUUMING': {'mode': 'fair', 'window': 250, 'edge': 20.0, 'soft_limit': 10, 'size': 10},
        'SLEEP_POD_COTTON': {'mode': 'fair', 'window': 50, 'edge': 10.0, 'soft_limit': 7, 'size': 7},
        'SLEEP_POD_LAMB_WOOL': {'mode': 'off', 'soft_limit': 0, 'size': 0},
        'SLEEP_POD_NYLON': {'mode': 'fair', 'window': 1000, 'edge': 10.0, 'soft_limit': 10, 'size': 10},
        'SLEEP_POD_POLYESTER': {'mode': 'fair', 'window': 250, 'edge': 24.0, 'soft_limit': 10, 'size': 10},
        'SLEEP_POD_SUEDE': {'mode': 'fair', 'window': 20, 'edge': 10.0, 'soft_limit': 10, 'size': 10},
        'SNACKPACK_CHOCOLATE': {'mode': 'fair', 'window': 2000, 'edge': 32.0, 'soft_limit': 10, 'size': 10},
        'SNACKPACK_PISTACHIO': {'mode': 'fair', 'window': 1000, 'edge': 32.0, 'soft_limit': 10, 'size': 10},
        'SNACKPACK_RASPBERRY': {'mode': 'fair', 'window': 1000, 'edge': 32.0, 'soft_limit': 10, 'size': 10},
        'SNACKPACK_STRAWBERRY': {'mode': 'fair', 'window': 20, 'edge': 6.0, 'soft_limit': 10, 'size': 10},
        'SNACKPACK_VANILLA': {'mode': 'fair', 'window': 2000, 'edge': 20.0, 'soft_limit': 10, 'size': 10},
        'TRANSLATOR_ASTRO_BLACK': {'mode': 'touch', 'soft_limit': 10, 'size': 10},
        'TRANSLATOR_ECLIPSE_CHARCOAL': {'mode': 'fair', 'window': 250, 'edge': 12.0, 'soft_limit': 10, 'size': 10},
        'TRANSLATOR_GRAPHITE_MIST': {'mode': 'off', 'soft_limit': 0, 'size': 0},
        'TRANSLATOR_SPACE_GRAY': {'mode': 'fair', 'window': 20, 'edge': 24.0, 'soft_limit': 10, 'size': 10},
        'TRANSLATOR_VOID_BLUE': {'mode': 'fair', 'window': 20, 'edge': 10.0, 'soft_limit': 10, 'size': 10},
        'UV_VISOR_AMBER': {'mode': 'off', 'soft_limit': 0, 'size': 0},
        'UV_VISOR_MAGENTA': {'mode': 'off', 'soft_limit': 0, 'size': 0},
        'UV_VISOR_ORANGE': {'mode': 'fair', 'window': 20, 'edge': 10.0, 'soft_limit': 10, 'size': 10},
        'UV_VISOR_RED': {'mode': 'touch', 'soft_limit': 10, 'size': 10},
        'UV_VISOR_YELLOW': {'mode': 'off', 'soft_limit': 0, 'size': 0},
    }
    POSITION_LIMITS: Dict[str, int] = {}

    # Keep these small and deterministic. The EMA is used as a live proxy for
    # the rolling fair values fitted from the historical CSVs.
    EMA_WINDOWS = (20, 50, 100, 250, 500, 1000, 2000)
    MIN_SAMPLES = {20: 5, 50: 12, 100: 25, 250: 62, 500: 125, 1000: 250, 2000: 500}
    MIN_SPREAD = 2
    PASSIVE_CROSS_OFFSET = 1
    INVENTORY_EDGE_SKEW = 0.15
    SELECTIVE_OFFSET_2 = set()
    TREND_FILTER_PRODUCTS = (
        "SLEEP_POD_COTTON",
        "PEBBLES_XL",
        "TRANSLATOR_ASTRO_BLACK",
        "UV_VISOR_RED",
        "MICROCHIP_SQUARE",
        "ROBOT_IRONING",
        "UV_VISOR_AMBER",
        "ROBOT_LAUNDRY",
        "PEBBLES_M",
    )
    TREND_BLOCK_EXTRA_EDGE = 20.0
    TREND_LEAN_EDGE_REDUCTION = 4.0

    def run(self, state: TradingState):
        saved = self.load_state(state.traderData)
        if state.timestamp < saved.get("last_timestamp", -1):
            saved = self.empty_state()
        seen = int(saved.get("seen", 0))
        saved["seen"] = seen + 1

        result: Dict[str, List[Order]] = {}
        snapshots = self.build_snapshots(state.order_depths)

        active_config = self.active_product_config(saved)
        for product, config in active_config.items():
            result[product] = []
            snap = snapshots.get(product)
            if snap is None:
                continue

            position = state.position.get(product, 0)
            fair = self.get_fair(product, config, snap["mid"], saved)
            if fair is None:
                continue

            orders = self.make_orders(product, config, snap, fair, position, saved)
            result[product] = orders

        self.add_active_overlays(result, snapshots, state.position, saved, seen)

        for product, snap in snapshots.items():
            if product in self.PRODUCT_CONFIG:
                self.update_emas(product, snap["mid"], saved)

        saved["last_timestamp"] = state.timestamp
        return result, 0, self.dump_state(saved)

    def build_snapshots(self, order_depths: Dict[str, OrderDepth]) -> Dict[str, dict]:
        snapshots = {}
        for product, depth in order_depths.items():
            if not depth.buy_orders or not depth.sell_orders:
                continue
            bid = max(depth.buy_orders)
            ask = min(depth.sell_orders)
            if bid >= ask:
                continue
            snapshots[product] = {
                "bid": int(bid),
                "ask": int(ask),
                "bid_vol": max(0, int(depth.buy_orders[bid])),
                "ask_vol": max(0, -int(depth.sell_orders[ask])),
                "mid": (bid + ask) / 2.0,
                "spread": ask - bid,
            }
        return snapshots

    def active_product_config(self, saved):
        active = {}
        for product, config in self.PRODUCT_CONFIG.items():
            active[product] = self.warmup_config(product, config, saved)
        return active

    def warmup_config(self, product, config, saved):
        if config.get("mode") != "fair":
            return config
        product_state = saved.get("products", {}).get(product, {})
        # A fair-value EMA is considered mature only after one full configured window.
        # Until then, use the simpler teammate/baseline config if it trades the product.
        factor = self.WARMUP_FACTOR_BY_PRODUCT.get(product, self.DEFAULT_WARMUP_FACTOR)
        if int(product_state.get("n", 0)) < int(config.get("window", 0) * factor):
            alt = self.EARLY_PRODUCT_CONFIG.get(product)
            if alt and alt.get("mode") != "off":
                return alt
        return config

    def is_warmup(self, product, saved):
        config = self.PRODUCT_CONFIG.get(product, {})
        if config.get("mode") != "fair":
            return False
        n = int(saved.get("products", {}).get(product, {}).get("n", 0))
        return n < int(config.get("window", 0))

    def is_open_overlay(self, product, seen):
        return seen < int(self.OPEN_OVERLAY_UNTIL.get(product, 0))

    def add_active_overlays(self, result, snapshots, positions, saved, seen):
        targets = {}
        self.overlay_trend(saved, seen, snapshots, targets, "GALAXY_SOUNDS_PLANETARY_RINGS", "rings", 200, 1200, 1.5, 0.375, 10, 1, 200, 0)
        self.overlay_trend(saved, seen, snapshots, targets, "PANEL_1X4", "p14", 100, 600, 1.5, 0.375, 7, 1, 400, 600)
        self.overlay_trend(saved, seen, snapshots, targets, "PANEL_2X4", "p24", 200, 1200, 1.0, 0.25, 7, -1, 400, 600)
        if self.is_warmup("PANEL_2X2", saved):
            self.overlay_trend(saved, seen, snapshots, targets, "PANEL_2X2", "p22", 200, 1200, 1.5, 0.375, 10, 1, 200, 0)
        if self.is_open_overlay("SLEEP_POD_LAMB_WOOL", seen):
            self.overlay_trend(saved, seen, snapshots, targets, "SLEEP_POD_LAMB_WOOL", "lamb", 200, 1200, 1.5, 0.375, 10, 1, 200, 0)
        if self.is_warmup("PANEL_4X4", saved):
            self.overlay_trend(saved, seen, snapshots, targets, "PANEL_4X4", "p44", 200, 1200, 1.5, 0.375, 10, 1, 200, 0)
        if self.is_warmup("ROBOT_LAUNDRY", saved):
            self.overlay_trend(saved, seen, snapshots, targets, "ROBOT_LAUNDRY", "laundry", 200, 1200, 1.5, 0.375, 10, 1, 200, 0)
        if self.is_warmup("UV_VISOR_MAGENTA", saved):
            self.overlay_trend(saved, seen, snapshots, targets, "UV_VISOR_MAGENTA", "magenta", 200, 1200, 1.5, 0.375, 10, 1, 200, 0)
        if self.is_warmup("ROBOT_MOPPING", saved):
            self.overlay_trend(saved, seen, snapshots, targets, "ROBOT_MOPPING", "mopping", 200, 1200, 1.0, 0.25, 7, -1, 400, 600)
        if self.is_warmup("OXYGEN_SHAKE_EVENING_BREATH", saved):
            self.overlay_trend(saved, seen, snapshots, targets, "OXYGEN_SHAKE_EVENING_BREATH", "evening", 200, 1200, 1.0, 0.25, 7, -1, 400, 600)
        if self.is_open_overlay("GALAXY_SOUNDS_DARK_MATTER", seen):
            self.overlay_trend(saved, seen, snapshots, targets, "GALAXY_SOUNDS_DARK_MATTER", "dark", 100, 600, 1.5, 0.375, 7, 1, 400, 600)
        for product, target in targets.items():
            snap = snapshots.get(product)
            if snap is None:
                continue
            order = self.to_target(product, snap, positions.get(product, 0), target)
            if order:
                result.setdefault(product, []).append(order)

    def overlay_trend(self, saved, seen, snapshots, targets, product, key, fast, slow, entry, exit_level, size, mult, warmup, max_age):
        snap = snapshots.get(product)
        stats = saved.setdefault("overlay_stats", {})
        if snap is None:
            return
        item = stats.setdefault(product, {"fast": snap["mid"], "slow": snap["mid"], "dev": 4.0})
        score = mult * (float(item["fast"]) - float(item["slow"])) / max(4.0, float(item["dev"]))
        st_key = "overlay_" + key
        age_key = st_key + "_age"
        st = int(saved.get(st_key, 0))
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
        age = 0 if st == 0 else int(saved.get(age_key, 0)) + 1 if st == old else 1
        if max_age and st and age > max_age:
            st = 0
            age = 0
        saved[st_key] = st
        saved[age_key] = age
        if st:
            targets[product] = st * size
        af = 2.0 / (fast + 1.0)
        aslow = 2.0 / (slow + 1.0)
        old_slow = float(item.get("slow", snap["mid"]))
        item["fast"] = af * snap["mid"] + (1.0 - af) * float(item.get("fast", snap["mid"]))
        item["slow"] = aslow * snap["mid"] + (1.0 - aslow) * old_slow
        item["dev"] = max(4.0, aslow * abs(snap["mid"] - old_slow) + (1.0 - aslow) * float(item.get("dev", 4.0)))

    def to_target(self, product, snap, position, target):
        hard_limit = int(self.POSITION_LIMITS.get(product, self.POSITION_LIMIT))
        delta = max(-hard_limit, min(hard_limit, int(target))) - position
        if delta > 0:
            qty = min(delta, snap["ask_vol"], hard_limit - position)
            return Order(product, int(snap["ask"]), qty) if qty > 0 else None
        if delta < 0:
            qty = min(-delta, snap["bid_vol"], hard_limit + position)
            return Order(product, int(snap["bid"]), -qty) if qty > 0 else None
        return None

    def get_fair(self, product: str, config: dict, current_mid: float, saved: dict) -> Optional[float]:
        if config["mode"] == "off":
            return None
        if config["mode"] == "touch":
            return current_mid

        window = int(config["window"])
        product_state = saved["products"].get(product)
        if not product_state or product_state.get("n", 0) < self.MIN_SAMPLES[window]:
            return None

        fair = product_state.get("ema", {}).get(str(window))
        return fair if isinstance(fair, (int, float)) else None

    def make_orders(
        self,
        product: str,
        config: dict,
        snap: dict,
        fair: float,
        position: int,
        saved: dict,
    ) -> List[Order]:
        bid = snap["bid"]
        ask = snap["ask"]
        spread = snap["spread"]
        if spread < self.MIN_SPREAD:
            return []

        offset = int(config.get("offset", 2 if product in self.SELECTIVE_OFFSET_2 else self.PASSIVE_CROSS_OFFSET))
        buy_price = min(bid + offset, ask - 1)
        sell_price = max(ask - offset, bid + 1)

        edge = float(config.get("edge", 0.0))
        soft_limit = int(config["soft_limit"])
        max_size = int(config["size"])
        hard_limit = int(self.POSITION_LIMITS.get(product, self.POSITION_LIMIT))

        buy_edge = fair - buy_price
        sell_edge = sell_price - fair

        # Small inventory skew: when already long, demand a bit more buy edge
        # and make selling slightly easier; mirror the logic when short.
        buy_threshold = edge + max(0, position) * self.INVENTORY_EDGE_SKEW
        sell_threshold = edge + max(0, -position) * self.INVENTORY_EDGE_SKEW
        trend = self.trend_filter_signal(product, snap, saved)
        if trend > 0:
            buy_threshold = max(0.0, buy_threshold - self.TREND_LEAN_EDGE_REDUCTION)
            sell_threshold += self.TREND_BLOCK_EXTRA_EDGE
        elif trend < 0:
            buy_threshold += self.TREND_BLOCK_EXTRA_EDGE
            sell_threshold = max(0.0, sell_threshold - self.TREND_LEAN_EDGE_REDUCTION)

        orders: List[Order] = []

        if config.get("dynamic", True):
            buy_size = self.inventory_scaled_size(max_size, position, soft_limit, hard_limit, True)
            sell_size = self.inventory_scaled_size(max_size, position, soft_limit, hard_limit, False)
        else:
            buy_size = max_size
            sell_size = max_size

        buy_capacity = min(soft_limit - position, hard_limit - position)
        if buy_capacity > 0 and buy_edge >= buy_threshold:
            qty = min(buy_size, buy_capacity)
            orders.append(Order(product, buy_price, qty))

        sell_capacity = min(soft_limit + position, hard_limit + position)
        if sell_capacity > 0 and sell_edge >= sell_threshold:
            qty = min(sell_size, sell_capacity)
            orders.append(Order(product, sell_price, -qty))

        return orders

    def trend_filter_signal(self, product: str, snap: dict, saved: dict) -> int:
        if product not in self.TREND_FILTER_PRODUCTS:
            return 0
        product_state = saved.get("products", {}).get(product, {})
        if int(product_state.get("n", 0)) < self.MIN_SAMPLES[100]:
            return 0
        ema = product_state.get("ema", {})
        fast = ema.get("20")
        slow = ema.get("100")
        if not isinstance(fast, (int, float)) or not isinstance(slow, (int, float)):
            return 0
        threshold = max(6.0, float(snap.get("spread", 0)) * 0.75)
        diff = float(fast) - float(slow)
        if diff > threshold:
            return 1
        if diff < -threshold:
            return -1
        return 0

    def inventory_scaled_size(self, base_size: int, position: int, soft_limit: int, hard_limit: int, is_buy: bool) -> int:
        if is_buy:
            if position >= hard_limit:
                return 0
            if position >= soft_limit:
                return max(1, base_size // 3)
            if position <= -soft_limit:
                return base_size + max(1, base_size // 2)
            return base_size

        if position <= -hard_limit:
            return 0
        if position <= -soft_limit:
            return max(1, base_size // 3)
        if position >= soft_limit:
            return base_size + max(1, base_size // 2)
        return base_size

    def update_emas(self, product: str, mid: float, saved: dict) -> None:
        product_state = saved["products"].setdefault(product, {"n": 0, "ema": {}})
        ema = product_state.setdefault("ema", {})
        for window in self.EMA_WINDOWS:
            key = str(window)
            previous = ema.get(key)
            if previous is None:
                ema[key] = mid
            else:
                alpha = 2.0 / (window + 1.0)
                ema[key] = previous + alpha * (mid - previous)
        product_state["n"] = int(product_state.get("n", 0)) + 1

    def empty_state(self) -> dict:
        return {"last_timestamp": -1, "seen": 0, "products": {}}

    def load_state(self, trader_data: str) -> dict:
        if not trader_data:
            return self.empty_state()
        try:
            saved = json.loads(trader_data)
            if not isinstance(saved, dict):
                return self.empty_state()
            saved.setdefault("last_timestamp", -1)
            saved.setdefault("seen", 0)
            saved.setdefault("products", {})
            return saved
        except Exception:
            return self.empty_state()

    def dump_state(self, saved: dict) -> str:
        return json.dumps(saved, separators=(",", ":"))


Trader.POSITION_LIMITS = {product: Trader.POSITION_LIMIT for product in Trader.PRODUCT_CONFIG}
