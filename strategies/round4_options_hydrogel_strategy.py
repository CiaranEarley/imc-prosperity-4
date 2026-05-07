from datamodel import Order, OrderDepth, TradingState
import json
import math

class Trader:
    HYDROGEL_PRODUCT = 'HYDROGEL_PACK'
    UNDERLYING = 'VELVETFRUIT_EXTRACT'
    OPTIONS = {'VEV_4000': 4000, 'VEV_4500': 4500, 'VEV_5000': 5000, 'VEV_5100': 5100, 'VEV_5200': 5200, 'VEV_5300': 5300, 'VEV_5400': 5400, 'VEV_5500': 5500, 'VEV_6000': 6000, 'VEV_6500': 6500}
    PRODUCTS = [HYDROGEL_PRODUCT, UNDERLYING] + list(OPTIONS)
    POSITION_LIMITS = {HYDROGEL_PRODUCT: 200, UNDERLYING: 200, **{product: 300 for product in OPTIONS}}
    ENABLE_HYDROGEL = True
    ENABLE_OPTIONS = True
    ENABLE_ZERO_BID = True
    ENABLE_SMILE_PASSIVE = True
    ENABLE_SMILE_ACTIVE = True
    ENABLE_PASSIVE_MM = True
    ENABLE_DELTA_SKEW = True
    ENABLE_RESIDUAL_Z_FILTER = True
    ENABLE_DYNAMIC_SMILE_SIZE = True
    ENABLE_IV_CARRY = True
    ENABLE_UNDERLYING_MR = True
    ENABLE_RESEARCH_LOGS = True
    ENABLE_DEAD_QUOTE_FILTER = False
    ENABLE_PUBLIC_FLOW_FADE = True
    ENABLE_MARK_PASSIVE_BIAS = True
    ENABLE_UNDERLYING_MARK_CALL_BIAS = True
    LIVE_TTE_DAYS = 5.0
    AUTO_TTE = False
    HISTORICAL_DAY0_TTE = 8.0
    DAY_TIMESTAMP_STRIDE = 1000000.0
    TTE_CANDIDATES = (4.0, 5.0, 6.0, 7.0, 8.0)
    SMILE_PRODUCTS = ('VEV_5000', 'VEV_5100', 'VEV_5200', 'VEV_5300', 'VEV_5400', 'VEV_5500')
    ZERO_BID_PRODUCTS = ('VEV_6000', 'VEV_6500')
    ZERO_BID_SIZE = 300
    ZERO_BID_MAX_POS = 300
    ZERO_ASK_SIZE = 45
    MM_CONFIG = {UNDERLYING: {'enabled': False, 'size': 12, 'soft': 90, 'hard': 160, 'min_spread': 2, 'min_edge': 1.0, 'skew': 0.025, 'fair': 'wall_mid'}, 'VEV_4000': {'size': 26, 'soft': 220, 'hard': 295, 'min_spread': 4, 'min_edge': 0.0, 'skew': 0.035, 'fair': 'parity'}, 'VEV_4500': {'size': 18, 'soft': 165, 'hard': 260, 'min_spread': 4, 'min_edge': 2.0, 'skew': 0.03, 'fair': 'parity'}, 'VEV_5000': {'enabled': False, 'size': 12, 'soft': 120, 'hard': 190, 'min_spread': 3, 'min_edge': 1.2, 'skew': 0.02, 'fair': 'book_mid'}, 'VEV_5100': {'enabled': False, 'size': 11, 'soft': 110, 'hard': 180, 'min_spread': 3, 'min_edge': 1.2, 'skew': 0.02, 'fair': 'book_mid'}, 'VEV_5200': {'enabled': False, 'size': 10, 'soft': 100, 'hard': 165, 'min_spread': 3, 'min_edge': 1.2, 'skew': 0.02, 'fair': 'book_mid'}, 'VEV_5300': {'enabled': True, 'size': 5, 'soft': 65, 'hard': 110, 'min_spread': 2, 'min_edge': 0.7, 'skew': 0.02, 'fair': 'smile'}, 'VEV_5400': {'enabled': False, 'size': 6, 'soft': 80, 'hard': 130, 'min_spread': 1, 'min_edge': 0.4, 'skew': 0.018, 'fair': 'smile'}, 'VEV_5500': {'enabled': True, 'size': 8, 'soft': 110, 'hard': 180, 'min_spread': 1, 'min_edge': 0.3, 'skew': 0.018, 'fair': 'smile'}}
    SCALP_PRODUCTS = ('VEV_5300',)
    WATCH_PRODUCTS = ('VEV_5000', 'VEV_5100', 'VEV_5200', 'VEV_5400', 'VEV_5500')
    FILTERED_SMILE_TRADE_PRODUCTS = SMILE_PRODUCTS
    ACTIVE_PRODUCTS = ('VEV_5300', 'VEV_5400', 'VEV_5500')
    PASSIVE_BASE_SIZE = {'VEV_5000': 18, 'VEV_5100': 16, 'VEV_5200': 14, 'VEV_5300': 10, 'VEV_5400': 8, 'VEV_5500': 14}
    ACTIVE_BASE_SIZE = {'VEV_5000': 4, 'VEV_5100': 4, 'VEV_5200': 5, 'VEV_5300': 30, 'VEV_5400': 20, 'VEV_5500': 30}
    LONG_TARGET = {'VEV_5000': 0, 'VEV_5100': 0, 'VEV_5200': 0, 'VEV_5300': 70, 'VEV_5400': 0, 'VEV_5500': 90}
    SHORT_TARGET = {'VEV_5000': 220, 'VEV_5100': 280, 'VEV_5200': 300, 'VEV_5300': 300, 'VEV_5400': 300, 'VEV_5500': 300}
    MIN_MODEL_EDGE = {'VEV_5000': 8.0, 'VEV_5100': 8.0, 'VEV_5200': 8.0, 'VEV_5300': 2.2, 'VEV_5400': 8.0, 'VEV_5500': 1.2}
    MIN_BUY_MODEL_EDGE = {'VEV_5000': 8.0, 'VEV_5100': 8.0, 'VEV_5200': 8.0, 'VEV_5300': 0.7, 'VEV_5400': 8.0, 'VEV_5500': 0.7}
    MIN_SELL_MODEL_EDGE = {'VEV_5000': 0.6, 'VEV_5100': 0.5, 'VEV_5200': 0.3, 'VEV_5300': 0.3, 'VEV_5400': 0.3, 'VEV_5500': 0.3}
    ACTIVE_EDGE_MULT = 0.45
    ACTIVE_SPREAD_FRACTION = 0.15
    FLOW_FADE_PRODUCTS = ('VEV_5300', 'VEV_5500')
    FLOW_FADE_DECAY = 0.65
    FLOW_FADE_CAP = 30.0
    FLOW_FADE_BASE_SIZE = 5
    FLOW_FADE_MAX_SIZE = 14
    MARK_SIGNAL_DECAY = 0.72
    MARK_SIGNAL_CAP = 30.0
    MARK_OTM_BID_PRODUCTS = ('VEV_5500',)
    MARK_OTM_SIGNAL_SELLERS = ('Mark 22',)
    MARK_OTM_CONFIRMING_BUYERS = ('Mark 01',)
    MARK_OTM_BID_SIZE = {'VEV_5400': 12, 'VEV_5500': 14}
    MARK_OTM_BID_HARD = {'VEV_5400': 240, 'VEV_5500': 280}
    MARK_OTM_BID_MIN_EDGE = {'VEV_5400': 0.2, 'VEV_5500': 0.0}
    MARK_OTM_DEPTH_TRIGGER = {'VEV_5400': -0.02, 'VEV_5500': -0.02}
    MARK_OTM_STATE_BID_SIZE = {'VEV_5400': 18, 'VEV_5500': 22}
    UNDERLYING_MARKS = ('Mark 14', 'Mark 67')
    UNDERLYING_MARK_SIGNAL_DECAY = 0.72
    UNDERLYING_MARK_SIGNAL_CAP = 80.0
    UNDERLYING_MARK_CALL_THRESHOLD = 6.0
    UNDERLYING_MARK_CALL_STRONG = 22.0
    UNDERLYING_MARK_CALL_PRODUCTS = ('VEV_5000', 'VEV_5100', 'VEV_5200')
    UNDERLYING_MARK_CALL_SHORT_TARGET = {'VEV_5000': 45, 'VEV_5100': 55, 'VEV_5200': 85}
    UNDERLYING_MARK_CALL_BASE_SIZE = {'VEV_5000': 4, 'VEV_5100': 5, 'VEV_5200': 8}
    UNDERLYING_MARK_CALL_MAX_SIZE = {'VEV_5000': 10, 'VEV_5100': 12, 'VEV_5200': 18}
    UNDERLYING_MARK_CALL_MODEL_ALLOWANCE = {'VEV_5000': 6.0, 'VEV_5100': 5.0, 'VEV_5200': 4.0}
    EXIT_EDGE = {'VEV_5000': 1.5, 'VEV_5100': 1.2, 'VEV_5200': 0.8, 'VEV_5300': 0.7, 'VEV_5400': 0.5, 'VEV_5500': 0.4}
    DELTA_SKEW_CAP = 250.0
    RESIDUAL_HISTORY_MIN = 12
    RESIDUAL_Z_ENTRY = 1.15
    RESIDUAL_Z_STRONG = 2.25
    ACTIVE_RESIDUAL_Z_ENTRY = 1.75
    IV_Z_ENTRY = 1.2
    HISTORY_LIMIT = 80
    UNDERLYING_MR_HISTORY_LIMIT = 220
    UNDERLYING_MR_MIN_HISTORY = 80
    UNDERLYING_MR_SPAN = 160
    UNDERLYING_MR_Z_ENTRY = 2.0
    UNDERLYING_MR_TARGET = 60
    UNDERLYING_MR_SIZE = 10
    UNDERLYING_MR_MIN_EDGE = 2.0
    OPTION_SHORT_TREND_MIN_HISTORY = 24
    OPTION_SHORT_TREND_LOOKBACK = 64
    OPTION_SHORT_TREND_WARN = 8.0
    OPTION_SHORT_TREND_HARD = 24.0
    OPTION_SHORT_TREND_MIN_SCALE = 0.0
    BULL_CALL_PROBE_PRODUCTS = ('VEV_5000', 'VEV_5100', 'VEV_5200', 'VEV_5300', 'VEV_5400')
    BULL_CALL_PROBE_LONG_CAP = {'VEV_5000': 110, 'VEV_5100': 130, 'VEV_5200': 150, 'VEV_5300': 150, 'VEV_5400': 90}
    BULL_CALL_PROBE_SIZE = {'VEV_5000': 8, 'VEV_5100': 10, 'VEV_5200': 12, 'VEV_5300': 12, 'VEV_5400': 10}
    BULL_CALL_PROBE_MODEL_ALLOWANCE = {'VEV_5000': 3.0, 'VEV_5100': 2.5, 'VEV_5200': 2.0, 'VEV_5300': 1.5, 'VEV_5400': 1.0}
    OPTION_UPTREND_RECYCLE_TRIGGER_SCALE = 0.25
    OPTION_UPTREND_RECYCLE_SIZE = {'VEV_5000': 5, 'VEV_5100': 6, 'VEV_5200': 6, 'VEV_5300': 4, 'VEV_5400': 4}
    OPTION_UPTREND_RECYCLE_MIN_SHORT = {'VEV_5000': 80, 'VEV_5100': 90, 'VEV_5200': 90, 'VEV_5300': 120, 'VEV_5400': 120}
    OPTION_UPTREND_RECYCLE_MODEL_ALLOWANCE = {'VEV_5000': 2.0, 'VEV_5100': 2.0, 'VEV_5200': 1.5, 'VEV_5300': 1.0, 'VEV_5400': 0.75}
    HYDROGEL_LOWER_EXTREME = 9950.0
    HYDROGEL_UPPER_EXTREME = 10027.0
    HYDROGEL_BASE_TARGET = 80
    HYDROGEL_TIER_STEP = 35
    HYDROGEL_TIER_SPACING = 10.0
    HYDROGEL_MAX_LONG_TARGET = 200
    HYDROGEL_MAX_SHORT_TARGET = 200
    HYDROGEL_CORE_TARGET = 20
    HYDROGEL_RECYCLE_TRIGGER = 190
    HYDROGEL_RECYCLE_TARGET = 170
    HYDROGEL_RECYCLE_RETRACE = 12.0
    HYDROGEL_RECYCLE_MAX_QTY = 6
    HYDROGEL_EXIT_RETRACE = HYDROGEL_UPPER_EXTREME - HYDROGEL_LOWER_EXTREME
    HYDROGEL_SHORT_EXIT_LEVEL = 9996.0
    HYDROGEL_STATIC_CENTER = (HYDROGEL_LOWER_EXTREME + HYDROGEL_UPPER_EXTREME) / 2.0
    HYDROGEL_LOWER_EXTREME_OFFSET = HYDROGEL_LOWER_EXTREME - HYDROGEL_STATIC_CENTER
    HYDROGEL_UPPER_EXTREME_OFFSET = HYDROGEL_UPPER_EXTREME - HYDROGEL_STATIC_CENTER
    HYDROGEL_SHORT_EXIT_OFFSET = HYDROGEL_SHORT_EXIT_LEVEL - HYDROGEL_STATIC_CENTER
    HYDROGEL_ANCHOR_MIN_HISTORY = 120
    HYDROGEL_ANCHOR_LOOKBACK = 400
    HYDROGEL_ANCHOR_TRIM_FRACTION = 0.1
    HYDROGEL_ANCHOR_SHIFT_TRIGGER = 95.0
    HYDROGEL_ANCHOR_RELEASE_TRIGGER = 70.0
    HYDROGEL_ANCHOR_CONFIRM_SAMPLES = 100
    HYDROGEL_LOWER_SWEEP_LEVELS = 1
    HYDROGEL_UPPER_SWEEP_LEVELS = 1
    HYDROGEL_MAX_LOWER_SWEEP_QTY = 120
    HYDROGEL_MAX_UPPER_SWEEP_QTY = 5
    HYDROGEL_MAX_TRIM_QTY = 20
    HYDROGEL_EXTREME_PASSIVE_SIZE = 12
    HYDROGEL_LOWER_ACTIVE_ENTRY_TIER = 0
    HYDROGEL_UPPER_ACTIVE_ENTRY_TIER = 0
    HYDROGEL_PASSIVE_SIZE = 12
    HYDROGEL_PASSIVE_EDGE = 3.0
    HYDROGEL_PASSIVE_INVENTORY_LIMIT = 200
    HYDROGEL_PASSIVE_SKEW_LIMIT = 200
    HYDROGEL_MARK38_REPEAT_TTL = 500
    HYDROGEL_MARK38_EXTRA_PASSIVE_SIZE = 8
    HYDROGEL_MARK38_EXTREME_TTL = 2000
    HYDROGEL_MARK38_EXTREME_EXTRA_PASSIVE_SIZE = 12
    HYDROGEL_MARK38_POSITION_SOFT_LIMIT = 180
    HYDROGEL_SIGNAL_HISTORY_LIMIT = 400
    HYDROGEL_SIGNAL_ANCHOR_LENGTH = 20
    HYDROGEL_SIGNAL_WALL_WEIGHT = 0.7
    HYDROGEL_SIGNAL_TOP_WEIGHT = 0.2
    HYDROGEL_SIGNAL_ANCHOR_WEIGHT = 0.1
    HYDROGEL_DYNAMIC_LOW_MIN_HISTORY = 120
    HYDROGEL_DYNAMIC_LOW_LOOKBACK = 240
    HYDROGEL_DYNAMIC_LOW_MIN_STD = 8.0
    HYDROGEL_DYNAMIC_LOW_Z = 2.5
    HYDROGEL_DYNAMIC_LOW_BOUNCE_LOOKBACK = 8
    HYDROGEL_DYNAMIC_LOW_BOUNCE = 0.5
    HYDROGEL_DYNAMIC_LOW_TARGET = 140
    HYDROGEL_UPTREND_RECYCLE_TRIGGER = 120
    HYDROGEL_UPTREND_RECYCLE_LOOKBACK = 45
    HYDROGEL_UPTREND_RECYCLE_RISE = 8.0
    HYDROGEL_UPTREND_RECYCLE_SIZE = 8
    HYDROGEL_UPTREND_RECYCLE_EDGE = 1.0

    def run(self, state):
        saved = self.load_trader_data(state.traderData)
        result = {}
        snapshots = self.build_snapshots(state.order_depths)
        orders_by_product = {product: [] for product in self.PRODUCTS}
        underlying = snapshots.get(self.UNDERLYING)
        spot = underlying['mid'] if underlying and underlying['mid'] is not None else None
        smile = self.fit_best_smile(snapshots, spot, state.timestamp) if self.ENABLE_OPTIONS else None
        if smile is not None:
            self.annotate_smile_state(saved, snapshots, smile)
        if self.ENABLE_HYDROGEL:
            self.trade_hydrogel(state, snapshots, saved, orders_by_product)
        if self.ENABLE_OPTIONS and self.ENABLE_UNDERLYING_MR:
            self.trade_underlying_mean_reversion(state, snapshots, saved, smile, orders_by_product)
        if self.ENABLE_OPTIONS and self.ENABLE_PUBLIC_FLOW_FADE:
            self.trade_public_flow_fade(state, snapshots, saved, smile, orders_by_product)
        if self.ENABLE_OPTIONS and self.ENABLE_MARK_PASSIVE_BIAS and (smile is not None):
            self.trade_mark_passive_bias(state, snapshots, saved, smile, orders_by_product)
        if self.ENABLE_OPTIONS:
            self.trade_deeper_option_short_probe(state, snapshots, saved, orders_by_product)
            self.trade_vev5200_probe(state, snapshots, saved, orders_by_product)
            self.trade_vev5400_probe(state, snapshots, saved, orders_by_product)
            if smile is not None:
                self.trade_option_uptrend_recycle(state, snapshots, saved, smile, orders_by_product)
        if self.ENABLE_OPTIONS and self.ENABLE_UNDERLYING_MARK_CALL_BIAS and (smile is not None):
            self.trade_underlying_mark_call_bias(state, snapshots, saved, smile, orders_by_product)
        if self.ENABLE_OPTIONS and self.ENABLE_PASSIVE_MM:
            self.trade_passive_market_making(state, snapshots, smile, orders_by_product)
        if self.ENABLE_OPTIONS and smile is not None:
            self.trade_bullish_call_probe(state, snapshots, saved, smile, orders_by_product)
            if self.ENABLE_SMILE_PASSIVE or self.ENABLE_SMILE_ACTIVE:
                self.trade_smile_residuals(state, snapshots, smile, orders_by_product)
            if self.ENABLE_ZERO_BID:
                self.trade_zero_bid_lottery(state, snapshots, smile, orders_by_product)
            if self.ENABLE_IV_CARRY:
                self.trade_iv_carry(state, snapshots, smile, orders_by_product)
        if self.ENABLE_OPTIONS and self.ENABLE_PUBLIC_FLOW_FADE:
            self.update_public_flow_fade_signals(state, snapshots, saved)
        if self.ENABLE_OPTIONS and self.ENABLE_MARK_PASSIVE_BIAS:
            self.update_mark_signals(state, saved)
        if self.ENABLE_OPTIONS and self.ENABLE_UNDERLYING_MARK_CALL_BIAS:
            self.update_underlying_mark_signal(state, saved)
        flat_orders = {}
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
        return (result, 0, trader_data)

    def classify_public_trade_side(self, trade, snap):
        ask = snap.get('ask')
        bid = snap.get('bid')
        mid = snap.get('mid')
        if ask is not None and trade.price >= ask:
            return 'BUY'
        if bid is not None and trade.price <= bid:
            return 'SELL'
        if mid is not None and trade.price >= mid:
            return 'BUY'
        return 'SELL'

    def trade_hydrogel(self, state, snapshots, saved, orders_by_product):
        product = self.HYDROGEL_PRODUCT
        snap = snapshots.get(product)
        if snap is None or snap['bid'] is None or snap['ask'] is None or (snap['mid'] is None):
            return
        fair = snap['wall_mid'] if snap['wall_mid'] is not None else snap['mid']
        signal_fair = self.hydrogel_signal_fair(saved, snap['mid'], snap['wall_mid'], fair)
        if signal_fair is None:
            return
        levels_info = self.hydrogel_adaptive_levels(signal_fair, saved)
        self.hydrogel_store_anchor_info(saved, levels_info)
        mark38_signal, mark38_extra_size = self.hydrogel_recent_mark38_signal(saved, state.timestamp)
        position = state.position.get(product, 0)
        target = position
        max_qty = 0
        levels = 1
        reason = 'hold'
        tier_target, tier, side = self.hydrogel_tier_target(signal_fair, levels_info)
        dynamic_low_target = self.hydrogel_dynamic_low_target(signal_fair, saved, levels_info)
        if side == 'lower' and dynamic_low_target is not None:
            tier_target = max(tier_target or 0, dynamic_low_target)
        active_entry_tier = self.hydrogel_active_entry_tier(side)
        if side in ('lower', 'upper') and tier < active_entry_tier:
            quote = self.hydrogel_extreme_passive_quote(product, position, snap, fair, signal_fair, tier_target, side, levels_info)
            if quote is not None:
                order, meta = quote
                orders_by_product[product].append((order, meta['reason'], meta))
            self.hydrogel_update_mark38_signal(state, saved, signal_fair)
            return
        if side == 'lower' and tier_target is not None and (position < tier_target):
            target = tier_target
            max_qty = self.HYDROGEL_MAX_LOWER_SWEEP_QTY
            levels = self.HYDROGEL_LOWER_SWEEP_LEVELS
            reason = 'lower_tier_%d_add_long' % tier
        elif side == 'upper' and tier_target is not None and (position > tier_target):
            target = tier_target
            max_qty = self.HYDROGEL_MAX_UPPER_SWEEP_QTY
            levels = self.HYDROGEL_UPPER_SWEEP_LEVELS
            reason = 'upper_tier_%d_add_short' % tier
        elif position > self.HYDROGEL_RECYCLE_TRIGGER and fair >= levels_info['lower'] + self.HYDROGEL_RECYCLE_RETRACE:
            target = self.HYDROGEL_RECYCLE_TARGET
            max_qty = self.HYDROGEL_RECYCLE_MAX_QTY
            levels = 1
            reason = 'light_recycle_long_after_lower_retrace'
        elif position < -self.HYDROGEL_RECYCLE_TRIGGER and fair <= levels_info['upper'] - self.HYDROGEL_RECYCLE_RETRACE:
            target = -self.HYDROGEL_RECYCLE_TARGET
            max_qty = self.HYDROGEL_RECYCLE_MAX_QTY
            levels = 1
            reason = 'light_recycle_short_after_upper_retrace'
        elif position > self.HYDROGEL_CORE_TARGET and fair >= levels_info['lower'] + self.HYDROGEL_EXIT_RETRACE:
            target = self.HYDROGEL_CORE_TARGET
            max_qty = self.HYDROGEL_MAX_TRIM_QTY
            levels = 1
            reason = 'trim_long_after_retrace'
        elif position < -self.HYDROGEL_CORE_TARGET and fair <= levels_info['short_exit']:
            target = -self.HYDROGEL_CORE_TARGET
            max_qty = self.HYDROGEL_MAX_TRIM_QTY
            levels = 1
            reason = 'trim_short_profit_take'
        detailed = []
        diff = target - position
        if diff > 0:
            qty = min(diff, max_qty, self.POSITION_LIMITS[product] - position)
            detailed = self.hydrogel_buy_through_levels(product, snap, qty, levels, fair, signal_fair, target, reason, levels_info)
        elif diff < 0:
            qty = min(-diff, max_qty, self.POSITION_LIMITS[product] + position)
            detailed = self.hydrogel_sell_through_levels(product, snap, qty, levels, fair, signal_fair, target, reason, levels_info)
        if not detailed:
            recycle = self.hydrogel_uptrend_recycle_quote(product, position, snap, fair, signal_fair, saved, levels_info)
            if recycle is not None:
                detailed = [recycle]
            else:
                detailed = self.hydrogel_passive_quotes(product, position, snap, fair, signal_fair, levels_info, mark38_signal, mark38_extra_size)
        for order, meta in detailed:
            orders_by_product[product].append((order, meta['reason'], meta))
        self.hydrogel_update_mark38_signal(state, saved, signal_fair)

    def hydrogel_adaptive_levels(self, signal_fair, saved):
        history = saved.get('hydrogel_fair_history', [])
        ready = len(history) >= self.HYDROGEL_ANCHOR_MIN_HISTORY
        center = self.HYDROGEL_STATIC_CENTER
        candidate_center = self.HYDROGEL_STATIC_CENTER
        mode = 'static'
        if ready:
            sample = history[-self.HYDROGEL_ANCHOR_LOOKBACK:]
            if len(sample) >= 10:
                ordered = sorted(sample)
                trim = int(len(ordered) * self.HYDROGEL_ANCHOR_TRIM_FRACTION)
                if trim > 0 and len(ordered) > 2 * trim:
                    ordered = ordered[trim:-trim]
                candidate_center = sum(ordered) / len(ordered)
        shift = abs(candidate_center - self.HYDROGEL_STATIC_CENTER)
        active = bool(saved.get('hydrogel_adaptive_active', False))
        shift_count = int(saved.get('hydrogel_anchor_shift_count', 0) or 0)
        release_count = int(saved.get('hydrogel_anchor_release_count', 0) or 0)
        if ready and shift >= self.HYDROGEL_ANCHOR_SHIFT_TRIGGER:
            shift_count += 1
        else:
            shift_count = 0
        if active:
            if ready and shift <= self.HYDROGEL_ANCHOR_RELEASE_TRIGGER:
                release_count += 1
            else:
                release_count = 0
            if release_count >= self.HYDROGEL_ANCHOR_CONFIRM_SAMPLES:
                active = False
                shift_count = 0
        elif shift_count >= self.HYDROGEL_ANCHOR_CONFIRM_SAMPLES:
            active = True
            release_count = 0
        if active:
            center = candidate_center
            mode = 'adaptive_fallback'
        elif ready and shift_count > 0:
            mode = 'static_watch'
        saved['hydrogel_adaptive_active'] = active
        saved['hydrogel_anchor_shift_count'] = shift_count
        saved['hydrogel_anchor_release_count'] = release_count
        return {'center': center, 'candidate_center': candidate_center, 'candidate_shift': shift, 'lower': center + self.HYDROGEL_LOWER_EXTREME_OFFSET, 'upper': center + self.HYDROGEL_UPPER_EXTREME_OFFSET, 'short_exit': center + self.HYDROGEL_SHORT_EXIT_OFFSET, 'ready': ready, 'mode': mode}

    def hydrogel_store_anchor_info(self, saved, levels_info):
        if levels_info is None:
            return
        saved['last_hydrogel_anchor'] = levels_info['center']
        saved['last_hydrogel_candidate_anchor'] = levels_info['candidate_center']
        saved['last_hydrogel_anchor_shift'] = levels_info['candidate_shift']
        saved['last_hydrogel_lower'] = levels_info['lower']
        saved['last_hydrogel_upper'] = levels_info['upper']
        saved['last_hydrogel_anchor_mode'] = levels_info['mode']

    def hydrogel_active_entry_tier(self, side):
        if side == 'lower':
            return self.HYDROGEL_LOWER_ACTIVE_ENTRY_TIER
        if side == 'upper':
            return self.HYDROGEL_UPPER_ACTIVE_ENTRY_TIER
        return 0

    def hydrogel_tier_target(self, fair, levels_info):
        lower = levels_info['lower']
        upper = levels_info['upper']
        if fair <= lower:
            tier = int((lower - fair) // self.HYDROGEL_TIER_SPACING)
            magnitude = self.HYDROGEL_BASE_TARGET + self.HYDROGEL_TIER_STEP * tier
            return (min(self.HYDROGEL_MAX_LONG_TARGET, magnitude), tier, 'lower')
        if fair >= upper:
            tier = int((fair - upper) // self.HYDROGEL_TIER_SPACING)
            magnitude = self.HYDROGEL_BASE_TARGET + self.HYDROGEL_TIER_STEP * tier
            return (-min(self.HYDROGEL_MAX_SHORT_TARGET, magnitude), tier, 'upper')
        return (None, 0, '')

    def hydrogel_dynamic_low_target(self, signal_fair, saved, levels_info):
        if signal_fair > levels_info['lower'] - self.HYDROGEL_TIER_SPACING:
            return None
        history = saved.get('hydrogel_fair_history', [])
        if len(history) < self.HYDROGEL_DYNAMIC_LOW_MIN_HISTORY:
            return None
        sample = history[-self.HYDROGEL_DYNAMIC_LOW_LOOKBACK:]
        avg = sum(sample) / len(sample)
        variance = sum(((value - avg) ** 2 for value in sample)) / len(sample)
        std = variance ** 0.5
        if std < self.HYDROGEL_DYNAMIC_LOW_MIN_STD:
            return None
        z_score = (avg - signal_fair) / std
        if z_score < self.HYDROGEL_DYNAMIC_LOW_Z:
            return None
        recent = history[-self.HYDROGEL_DYNAMIC_LOW_BOUNCE_LOOKBACK:]
        if recent and signal_fair < min(recent) + self.HYDROGEL_DYNAMIC_LOW_BOUNCE:
            return None
        return self.HYDROGEL_DYNAMIC_LOW_TARGET

    def hydrogel_signal_fair(self, saved, mid, wall_mid, fair):
        if fair is None:
            return None
        if mid is None or wall_mid is None:
            return fair
        if abs(wall_mid - mid) <= 1.0:
            return wall_mid
        history = saved.get('hydrogel_fair_history', [])
        if len(history) < 6:
            anchor = mid
        else:
            recent = history[-self.HYDROGEL_SIGNAL_ANCHOR_LENGTH:]
            anchor = sum(recent) / len(recent)
        return self.HYDROGEL_SIGNAL_WALL_WEIGHT * wall_mid + self.HYDROGEL_SIGNAL_TOP_WEIGHT * mid + self.HYDROGEL_SIGNAL_ANCHOR_WEIGHT * anchor

    def hydrogel_buy_through_levels(self, product, snap, quantity, levels, fair, signal_fair, target, reason, levels_info):
        detailed = []
        remaining = max(0, quantity)
        for price, volume in snap['asks'][:levels]:
            if remaining <= 0:
                break
            qty = min(remaining, volume)
            if qty > 0:
                order = Order(product, price, qty)
                detailed.append((order, self.hydrogel_meta(product, reason, price, qty, snap, fair, signal_fair, target, levels_info)))
                remaining -= qty
        return detailed

    def hydrogel_sell_through_levels(self, product, snap, quantity, levels, fair, signal_fair, target, reason, levels_info):
        detailed = []
        remaining = max(0, quantity)
        for price, volume in snap['bids'][:levels]:
            if remaining <= 0:
                break
            qty = min(remaining, volume)
            if qty > 0:
                order = Order(product, price, -qty)
                detailed.append((order, self.hydrogel_meta(product, reason, price, -qty, snap, fair, signal_fair, target, levels_info)))
                remaining -= qty
        return detailed

    def hydrogel_extreme_passive_quote(self, product, position, snap, fair, signal_fair, target, side, levels_info):
        if target is None or not snap['bids'] or (not snap['asks']):
            return None
        bid_price, ask_price = self.hydrogel_passive_prices(snap, fair)
        if bid_price is None or ask_price is None:
            return None
        if side == 'lower' and position < target:
            capacity = min(self.HYDROGEL_EXTREME_PASSIVE_SIZE, target - position, self.POSITION_LIMITS[product] - position)
            if capacity > 0 and bid_price < snap['ask'] and (fair - bid_price >= self.HYDROGEL_PASSIVE_EDGE):
                order = Order(product, bid_price, capacity)
                meta = self.hydrogel_meta(product, '%s_tier_passive_probe' % side, bid_price, capacity, snap, fair, signal_fair, target, levels_info)
                return (order, meta)
        if side == 'upper' and position > target:
            capacity = min(self.HYDROGEL_EXTREME_PASSIVE_SIZE, position - target, self.POSITION_LIMITS[product] + position)
            if capacity > 0 and ask_price > snap['bid'] and (ask_price - fair >= self.HYDROGEL_PASSIVE_EDGE):
                order = Order(product, ask_price, -capacity)
                meta = self.hydrogel_meta(product, '%s_tier_passive_probe' % side, ask_price, -capacity, snap, fair, signal_fair, target, levels_info)
                return (order, meta)
        return None

    def hydrogel_passive_quotes(self, product, position, snap, fair, signal_fair, levels_info, mark38_signal=0, mark38_extra_size=0):
        if not snap['bids'] or not snap['asks']:
            return []
        if fair <= levels_info['lower'] or fair >= levels_info['upper']:
            return []
        if abs(position) > self.HYDROGEL_PASSIVE_INVENTORY_LIMIT:
            return []
        bid_price, ask_price = self.hydrogel_passive_prices(snap, fair)
        if bid_price is None or ask_price is None or bid_price >= ask_price:
            return []
        detailed = []
        buy_size = self.HYDROGEL_PASSIVE_SIZE + (mark38_extra_size if mark38_signal < 0 else 0)
        sell_size = self.HYDROGEL_PASSIVE_SIZE + (mark38_extra_size if mark38_signal > 0 else 0)
        buy_limit = self.HYDROGEL_MARK38_POSITION_SOFT_LIMIT if mark38_signal < 0 else self.HYDROGEL_PASSIVE_INVENTORY_LIMIT
        sell_limit = self.HYDROGEL_MARK38_POSITION_SOFT_LIMIT if mark38_signal > 0 else self.HYDROGEL_PASSIVE_INVENTORY_LIMIT
        buy_capacity = min(buy_size, buy_limit - position)
        sell_capacity = min(sell_size, sell_limit + position)
        if position > self.HYDROGEL_PASSIVE_SKEW_LIMIT:
            buy_capacity = 0
        if position < -self.HYDROGEL_PASSIVE_SKEW_LIMIT:
            sell_capacity = 0
        if buy_capacity > 0 and bid_price < snap['ask'] and (fair - bid_price >= self.HYDROGEL_PASSIVE_EDGE):
            order = Order(product, bid_price, buy_capacity)
            meta = self.hydrogel_meta(product, 'passive_wall_edge', bid_price, buy_capacity, snap, fair, signal_fair, position, levels_info)
            if mark38_signal < 0:
                meta['reason'] = 'mark38_repeat_bid'
                meta['mark38_signal'] = mark38_signal
                meta['mark38_extra'] = mark38_extra_size
            detailed.append((order, meta))
        if sell_capacity > 0 and ask_price > snap['bid'] and (ask_price - fair >= self.HYDROGEL_PASSIVE_EDGE):
            order = Order(product, ask_price, -sell_capacity)
            meta = self.hydrogel_meta(product, 'passive_wall_edge', ask_price, -sell_capacity, snap, fair, signal_fair, position, levels_info)
            if mark38_signal > 0:
                meta['reason'] = 'mark38_repeat_ask'
                meta['mark38_signal'] = mark38_signal
                meta['mark38_extra'] = mark38_extra_size
            detailed.append((order, meta))
        return detailed

    def hydrogel_uptrend_recycle_quote(self, product, position, snap, fair, signal_fair, saved, levels_info):
        if position >= -self.HYDROGEL_UPTREND_RECYCLE_TRIGGER:
            return None
        history = saved.get('hydrogel_fair_history', [])
        if len(history) < self.HYDROGEL_UPTREND_RECYCLE_LOOKBACK:
            return None
        recent = history[-self.HYDROGEL_UPTREND_RECYCLE_LOOKBACK:]
        if signal_fair - recent[0] < self.HYDROGEL_UPTREND_RECYCLE_RISE:
            return None
        if not snap['bids'] or not snap['asks']:
            return None
        price = int(snap['bid'] + 2)
        if price >= snap['ask']:
            price = int(snap['ask'] - 1)
        if price <= snap['bid']:
            price = int(snap['bid'])
        if price >= snap['ask'] or fair - price < self.HYDROGEL_UPTREND_RECYCLE_EDGE:
            return None
        qty = min(self.HYDROGEL_UPTREND_RECYCLE_SIZE, -position, self.POSITION_LIMITS[product] - position)
        if qty <= 0:
            return None
        meta = self.hydrogel_meta(product, 'uptrend_short_recycle_bid', price, qty, snap, fair, signal_fair, position, levels_info)
        return (Order(product, price, qty), meta)

    def hydrogel_recent_mark38_signal(self, saved, timestamp):
        sign = int(saved.get('hydrogel_mark38_sign', 0) or 0)
        last_ts = saved.get('hydrogel_mark38_timestamp')
        if sign == 0 or last_ts is None:
            return (0, 0)
        age = timestamp - int(last_ts)
        last_pct = saved.get('hydrogel_mark38_rolling_pct')
        if last_pct is not None:
            pct = float(last_pct)
            if pct >= 0.9:
                return (0, 0)
            if age <= self.HYDROGEL_MARK38_EXTREME_TTL and (pct <= 0.1 or 0.75 <= pct <= 0.9):
                return (sign, self.HYDROGEL_MARK38_EXTREME_EXTRA_PASSIVE_SIZE)
        if age > self.HYDROGEL_MARK38_REPEAT_TTL:
            return (0, 0)
        return (sign, self.HYDROGEL_MARK38_EXTRA_PASSIVE_SIZE)

    def hydrogel_update_mark38_signal(self, state, saved, signal_fair):
        net = 0
        for trade in state.market_trades.get(self.HYDROGEL_PRODUCT, []):
            qty = int(getattr(trade, 'quantity', 0) or 0)
            if getattr(trade, 'buyer', None) == 'Mark 38':
                net += qty
            if getattr(trade, 'seller', None) == 'Mark 38':
                net -= qty
        if net == 0:
            return
        saved['hydrogel_mark38_sign'] = 1 if net > 0 else -1
        saved['hydrogel_mark38_quantity'] = abs(net)
        saved['hydrogel_mark38_timestamp'] = int(state.timestamp)
        history = saved.get('hydrogel_fair_history', [])
        if len(history) >= 25:
            below = sum((1 for value in history if value < signal_fair))
            equal = sum((1 for value in history if value == signal_fair))
            saved['hydrogel_mark38_rolling_pct'] = (below + 0.5 * equal) / len(history)
        else:
            saved['hydrogel_mark38_rolling_pct'] = 0.5

    def hydrogel_passive_prices(self, snap, fair):
        bid_price = int(snap['bids'][-1][0] + 1)
        ask_price = int(snap['asks'][-1][0] - 1)
        for price, volume in snap['bids']:
            overbid = price + 1
            if volume > 1 and overbid < fair:
                bid_price = max(bid_price, overbid)
                break
            if price < fair:
                bid_price = max(bid_price, price)
                break
        for price, volume in snap['asks']:
            undercut = price - 1
            if volume > 1 and undercut > fair:
                ask_price = min(ask_price, undercut)
                break
            if price > fair:
                ask_price = min(ask_price, price)
                break
        if bid_price >= fair or ask_price <= fair:
            return (None, None)
        return (bid_price, ask_price)

    def hydrogel_meta(self, product, reason, price, quantity, snap, fair, signal_fair, target, levels_info=None):
        extra = {'signal_fair': signal_fair, 'target': target}
        if levels_info is not None:
            extra.update({'anchor': levels_info['center'], 'candidate_anchor': levels_info['candidate_center'], 'anchor_shift': levels_info['candidate_shift'], 'lower_extreme': levels_info['lower'], 'upper_extreme': levels_info['upper'], 'anchor_mode': levels_info['mode'], 'anchor_ready': levels_info['ready']})
        return self.quote_meta(product, reason, int(price), int(quantity), snap, fair, None, extra)

    def trade_public_flow_fade(self, state, snapshots, saved, smile, orders_by_product):
        for product in self.FLOW_FADE_PRODUCTS:
            snap = snapshots.get(product)
            if snap is None or snap['bid'] is None or snap['ask'] is None or (snap['mid'] is None):
                continue
            signal = float(saved.get('flow_fade_%s' % product, 0.0) or 0.0)
            if abs(signal) < 1.0:
                continue
            position = state.position.get(product, 0)
            long_cap = self.LONG_TARGET.get(product, 50)
            short_cap = self.SHORT_TARGET.get(product, 30)
            base_qty = self.FLOW_FADE_BASE_SIZE + int(min(self.FLOW_FADE_MAX_SIZE - self.FLOW_FADE_BASE_SIZE, abs(signal) // 4))
            model = snap['wall_mid'] if snap.get('wall_mid') is not None else snap['mid']
            if signal > 0 and position < long_cap:
                qty = min(base_qty, long_cap - position)
                price = int(snap['bid'])
                improved = price + 1
                if improved < snap['ask']:
                    price = improved
                if qty > 0 and price < snap['ask']:
                    meta = self.quote_meta(product, 'public_flow_fade_buy', price, qty, snap, model, smile, {'flow_fade_signal': signal})
                    orders_by_product[product].append((Order(product, price, qty), 'public_flow_fade_buy', meta))
            elif signal < 0 and position > -short_cap:
                qty = min(base_qty, position + short_cap)
                price = int(snap['ask'])
                improved = price - 1
                if improved > snap['bid']:
                    price = improved
                if qty > 0 and price > snap['bid']:
                    meta = self.quote_meta(product, 'public_flow_fade_sell', price, -qty, snap, model, smile, {'flow_fade_signal': signal})
                    orders_by_product[product].append((Order(product, price, -qty), 'public_flow_fade_sell', meta))

    def update_public_flow_fade_signals(self, state, snapshots, saved):
        for product in self.FLOW_FADE_PRODUCTS:
            old_signal = float(saved.get('flow_fade_%s' % product, 0.0) or 0.0)
            new_signal = 0.0
            snap = snapshots.get(product)
            if snap is not None and snap.get('mid') is not None:
                for trade in state.market_trades.get(product, []) or []:
                    side = self.classify_public_trade_side(trade, snap)
                    qty = abs(int(trade.quantity))
                    if side == 'BUY':
                        new_signal -= qty
                    else:
                        new_signal += qty
            combined = old_signal * self.FLOW_FADE_DECAY + new_signal
            if combined > self.FLOW_FADE_CAP:
                combined = self.FLOW_FADE_CAP
            elif combined < -self.FLOW_FADE_CAP:
                combined = -self.FLOW_FADE_CAP
            saved['flow_fade_%s' % product] = float(combined)

    def trade_mark_passive_bias(self, state, snapshots, saved, smile, orders_by_product):
        models = smile.get('loo_models', smile.get('models', {}))
        for product in self.MARK_OTM_BID_PRODUCTS:
            signal = float(saved.get('mark_otm_bid_%s' % product, 0.0) or 0.0)
            snap = snapshots.get(product)
            model = models.get(product)
            if snap is None or model is None:
                continue
            if snap['bid'] is None or snap['ask'] is None or snap['mid'] is None:
                continue
            depth_imbalance = snap.get('depth_imbalance')
            depth_trigger = self.MARK_OTM_DEPTH_TRIGGER.get(product, -0.04)
            state_active = depth_imbalance is not None and depth_imbalance <= depth_trigger
            if not state_active and signal < 8.0:
                continue
            position = state.position.get(product, 0)
            hard_cap = min(self.POSITION_LIMITS.get(product, 300), self.MARK_OTM_BID_HARD.get(product, 160))
            capacity = hard_cap - position
            if capacity <= 0:
                continue
            min_edge = self.MARK_OTM_BID_MIN_EDGE.get(product, 0.25)
            price = self.passive_bid_price(snap, model, min_edge)
            if price is None:
                continue
            base_size = self.MARK_OTM_STATE_BID_SIZE.get(product, self.MARK_OTM_BID_SIZE.get(product, 8)) if state_active else self.MARK_OTM_BID_SIZE.get(product, 8)
            scaled = base_size + int(min(base_size, signal // 6))
            qty = min(capacity, scaled)
            if qty <= 0:
                continue
            extra = {'mark_signal': signal, 'mark_state_active': state_active, 'depth_imbalance': depth_imbalance, 'mark_bias_product': product, 'mark_min_edge': min_edge}
            meta = self.quote_meta(product, 'mark_otm_passive_bid', price, qty, snap, model, smile, extra)
            orders_by_product[product].append((Order(product, price, qty), 'mark_otm_passive_bid', meta))

    def update_mark_signals(self, state, saved):
        for product in self.MARK_OTM_BID_PRODUCTS:
            key = 'mark_otm_bid_%s' % product
            signal = float(saved.get(key, 0.0) or 0.0) * self.MARK_SIGNAL_DECAY
            for trade in state.market_trades.get(product, []) or []:
                qty = abs(int(trade.quantity))
                seller = getattr(trade, 'seller', None)
                buyer = getattr(trade, 'buyer', None)
                if seller in self.MARK_OTM_SIGNAL_SELLERS:
                    signal += qty
                if buyer in self.MARK_OTM_CONFIRMING_BUYERS:
                    signal += 0.5 * qty
            if signal > self.MARK_SIGNAL_CAP:
                signal = self.MARK_SIGNAL_CAP
            saved[key] = float(signal)

    def trade_underlying_mark_call_bias(self, state, snapshots, saved, smile, orders_by_product):
        signal = float(saved.get('underlying_mark_signal', 0.0) or 0.0)
        if abs(signal) < self.UNDERLYING_MARK_CALL_THRESHOLD:
            return
        models = smile.get('loo_models', smile.get('models', {}))
        denominator = max(1.0, self.UNDERLYING_MARK_CALL_STRONG - self.UNDERLYING_MARK_CALL_THRESHOLD)
        strength = min(1.0, (abs(signal) - self.UNDERLYING_MARK_CALL_THRESHOLD) / denominator)
        for product in self.UNDERLYING_MARK_CALL_PRODUCTS:
            snap = snapshots.get(product)
            if snap is None or snap['bid'] is None or snap['ask'] is None or (snap['mid'] is None):
                continue
            position = state.position.get(product, 0)
            model = models.get(product)
            allowance = self.UNDERLYING_MARK_CALL_MODEL_ALLOWANCE.get(product, 4.0)
            base = self.UNDERLYING_MARK_CALL_BASE_SIZE.get(product, 5)
            max_size = self.UNDERLYING_MARK_CALL_MAX_SIZE.get(product, base)
            qty_base = base + int((max_size - base) * strength)
            if signal < 0:
                short_cap = min(self.POSITION_LIMITS.get(product, 300), self.UNDERLYING_MARK_CALL_SHORT_TARGET.get(product, 40))
                capacity = position + short_cap
                if capacity <= 0:
                    continue
                if model is not None and snap['bid'] + allowance < model:
                    continue
                qty = min(qty_base, capacity)
                if qty > 0:
                    price = int(snap['bid'])
                    extra = {'underlying_mark_signal': signal, 'mark_call_bias': 'bearish'}
                    meta = self.quote_meta(product, 'underlying_mark_call_sell', price, -qty, snap, model, smile, extra)
                    orders_by_product[product].append((Order(product, price, -qty), 'underlying_mark_call_sell', meta))
            else:
                if position >= 0:
                    continue
                price = int(snap['bid'])
                if price + 1 < snap['ask']:
                    price += 1
                if price >= snap['ask']:
                    continue
                if model is not None and price > model + allowance:
                    continue
                qty = min(qty_base, -position)
                if qty > 0:
                    extra = {'underlying_mark_signal': signal, 'mark_call_bias': 'bullish_cover'}
                    meta = self.quote_meta(product, 'underlying_mark_call_buy', price, qty, snap, model, smile, extra)
                    orders_by_product[product].append((Order(product, price, qty), 'underlying_mark_call_buy', meta))

    def update_underlying_mark_signal(self, state, saved):
        signal = float(saved.get('underlying_mark_signal', 0.0) or 0.0) * self.UNDERLYING_MARK_SIGNAL_DECAY
        trades = []
        trades.extend(state.market_trades.get(self.UNDERLYING, []) or [])
        trades.extend(state.own_trades.get(self.UNDERLYING, []) or [])
        for trade in trades:
            qty = abs(int(getattr(trade, 'quantity', 0) or 0))
            buyer = getattr(trade, 'buyer', None)
            seller = getattr(trade, 'seller', None)
            if buyer in self.UNDERLYING_MARKS:
                signal += qty
            if seller in self.UNDERLYING_MARKS:
                signal -= qty
        if signal > self.UNDERLYING_MARK_SIGNAL_CAP:
            signal = self.UNDERLYING_MARK_SIGNAL_CAP
        elif signal < -self.UNDERLYING_MARK_SIGNAL_CAP:
            signal = -self.UNDERLYING_MARK_SIGNAL_CAP
        saved['underlying_mark_signal'] = float(signal)

    def option_short_trend_scale(self, saved, snapshots=None):
        current = None
        if snapshots is not None:
            underlying = snapshots.get(self.UNDERLYING)
            if underlying is not None:
                current = underlying.get('wall_mid')
                if current is None:
                    current = underlying.get('mid')
        if current is not None and saved.get('velvet_session_anchor') is None:
            saved['velvet_session_anchor'] = float(current)
        history = saved.get('velvet_mr_history', [])
        if current is None and len(history) < self.OPTION_SHORT_TREND_MIN_HISTORY:
            return 1.0
        sample = history[-self.OPTION_SHORT_TREND_LOOKBACK:]
        if current is not None:
            sample = sample + [float(current)]
        if len(sample) < self.OPTION_SHORT_TREND_MIN_HISTORY:
            return 1.0
        anchor = sum(sample) / len(sample)
        session_anchor = float(saved.get('velvet_session_anchor', anchor) or anchor)
        up_move = max(sample[-1] - anchor, sample[-1] - session_anchor)
        if up_move <= self.OPTION_SHORT_TREND_WARN:
            return 1.0
        if up_move >= self.OPTION_SHORT_TREND_HARD:
            return self.OPTION_SHORT_TREND_MIN_SCALE
        span = max(1.0, self.OPTION_SHORT_TREND_HARD - self.OPTION_SHORT_TREND_WARN)
        fade = (up_move - self.OPTION_SHORT_TREND_WARN) / span
        return max(self.OPTION_SHORT_TREND_MIN_SCALE, 1.0 - fade * (1.0 - self.OPTION_SHORT_TREND_MIN_SCALE))

    def bullish_call_probe_active(self, saved, snapshots):
        return self.option_short_trend_scale(saved, snapshots) <= 0.2

    def trade_vev5400_probe(self, state, snapshots, saved, orders_by_product):
        product = 'VEV_5400'
        snap = snapshots.get(product)
        if snap is None or snap['bid'] is None:
            return
        scale = self.option_short_trend_scale(saved, snapshots)
        position = state.position.get(product, 0)
        short_cap = 300
        if position <= -short_cap:
            return
        raw_qty = int(round(15 * scale))
        if raw_qty <= 0:
            return
        qty = min(raw_qty, position + short_cap)
        if qty <= 0:
            return
        price = int(snap['bid'])
        orders_by_product[product].append((Order(product, price, -qty), 'vev5400_probe_sell', self.quote_meta(product, 'vev5400_probe_sell', price, -qty, snap, None, None, {'trend_scale': scale})))

    def trade_vev5200_probe(self, state, snapshots, saved, orders_by_product):
        product = 'VEV_5200'
        snap = snapshots.get(product)
        if snap is None or snap['bid'] is None:
            return
        scale = self.option_short_trend_scale(saved, snapshots)
        position = state.position.get(product, 0)
        short_cap = 300
        if position <= -short_cap:
            return
        raw_qty = int(round(12 * scale))
        if raw_qty <= 0:
            return
        qty = min(raw_qty, position + short_cap)
        if qty <= 0:
            return
        price = int(snap['bid'])
        orders_by_product[product].append((Order(product, price, -qty), 'vev5200_probe_sell', self.quote_meta(product, 'vev5200_probe_sell', price, -qty, snap, None, None, {'trend_scale': scale})))

    def trade_deeper_option_short_probe(self, state, snapshots, saved, orders_by_product):
        scale = self.option_short_trend_scale(saved, snapshots)
        for product, per_tick, short_cap in (('VEV_5000', 9, 220), ('VEV_5100', 11, 280)):
            snap = snapshots.get(product)
            if snap is None or snap['bid'] is None:
                continue
            position = state.position.get(product, 0)
            if position <= -short_cap:
                continue
            raw_qty = int(round(per_tick * scale))
            if raw_qty <= 0:
                continue
            qty = min(raw_qty, position + short_cap)
            if qty <= 0:
                continue
            price = int(snap['bid'])
            reason = product.lower() + '_probe_sell'
            orders_by_product[product].append((Order(product, price, -qty), reason, self.quote_meta(product, reason, price, -qty, snap, None, None, {'trend_scale': scale})))

    def trade_option_uptrend_recycle(self, state, snapshots, saved, smile, orders_by_product):
        scale = self.option_short_trend_scale(saved, snapshots)
        if scale > self.OPTION_UPTREND_RECYCLE_TRIGGER_SCALE:
            return
        models = smile.get('loo_models', smile.get('models', {})) if smile is not None else {}
        strength = max(0.0, min(1.0, (self.OPTION_UPTREND_RECYCLE_TRIGGER_SCALE - scale) / max(0.01, self.OPTION_UPTREND_RECYCLE_TRIGGER_SCALE)))
        for product, base_size in self.OPTION_UPTREND_RECYCLE_SIZE.items():
            snap = snapshots.get(product)
            if snap is None or snap.get('bid') is None or snap.get('ask') is None:
                continue
            position = state.position.get(product, 0)
            min_short = self.OPTION_UPTREND_RECYCLE_MIN_SHORT.get(product, 100)
            if position > -min_short:
                continue
            price = int(snap['bid'])
            if price + 1 < snap['ask']:
                price += 1
            model = models.get(product)
            allowance = self.OPTION_UPTREND_RECYCLE_MODEL_ALLOWANCE.get(product, 1.0)
            if model is not None and price > model + allowance:
                continue
            qty = min(max(1, int(round(base_size * strength))), -position, self.POSITION_LIMITS[product] - position)
            if qty <= 0:
                continue
            reason = product.lower() + '_uptrend_recycle_bid'
            extra = {'trend_scale': scale, 'uptrend_recycle': True}
            orders_by_product[product].append((Order(product, price, qty), reason, self.quote_meta(product, reason, price, qty, snap, model, smile, extra)))

    def trade_bullish_call_probe(self, state, snapshots, saved, smile, orders_by_product):
        if not self.bullish_call_probe_active(saved, snapshots):
            return
        models = smile.get('loo_models', smile.get('models', {})) if smile is not None else {}
        trend_scale = self.option_short_trend_scale(saved, snapshots)
        strength = max(0.0, min(1.0, (0.2 - trend_scale) / 0.2))
        for product in self.BULL_CALL_PROBE_PRODUCTS:
            snap = snapshots.get(product)
            if snap is None or snap.get('bid') is None or snap.get('ask') is None:
                continue
            model = models.get(product)
            allowance = self.BULL_CALL_PROBE_MODEL_ALLOWANCE.get(product, 1.0)
            position = state.position.get(product, 0)
            long_cap = self.BULL_CALL_PROBE_LONG_CAP.get(product, 30)
            if position >= long_cap:
                continue
            base = self.BULL_CALL_PROBE_SIZE.get(product, 4)
            qty = min(base + int(base * strength), long_cap - position, self.POSITION_LIMITS[product] - position)
            if qty <= 0:
                continue
            if model is not None and snap['bid'] > model + allowance:
                continue
            price = int(snap['bid'])
            if price + 1 < snap['ask']:
                price += 1
            reason = product.lower() + '_bull_call_probe_bid'
            extra = {'bull_call_probe': True, 'trend_scale': trend_scale}
            orders_by_product[product].append((Order(product, price, qty), reason, self.quote_meta(product, reason, price, qty, snap, model, smile, extra)))

    def trade_underlying_mean_reversion(self, state, snapshots, saved, smile, orders_by_product):
        product = self.UNDERLYING
        snap = snapshots.get(product)
        if snap is None or snap['bid'] is None or snap['ask'] is None or (snap['mid'] is None):
            return
        stats = self.underlying_mr_stats(saved.get('velvet_mr_history', []))
        if stats is None:
            return
        mid = snap['wall_mid'] if snap.get('wall_mid') is not None else snap['mid']
        ema, std = stats
        if std <= 1e-09:
            return
        dev = mid - ema
        z_score = dev / std
        position = state.position.get(product, 0)
        target = 0
        if z_score <= -self.UNDERLYING_MR_Z_ENTRY:
            target = self.UNDERLYING_MR_TARGET
        elif z_score >= self.UNDERLYING_MR_Z_ENTRY:
            target = -self.UNDERLYING_MR_TARGET
        elif position > 0 and dev >= 0:
            target = 0
        elif position < 0 and dev <= 0:
            target = 0
        else:
            return
        diff = target - position
        if diff == 0:
            return
        model = ema
        meta_extra = {'mr_ema': ema, 'mr_std': std, 'mr_z': z_score, 'target': target}
        if diff > 0:
            qty = min(diff, self.UNDERLYING_MR_SIZE, self.POSITION_LIMITS[product] - position)
            price = self.passive_bid_price(snap, model, self.UNDERLYING_MR_MIN_EDGE)
            if qty > 0 and price is not None:
                orders_by_product[product].append((Order(product, price, qty), 'underlying_mr_buy', self.quote_meta(product, 'underlying_mr_buy', price, qty, snap, model, smile, meta_extra)))
        else:
            qty = min(-diff, self.UNDERLYING_MR_SIZE, self.POSITION_LIMITS[product] + position)
            price = self.passive_ask_price(snap, model, self.UNDERLYING_MR_MIN_EDGE)
            if qty > 0 and price is not None:
                orders_by_product[product].append((Order(product, price, -qty), 'underlying_mr_sell', self.quote_meta(product, 'underlying_mr_sell', price, -qty, snap, model, smile, meta_extra)))

    def underlying_mr_stats(self, history):
        if len(history) < self.UNDERLYING_MR_MIN_HISTORY:
            return None
        sample = history[-self.UNDERLYING_MR_HISTORY_LIMIT:]
        alpha = 2.0 / (self.UNDERLYING_MR_SPAN + 1.0)
        ema = sample[0]
        for value in sample[1:]:
            ema = alpha * value + (1.0 - alpha) * ema
        mean = sum(sample) / len(sample)
        variance = sum(((value - mean) ** 2 for value in sample)) / max(1, len(sample) - 1)
        return (ema, math.sqrt(max(0.0, variance)))

    def trade_passive_market_making(self, state, snapshots, smile, orders_by_product):
        for product, config in self.MM_CONFIG.items():
            if config.get('enabled') is False:
                continue
            snap = snapshots.get(product)
            if snap is None or snap['bid'] is None or snap['ask'] is None or (snap['mid'] is None):
                continue
            spread = snap['ask'] - snap['bid']
            if spread < config['min_spread']:
                continue
            fair = self.market_making_fair(product, snap, snapshots, smile, config)
            if fair is None:
                continue
            position = state.position.get(product, 0)
            hard = int(config['hard'])
            soft = int(config['soft'])
            base_size = int(config['size'])
            skew = float(config['skew'])
            min_edge = float(config['min_edge'])
            skew_position = self.inventory_skew_position(product, position, state, smile)
            skewed_fair = fair - skew_position * skew
            bid_qty = self.inventory_scaled_size(base_size, position, soft, hard, is_buy=True)
            ask_qty = self.inventory_scaled_size(base_size, position, soft, hard, is_buy=False)
            bid_price = self.market_making_bid_price(snap, skewed_fair, min_edge)
            ask_price = self.market_making_ask_price(snap, skewed_fair, min_edge)
            if bid_qty > 0 and position < hard and (bid_price is not None):
                orders_by_product[product].append((Order(product, bid_price, min(bid_qty, hard - position)), 'passive_mm_bid', self.quote_meta(product, 'passive_mm_bid', bid_price, min(bid_qty, hard - position), snap, fair, smile, {'delta_exposure': skew_position})))
            if ask_qty > 0 and position > -hard and (ask_price is not None):
                orders_by_product[product].append((Order(product, ask_price, -min(ask_qty, hard + position)), 'passive_mm_ask', self.quote_meta(product, 'passive_mm_ask', ask_price, -min(ask_qty, hard + position), snap, fair, smile, {'delta_exposure': skew_position})))

    def inventory_skew_position(self, product, position, state, smile):
        if product != self.UNDERLYING or not self.ENABLE_DELTA_SKEW or smile is None:
            return float(position)
        exposure = float(state.position.get(self.UNDERLYING, 0))
        deltas = smile.get('deltas', {})
        for option in self.OPTIONS:
            exposure += state.position.get(option, 0) * deltas.get(option, 0.0)
        return max(-self.DELTA_SKEW_CAP, min(self.DELTA_SKEW_CAP, exposure))

    def market_making_fair(self, product, snap, snapshots, smile, config):
        source = config.get('fair')
        if source == 'wall_mid':
            return snap.get('wall_mid') if snap.get('wall_mid') is not None else snap['mid']
        if source == 'parity':
            underlying = snapshots.get(self.UNDERLYING)
            if underlying is None or underlying.get('mid') is None:
                return snap['mid']
            strike = self.OPTIONS.get(product)
            if strike is None:
                return snap['mid']
            parity = max(underlying['mid'] - strike, 0.0)
            if snap['mid'] is None:
                return parity
            return 0.65 * parity + 0.35 * snap['mid']
        if source == 'smile' and smile is not None:
            return smile.get('loo_models', smile.get('models', {})).get(product, snap['mid'])
        return snap['mid']

    def inventory_scaled_size(self, base_size, position, soft, hard, is_buy):
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

    def market_making_bid_price(self, snap, fair, min_edge):
        bid = int(snap['bid'])
        ask = int(snap['ask'])
        price = bid
        improved = bid + 1
        if improved < ask and fair - improved >= min_edge:
            price = improved
        if price < ask and fair - price >= min_edge:
            return max(0, price)
        return None

    def market_making_ask_price(self, snap, fair, min_edge):
        bid = int(snap['bid'])
        ask = int(snap['ask'])
        price = ask
        improved = ask - 1
        if improved > bid and improved - fair >= min_edge:
            price = improved
        if price > bid and price - fair >= min_edge:
            return max(1, price)
        return None

    def quote_meta(self, product, reason, price, quantity, snap, model, smile, extra=None):
        return {'reason': reason}

    def trade_smile_residuals(self, state, snapshots, smile, orders_by_product):
        if self.ENABLE_DEAD_QUOTE_FILTER:
            products = self.FILTERED_SMILE_TRADE_PRODUCTS
        else:
            products = self.WATCH_PRODUCTS + self.SCALP_PRODUCTS
        for product in products:
            snap = snapshots.get(product)
            model = smile.get('loo_models', smile['models']).get(product)
            if snap is None or model is None:
                continue
            if snap['bid'] is None or snap['ask'] is None or snap['mid'] is None:
                continue
            position = state.position.get(product, 0)
            spread = max(1.0, snap['ask'] - snap['bid'])
            buy_min_edge = self.MIN_BUY_MODEL_EDGE.get(product, self.MIN_MODEL_EDGE.get(product, 2.0))
            sell_min_edge = self.MIN_SELL_MODEL_EDGE.get(product, self.MIN_MODEL_EDGE.get(product, 2.0))
            residual = snap['mid'] - model
            long_cap = self.LONG_TARGET.get(product, 60)
            short_cap = self.SHORT_TARGET.get(product, 0)
            residual_z = smile.get('residual_z', {}).get(product)
            delta = smile.get('deltas', {}).get(product, 0.0)
            vega = smile.get('vegas', {}).get(product, 0.0)
            gamma = smile.get('gammas', {}).get(product, 0.0)
            theta = smile.get('thetas', {}).get(product, 0.0)
            buy_edge = model - snap['ask']
            sell_edge = snap['bid'] - model
            buy_signal = self.signal_allows_buy(residual_z, buy_edge, buy_min_edge)
            sell_signal = self.signal_allows_sell(residual_z, sell_edge, sell_min_edge)
            active_buy_signal = self.active_signal_allows_buy(product, residual_z, buy_edge, buy_min_edge)
            active_sell_signal = self.active_signal_allows_sell(product, residual_z, sell_edge, sell_min_edge)
            active_buy_edge = max(buy_min_edge * self.ACTIVE_EDGE_MULT, spread * self.ACTIVE_SPREAD_FRACTION + 0.5)
            active_sell_edge = max(sell_min_edge * self.ACTIVE_EDGE_MULT, spread * self.ACTIVE_SPREAD_FRACTION + 0.5)
            if self.ENABLE_SMILE_ACTIVE and product in self.ACTIVE_PRODUCTS and (buy_edge >= active_buy_edge) and (position < long_cap) and active_buy_signal:
                qty = self.dynamic_smile_size(product, self.ACTIVE_BASE_SIZE.get(product, 5), long_cap - position, residual_z, buy_edge, spread)
                order = Order(product, int(snap['ask']), qty)
                orders_by_product[product].append((order, 'smile_take_buy', self.quote_meta(product, 'smile_take_buy', int(snap['ask']), qty, snap, model, smile)))
                continue
            if self.ENABLE_SMILE_ACTIVE and product in self.ACTIVE_PRODUCTS and (sell_edge >= active_sell_edge) and (position > -short_cap) and active_sell_signal:
                qty = self.dynamic_smile_size(product, self.ACTIVE_BASE_SIZE.get(product, 5), position + short_cap, residual_z, sell_edge, spread)
                order = Order(product, int(snap['bid']), -qty)
                orders_by_product[product].append((order, 'smile_take_sell', self.quote_meta(product, 'smile_take_sell', int(snap['bid']), -qty, snap, model, smile)))
                continue
            exit_edge = self.EXIT_EDGE.get(product, 0.5)
            if position > 0 and residual >= -exit_edge:
                qty = min(abs(position), self.PASSIVE_BASE_SIZE.get(product, 10))
                price = self.passive_ask_price(snap, model, min_edge=0.0)
                if qty > 0 and price is not None:
                    orders_by_product[product].append((Order(product, price, -qty), 'smile_exit_long', self.quote_meta(product, 'smile_exit_long', price, -qty, snap, model, smile)))
                continue
            if position < 0 and residual <= exit_edge:
                qty = min(abs(position), self.PASSIVE_BASE_SIZE.get(product, 10))
                price = self.passive_bid_price(snap, model, min_edge=0.0)
                if qty > 0 and price is not None:
                    orders_by_product[product].append((Order(product, price, qty), 'smile_exit_short', self.quote_meta(product, 'smile_exit_short', price, qty, snap, model, smile)))
                continue
            if self.ENABLE_SMILE_PASSIVE and model - snap['bid'] >= buy_min_edge and (position < long_cap) and buy_signal:
                qty = self.dynamic_smile_size(product, self.PASSIVE_BASE_SIZE.get(product, 10), long_cap - position, residual_z, model - snap['bid'], spread)
                price = self.passive_bid_price(snap, model, buy_min_edge)
                if qty > 0 and price is not None:
                    orders_by_product[product].append((Order(product, price, qty), 'smile_passive_buy', self.quote_meta(product, 'smile_passive_buy', price, qty, snap, model, smile)))
            if self.ENABLE_SMILE_PASSIVE and short_cap > 0 and (snap['ask'] - model >= sell_min_edge) and (position > -short_cap) and sell_signal:
                qty = self.dynamic_smile_size(product, self.PASSIVE_BASE_SIZE.get(product, 10), position + short_cap, residual_z, snap['ask'] - model, spread)
                price = self.passive_ask_price(snap, model, sell_min_edge)
                if qty > 0 and price is not None:
                    orders_by_product[product].append((Order(product, price, -qty), 'smile_passive_sell', self.quote_meta(product, 'smile_passive_sell', price, -qty, snap, model, smile)))

    def signal_allows_buy(self, residual_z, edge_to_model, min_edge):
        if not self.ENABLE_RESIDUAL_Z_FILTER or residual_z is None:
            return True
        if residual_z <= -self.RESIDUAL_Z_ENTRY:
            return True
        return edge_to_model >= min_edge * 2.4

    def signal_allows_sell(self, residual_z, edge_to_model, min_edge):
        if not self.ENABLE_RESIDUAL_Z_FILTER or residual_z is None:
            return True
        if residual_z >= self.RESIDUAL_Z_ENTRY:
            return True
        return edge_to_model >= min_edge * 2.4

    def active_signal_allows_buy(self, product, residual_z, edge_to_model, min_edge):
        if residual_z is not None and residual_z <= -self.ACTIVE_RESIDUAL_Z_ENTRY:
            return True
        return edge_to_model >= min_edge * 3.0

    def active_signal_allows_sell(self, product, residual_z, edge_to_model, min_edge):
        if residual_z is not None and residual_z >= self.ACTIVE_RESIDUAL_Z_ENTRY:
            return True
        return edge_to_model >= min_edge * 3.0

    def dynamic_smile_size(self, product, base_size, remaining_capacity, residual_z, edge_to_model, spread):
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
        cap = max(base_size, int(base_size * 2.75))
        return max(1, min(int(round(base_size * multiplier)), cap, remaining_capacity))

    def trade_zero_bid_lottery(self, state, snapshots, smile, orders_by_product):
        for product in self.ZERO_BID_PRODUCTS:
            snap = snapshots.get(product)
            if snap is None or snap['ask'] is None:
                continue
            position = state.position.get(product, 0)
            model = smile['models'].get(product)
            if position < self.ZERO_BID_MAX_POS and snap['ask'] >= 1:
                qty = min(self.ZERO_BID_SIZE, self.ZERO_BID_MAX_POS - position)
                if qty > 0:
                    orders_by_product[product].append((Order(product, 0, qty), 'zero_bid_lottery', self.quote_meta(product, 'zero_bid_lottery', 0, qty, snap, model, smile)))
            if position > 0 and snap['ask'] is not None:
                ask_price = max(1, int(snap['ask']))
                qty = min(position, self.ZERO_ASK_SIZE)
                if qty > 0:
                    orders_by_product[product].append((Order(product, ask_price, -qty), 'zero_bid_take_profit', self.quote_meta(product, 'zero_bid_take_profit', ask_price, -qty, snap, model, smile)))

    def trade_iv_carry(self, state, snapshots, smile, orders_by_product):
        iv_zs = smile.get('iv_z', {})
        fair_ivs = smile.get('fair_ivs', {})
        market_ivs = smile.get('ivs', {})
        for product in self.SMILE_PRODUCTS:
            snap = snapshots.get(product)
            model = smile.get('loo_models', smile['models']).get(product)
            iv_z = iv_zs.get(product)
            if snap is None or model is None or iv_z is None:
                continue
            if snap['bid'] is None or snap['ask'] is None or snap['mid'] is None:
                continue
            position = state.position.get(product, 0)
            spread = max(1.0, snap['ask'] - snap['bid'])
            min_edge = max(1.0, self.MIN_MODEL_EDGE.get(product, 2.0) * 0.5, spread * 0.4)
            residual = snap['mid'] - model
            delta = smile.get('deltas', {}).get(product, 0.0)
            vega = smile.get('vegas', {}).get(product, 0.0)
            gamma = smile.get('gammas', {}).get(product, 0.0)
            theta = smile.get('thetas', {}).get(product, 0.0)
            meta = {'model': model, 'residual': residual, 'residual_z': smile.get('residual_z', {}).get(product), 'iv': market_ivs.get(product), 'fair_iv': fair_ivs.get(product), 'iv_z': iv_z, 'tte': smile['tte'], 'delta': delta, 'vega': vega, 'gamma': gamma, 'theta': theta}
            if iv_z <= -self.IV_Z_ENTRY and model - snap['bid'] >= min_edge:
                long_cap = self.LONG_TARGET.get(product, 50)
                if position < long_cap:
                    qty = min(8, long_cap - position)
                    price = self.iv_carry_bid_price(snap, model, min_edge)
                    if qty > 0 and price is not None:
                        orders_by_product[product].append((Order(product, price, qty), 'iv_carry_buy', meta))
            if iv_z >= self.IV_Z_ENTRY and snap['ask'] - model >= min_edge:
                short_cap = self.SHORT_TARGET.get(product, 0)
                if short_cap > 0 and position > -short_cap:
                    qty = min(8, position + short_cap)
                    price = self.iv_carry_ask_price(snap, model, min_edge)
                    if qty > 0 and price is not None:
                        orders_by_product[product].append((Order(product, price, -qty), 'iv_carry_sell', meta))

    def fit_best_smile(self, snapshots, spot, timestamp):
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
                if snap is None or snap['mid'] is None or snap['spread'] is None:
                    continue
                strike = self.OPTIONS[product]
                intrinsic = max(spot - strike, 0.0)
                extrinsic = snap['mid'] - intrinsic
                if extrinsic < 0.5:
                    continue
                iv = self.implied_vol(snap['mid'], spot, strike, t)
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
                if snap is None or snap['mid'] is None:
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
                if product in self.SMILE_PRODUCTS and snap['spread'] is not None:
                    denom = max(1.0, snap['spread'])
                    score += ((snap['mid'] - model) / denom) ** 2
                    count += 1
            if count == 0:
                continue
            loo_models = self.build_leave_one_out_models(points, snapshots, spot, t)
            score /= count
            candidate = {'tte': tte_days, 'tte_source': tte_source, 't': t, 'spot': spot, 'coef': coef, 'models': models, 'loo_models': loo_models, 'deltas': deltas, 'vegas': vegas, 'gammas': gammas, 'thetas': thetas, 'fair_ivs': fair_ivs, 'score': score, 'ivs': all_ivs}
            if best is None or candidate['score'] < best['score']:
                best = candidate
        return best

    def annotate_smile_state(self, saved, snapshots, smile):
        residual_z = {}
        residual_mean = {}
        residual_std = {}
        iv_z = {}
        iv_mean = {}
        iv_std = {}
        iv_residuals = {}
        models = smile.get('loo_models', smile.get('models', {}))
        for product in self.SMILE_PRODUCTS:
            snap = snapshots.get(product)
            model = models.get(product)
            if snap is None or model is None or snap.get('mid') is None:
                continue
            residual = snap['mid'] - model
            z, mean, std = self.history_zscore(saved.get(f'resid_{product}', []), residual)
            if z is not None:
                residual_z[product] = z
                residual_mean[product] = mean
                residual_std[product] = std
            market_iv = smile.get('ivs', {}).get(product)
            fair_iv = smile.get('fair_ivs', {}).get(product)
            if market_iv is not None and fair_iv is not None:
                iv_residual = market_iv - fair_iv
                iv_residuals[product] = iv_residual
                z, mean, std = self.history_zscore(saved.get(f'iv_resid_{product}', []), iv_residual)
                if z is not None:
                    iv_z[product] = z
                    iv_mean[product] = mean
                    iv_std[product] = std
        smile['residual_z'] = residual_z
        smile['residual_mean'] = residual_mean
        smile['residual_std'] = residual_std
        smile['iv_z'] = iv_z
        smile['iv_mean'] = iv_mean
        smile['iv_std'] = iv_std
        smile['iv_residuals'] = iv_residuals

    def history_zscore(self, history, value):
        if len(history) < self.RESIDUAL_HISTORY_MIN:
            return (None, None, None)
        mean = sum(history) / len(history)
        variance = sum(((item - mean) ** 2 for item in history)) / max(1, len(history) - 1)
        std = math.sqrt(variance)
        if std <= 1e-09:
            return (None, mean, std)
        return ((value - mean) / std, mean, std)

    def build_leave_one_out_models(self, points, snapshots, spot, t):
        models = {}
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

    def get_tte_candidates(self, timestamp):
        if self.AUTO_TTE:
            return (self.TTE_CANDIDATES, 'auto')
        if abs(timestamp) >= 1000000:
            day_index = int(timestamp // 1000000)
            day_fraction = timestamp % int(self.DAY_TIMESTAMP_STRIDE) / self.DAY_TIMESTAMP_STRIDE
            return ((max(0.01, self.HISTORICAL_DAY0_TTE - day_index - day_fraction),), 'global_timestamp')
        live_fraction = max(0.0, timestamp) / self.DAY_TIMESTAMP_STRIDE
        return ((max(0.01, self.LIVE_TTE_DAYS - live_fraction),), 'live')

    def passive_bid_price(self, snap, model, min_edge):
        if snap['bid'] is None or snap['ask'] is None:
            return None
        price = int(snap['bid'])
        improved = price + 1
        if improved < snap['ask'] and model - improved >= min_edge:
            price = improved
        if price < snap['ask'] and model - price >= min_edge:
            return max(0, price)
        return None

    def passive_ask_price(self, snap, model, min_edge):
        if snap['bid'] is None or snap['ask'] is None:
            return None
        price = int(snap['ask'])
        improved = price - 1
        if improved > snap['bid'] and improved - model >= min_edge:
            price = improved
        if price > snap['bid'] and price - model >= min_edge:
            return max(1, price)
        return None

    def iv_carry_bid_price(self, snap, model, min_edge):
        if snap['bid'] is None or snap['ask'] is None:
            return None
        price = int(snap['bid'])
        improved = price + 1
        if improved < snap['ask'] and model - improved >= min_edge:
            price = improved
        if price < snap['ask'] and model - price >= min_edge:
            return max(0, price)
        return None

    def iv_carry_ask_price(self, snap, model, min_edge):
        if snap['bid'] is None or snap['ask'] is None:
            return None
        price = int(snap['ask'])
        improved = price - 1
        if improved > snap['bid'] and improved - model >= min_edge:
            price = improved
        if price > snap['bid'] and price - model >= min_edge:
            return max(1, price)
        return None

    def build_snapshots(self, order_depths):
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
            bid_depth = sum((volume for _, volume in bids))
            ask_depth = sum((volume for _, volume in asks))
            depth_sum = bid_depth + ask_depth
            depth_imbalance = (bid_depth - ask_depth) / depth_sum if depth_sum > 0 else None
            top_sum = 0
            top_imbalance = None
            if bids:
                top_sum += bids[0][1]
            if asks:
                top_sum += asks[0][1]
            if top_sum > 0 and bids and asks:
                top_imbalance = (bids[0][1] - asks[0][1]) / top_sum
            snapshots[product] = {'bids': bids, 'asks': asks, 'bid': bid, 'ask': ask, 'mid': mid, 'wall_mid': wall_mid, 'spread': spread, 'bid_depth': bid_depth, 'ask_depth': ask_depth, 'depth_imbalance': depth_imbalance, 'top_imbalance': top_imbalance}
        return snapshots

    def net_and_clip_orders(self, product, orders, position):
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

    def net_and_clip_detailed_orders(self, product, detailed_orders, position):
        if not detailed_orders:
            return []
        limit = self.POSITION_LIMITS.get(product, 300)
        buy_capacity = max(0, limit - position)
        sell_capacity = max(0, limit + position)
        clipped = []
        used_buy = 0
        used_sell = 0
        for order, reason, meta in detailed_orders:
            if order.quantity > 0:
                qty = min(order.quantity, buy_capacity - used_buy)
                if qty > 0:
                    clipped_order = Order(product, int(order.price), int(qty))
                    clipped_meta = dict(meta)
                    clipped_meta['submitted_qty'] = int(qty)
                    clipped.append((clipped_order, reason, clipped_meta))
                    used_buy += qty
            elif order.quantity < 0:
                qty = min(-order.quantity, sell_capacity - used_sell)
                if qty > 0:
                    clipped_order = Order(product, int(order.price), -int(qty))
                    clipped_meta = dict(meta)
                    clipped_meta['submitted_qty'] = -int(qty)
                    clipped.append((clipped_order, reason, clipped_meta))
                    used_sell += qty
        return clipped

    def norm_cdf(self, x):
        return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))

    def norm_pdf(self, x):
        return math.exp(-0.5 * x * x) / math.sqrt(2.0 * math.pi)

    def bs_call_price(self, spot, strike, t, sigma):
        intrinsic = max(spot - strike, 0.0)
        if t <= 0 or sigma <= 1e-09:
            return intrinsic
        vol_sqrt_t = sigma * math.sqrt(t)
        if vol_sqrt_t <= 0:
            return intrinsic
        d1 = (math.log(spot / strike) + 0.5 * sigma * sigma * t) / vol_sqrt_t
        d2 = d1 - vol_sqrt_t
        return spot * self.norm_cdf(d1) - strike * self.norm_cdf(d2)

    def bs_vega(self, spot, strike, t, sigma):
        if t <= 0 or sigma <= 1e-09:
            return 0.0
        vol_sqrt_t = sigma * math.sqrt(t)
        if vol_sqrt_t <= 0:
            return 0.0
        d1 = (math.log(spot / strike) + 0.5 * sigma * sigma * t) / vol_sqrt_t
        return spot * self.norm_pdf(d1) * math.sqrt(t)

    def bs_delta(self, spot, strike, t, sigma):
        if t <= 0 or sigma <= 1e-09:
            return 1.0 if spot > strike else 0.0
        vol_sqrt_t = sigma * math.sqrt(t)
        if vol_sqrt_t <= 0:
            return 1.0 if spot > strike else 0.0
        d1 = (math.log(spot / strike) + 0.5 * sigma * sigma * t) / vol_sqrt_t
        return self.norm_cdf(d1)

    def bs_gamma(self, spot, strike, t, sigma):
        if spot <= 0 or t <= 0 or sigma <= 1e-09:
            return 0.0
        vol_sqrt_t = sigma * math.sqrt(t)
        if vol_sqrt_t <= 0:
            return 0.0
        d1 = (math.log(spot / strike) + 0.5 * sigma * sigma * t) / vol_sqrt_t
        return self.norm_pdf(d1) / (spot * vol_sqrt_t)

    def bs_theta_per_day(self, spot, strike, t, sigma):
        if t <= 0 or sigma <= 1e-09:
            return 0.0
        vol_sqrt_t = sigma * math.sqrt(t)
        if vol_sqrt_t <= 0:
            return 0.0
        d1 = (math.log(spot / strike) + 0.5 * sigma * sigma * t) / vol_sqrt_t
        annual_theta = -(spot * self.norm_pdf(d1) * sigma) / (2.0 * math.sqrt(t))
        return annual_theta / 365.0

    def implied_vol(self, mid, spot, strike, t):
        if spot <= 0 or strike <= 0 or t <= 0:
            return None
        intrinsic = max(spot - strike, 0.0)
        if mid <= intrinsic + 1e-06 or mid >= spot:
            return None
        lo = 1e-05
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

    def weighted_quadratic_fit(self, points):
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

    def solve_3x3(self, matrix, vector):
        a = [row[:] + [vector[i]] for i, row in enumerate(matrix)]
        n = 3
        for col in range(n):
            pivot = max(range(col, n), key=lambda r: abs(a[r][col]))
            if abs(a[pivot][col]) < 1e-12:
                return None
            if pivot != col:
                a[col], a[pivot] = (a[pivot], a[col])
            divisor = a[col][col]
            for k in range(col, n + 1):
                a[col][k] /= divisor
            for r in range(n):
                if r == col:
                    continue
                factor = a[r][col]
                for k in range(col, n + 1):
                    a[r][k] -= factor * a[col][k]
        return (a[0][3], a[1][3], a[2][3])

    def eval_quadratic(self, coef, x):
        return coef[0] * x * x + coef[1] * x + coef[2]

    def load_trader_data(self, trader_data):
        if not trader_data:
            return {}
        try:
            return json.loads(trader_data)
        except Exception:
            return {}

    def remember(self, saved, key, value, limit):
        history = saved.setdefault(key, [])
        history.append(float(value))
        if len(history) > limit:
            del history[:-limit]

    def make_trader_data(self, saved, snapshots, smile):
        underlying = snapshots.get(self.UNDERLYING)
        if underlying and underlying['mid'] is not None:
            self.remember(saved, 'velvet_mid_history', underlying['mid'], self.HISTORY_LIMIT)
            mr_fair = underlying['wall_mid'] if underlying.get('wall_mid') is not None else underlying['mid']
            self.remember(saved, 'velvet_mr_history', mr_fair, self.UNDERLYING_MR_HISTORY_LIMIT)
        hydrogel = snapshots.get(self.HYDROGEL_PRODUCT)
        if hydrogel and hydrogel['mid'] is not None:
            fair = hydrogel['wall_mid'] if hydrogel['wall_mid'] is not None else hydrogel['mid']
            signal_fair = self.hydrogel_signal_fair(saved, hydrogel['mid'], hydrogel['wall_mid'], fair)
            saved['last_hydrogel_mid'] = hydrogel['mid']
            if hydrogel['wall_mid'] is not None:
                saved['last_hydrogel_wall_mid'] = hydrogel['wall_mid']
            saved['last_hydrogel_fair'] = fair
            saved['last_hydrogel_signal_fair'] = signal_fair
            self.remember(saved, 'hydrogel_fair_history', fair, self.HYDROGEL_SIGNAL_HISTORY_LIMIT)
        if smile is not None:
            saved['last_smile_tte'] = smile['tte']
            saved['last_smile_score'] = smile['score']
            models = smile.get('loo_models', smile.get('models', {}))
            for product in self.SMILE_PRODUCTS:
                snap = snapshots.get(product)
                model = models.get(product)
                if snap is not None and model is not None and (snap.get('mid') is not None):
                    self.remember(saved, f'resid_{product}', snap['mid'] - model, self.HISTORY_LIMIT)
                iv_residual = smile.get('iv_residuals', {}).get(product)
                if iv_residual is not None:
                    self.remember(saved, f'iv_resid_{product}', iv_residual, self.HISTORY_LIMIT)
        return json.dumps(saved, separators=(',', ':'))

    def log_orders(self, timestamp, product, detailed_orders, snapshot, smile):
        if not self.ENABLE_RESEARCH_LOGS:
            return
        if product in ('VEV_5500', 'VEV_6000', 'VEV_6500'):
            return
        orders = [item[0] for item in detailed_orders]
        reasons = [item[1] for item in detailed_orders]
        meta = detailed_orders[0][2] if detailed_orders else {}

        def compact_value(value):
            if isinstance(value, float):
                return round(value, 4)
            return value
        payload = {'kind': 'quotes', 'timestamp': timestamp, 'product': product, 'reason': '+'.join(reasons), 'orders': [[order.price, order.quantity] for order in orders]}
        print(json.dumps(payload, separators=(',', ':')))