from __future__ import annotations

import csv
import hashlib
import json
import math
from collections import defaultdict
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / "Price & Trade Data"
REPORT_DIR = ROOT / "Reports"

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


def norm_cdf(x: float) -> float:
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def norm_pdf(x: float) -> float:
    return math.exp(-0.5 * x * x) / math.sqrt(2.0 * math.pi)


def bs_call_price(spot: float, strike: float, t: float, sigma: float) -> float:
    intrinsic = max(spot - strike, 0.0)
    if t <= 0 or sigma <= 1e-9:
        return intrinsic
    vol_sqrt_t = sigma * math.sqrt(t)
    if vol_sqrt_t <= 0:
        return intrinsic
    d1 = (math.log(spot / strike) + 0.5 * sigma * sigma * t) / vol_sqrt_t
    d2 = d1 - vol_sqrt_t
    return spot * norm_cdf(d1) - strike * norm_cdf(d2)


def bs_delta(spot: float, strike: float, t: float, sigma: float) -> float:
    if t <= 0 or sigma <= 1e-9:
        return 1.0 if spot > strike else 0.0
    vol_sqrt_t = sigma * math.sqrt(t)
    d1 = (math.log(spot / strike) + 0.5 * sigma * sigma * t) / vol_sqrt_t
    return norm_cdf(d1)


def bs_vega(spot: float, strike: float, t: float, sigma: float) -> float:
    if t <= 0 or sigma <= 1e-9:
        return 0.0
    vol_sqrt_t = sigma * math.sqrt(t)
    d1 = (math.log(spot / strike) + 0.5 * sigma * sigma * t) / vol_sqrt_t
    return spot * norm_pdf(d1) * math.sqrt(t)


def implied_vol(mid: float, spot: float, strike: float, t: float) -> Optional[float]:
    if not all(math.isfinite(x) for x in (mid, spot, strike, t)):
        return None
    if spot <= 0 or strike <= 0 or t <= 0:
        return None
    intrinsic = max(spot - strike, 0.0)
    if mid <= intrinsic + 1e-6:
        return None
    if mid >= spot:
        return None

    lo, hi = 1e-5, 6.0
    lo_price = bs_call_price(spot, strike, t, lo)
    hi_price = bs_call_price(spot, strike, t, hi)
    if mid < lo_price - 1e-6 or mid > hi_price + 1e-6:
        return None

    for _ in range(70):
        mid_sigma = (lo + hi) / 2.0
        price = bs_call_price(spot, strike, t, mid_sigma)
        if price < mid:
            lo = mid_sigma
        else:
            hi = mid_sigma
    return (lo + hi) / 2.0


def tte_days(day: int) -> float:
    # Historical day 0/1/2 correspond to TTE 8/7/6 days for the Round 3 data.
    return float(8 - day)


def read_prices(data_dir: Path) -> pd.DataFrame:
    frames = []
    for path in sorted(data_dir.glob("prices_round_*_day_*.csv")):
        df = pd.read_csv(path, sep=";")
        df["source_file"] = path.name
        frames.append(df)
    if not frames:
        raise FileNotFoundError(f"No prices_round_*_day_*.csv files found in {data_dir}")
    df = pd.concat(frames, ignore_index=True)

    numeric_cols = [c for c in df.columns if c.startswith(("bid_", "ask_")) or c in ("mid_price", "profit_and_loss")]
    for col in numeric_cols:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    df["day"] = pd.to_numeric(df["day"], errors="coerce").astype(int)
    df["timestamp"] = pd.to_numeric(df["timestamp"], errors="coerce").astype(int)
    df["global_ts"] = df["day"] * 1_000_000 + df["timestamp"]
    df["best_bid"] = df["bid_price_1"]
    df["best_ask"] = df["ask_price_1"]
    df["spread"] = df["best_ask"] - df["best_bid"]
    return df


def read_trades(data_dir: Path) -> pd.DataFrame:
    frames = []
    for path in sorted(data_dir.glob("trades_round_*_day_*.csv")):
        day = int(path.stem.split("_day_")[1])
        df = pd.read_csv(path, sep=";")
        df["day"] = day
        df["source_file"] = path.name
        frames.append(df)
    if not frames:
        return pd.DataFrame()
    df = pd.concat(frames, ignore_index=True)
    df["timestamp"] = pd.to_numeric(df["timestamp"], errors="coerce").astype(int)
    df["price"] = pd.to_numeric(df["price"], errors="coerce")
    df["quantity"] = pd.to_numeric(df["quantity"], errors="coerce")
    df["global_ts"] = df["day"] * 1_000_000 + df["timestamp"]
    return df


def pivot_field(df: pd.DataFrame, field: str, products: Iterable[str]) -> pd.DataFrame:
    out = (
        df[df["product"].isin(products)]
        .pivot_table(index=["day", "timestamp", "global_ts"], columns="product", values=field, aggfunc="first")
        .sort_index()
    )
    return out


def autocorr(values: np.ndarray, lag: int) -> Optional[float]:
    if len(values) <= lag + 2:
        return None
    a = values[:-lag]
    b = values[lag:]
    mask = np.isfinite(a) & np.isfinite(b)
    if mask.sum() < 5:
        return None
    a = a[mask]
    b = b[mask]
    if np.std(a) == 0 or np.std(b) == 0:
        return None
    return float(np.corrcoef(a, b)[0, 1])


def percentile(values: Iterable[float], pct: float) -> Optional[float]:
    arr = np.asarray([v for v in values if v is not None and math.isfinite(v)], dtype=float)
    if arr.size == 0:
        return None
    return float(np.percentile(arr, pct))


def fmt(value, digits: int = 3) -> str:
    if value is None:
        return "n/a"
    if isinstance(value, (int, np.integer)):
        return str(int(value))
    if isinstance(value, float) and math.isfinite(value):
        return f"{value:.{digits}f}"
    return str(value)


def table(headers: List[str], rows: List[List[object]]) -> str:
    all_rows = [[str(x) for x in headers]] + [[str(x) for x in row] for row in rows]
    widths = [max(len(row[i]) for row in all_rows) for i in range(len(headers))]
    lines = []
    lines.append("  ".join(all_rows[0][i].rjust(widths[i]) for i in range(len(headers))))
    for row in all_rows[1:]:
        lines.append("  ".join(row[i].rjust(widths[i]) for i in range(len(headers))))
    return "\n".join(lines)


def fit_smile(group: pd.DataFrame) -> Tuple[Optional[np.ndarray], int]:
    candidates = group[
        (group["iv"].notna())
        & (group["extrinsic"] >= 0.5)
        & (group["mid"] > 0)
        & (group["spread"].notna())
        & (group["spread"] <= np.maximum(20.0, group["mid"].abs() * 0.60))
    ].copy()
    if len(candidates) < 4:
        return None, len(candidates)

    x = candidates["moneyness"].to_numpy(dtype=float)
    y = candidates["iv"].to_numpy(dtype=float)
    weights = np.sqrt(np.maximum(candidates["vega"].to_numpy(dtype=float), 1.0))

    try:
        coef = np.polyfit(x, y, deg=2, w=weights)
    except np.linalg.LinAlgError:
        return None, len(candidates)

    residual = y - np.polyval(coef, x)
    med = np.median(residual)
    mad = np.median(np.abs(residual - med))
    if mad > 1e-9 and len(candidates) >= 6:
        keep = np.abs(residual - med) <= 3.5 * mad
        if keep.sum() >= 4 and keep.sum() < len(candidates):
            try:
                coef = np.polyfit(x[keep], y[keep], deg=2, w=weights[keep])
            except np.linalg.LinAlgError:
                pass
    return coef, len(candidates)


def build_option_frame(prices: pd.DataFrame) -> pd.DataFrame:
    products = [UNDERLYING] + list(OPTIONS)
    mids = pivot_field(prices, "mid_price", products)
    bids = pivot_field(prices, "best_bid", products)
    asks = pivot_field(prices, "best_ask", products)
    spreads = pivot_field(prices, "spread", products)

    records = []
    for idx, row in mids.iterrows():
        day, timestamp, global_ts = idx
        spot = row.get(UNDERLYING)
        if not math.isfinite(spot):
            continue
        t_days = tte_days(day)
        t = t_days / 365.0
        for product, strike in OPTIONS.items():
            mid = row.get(product)
            if mid is None or not math.isfinite(mid):
                continue
            bid = bids.loc[idx].get(product)
            ask = asks.loc[idx].get(product)
            spread = spreads.loc[idx].get(product)
            intrinsic = max(spot - strike, 0.0)
            extrinsic = mid - intrinsic
            money = math.log(strike / spot) / math.sqrt(t) if spot > 0 and t > 0 else np.nan
            iv = implied_vol(float(mid), float(spot), float(strike), float(t))
            vega = bs_vega(float(spot), float(strike), float(t), float(iv)) if iv is not None else np.nan
            delta = bs_delta(float(spot), float(strike), float(t), float(iv)) if iv is not None else np.nan
            records.append(
                {
                    "day": day,
                    "timestamp": timestamp,
                    "global_ts": global_ts,
                    "product": product,
                    "strike": strike,
                    "spot": float(spot),
                    "tte_days": t_days,
                    "mid": float(mid),
                    "bid": float(bid) if bid is not None and math.isfinite(bid) else np.nan,
                    "ask": float(ask) if ask is not None and math.isfinite(ask) else np.nan,
                    "spread": float(spread) if spread is not None and math.isfinite(spread) else np.nan,
                    "intrinsic": intrinsic,
                    "extrinsic": extrinsic,
                    "moneyness": money,
                    "iv": iv,
                    "vega": vega,
                    "delta": delta,
                }
            )

    opt = pd.DataFrame(records)
    fair_iv = []
    model = []
    smile_n = []
    for _, group in opt.groupby(["day", "timestamp"], sort=False):
        coef, n = fit_smile(group)
        for _, r in group.iterrows():
            if coef is None:
                fair_iv.append(np.nan)
                model.append(np.nan)
                smile_n.append(n)
            else:
                iv_fit = max(1e-5, float(np.polyval(coef, r["moneyness"])))
                fair_iv.append(iv_fit)
                model.append(bs_call_price(float(r["spot"]), float(r["strike"]), float(r["tte_days"]) / 365.0, iv_fit))
                smile_n.append(n)

    opt["fair_iv"] = fair_iv
    opt["model_price"] = model
    opt["smile_n"] = smile_n
    opt["residual"] = opt["mid"] - opt["model_price"]
    opt["residual_over_spread"] = opt["residual"] / opt["spread"].replace(0, np.nan)
    return opt


def analyze_underlying(prices: pd.DataFrame) -> Dict:
    under = prices[prices["product"] == UNDERLYING].sort_values(["day", "timestamp"]).copy()
    out: Dict = {}
    day_rows = []
    for day, g in under.groupby("day"):
        s = g["mid_price"].to_numpy(dtype=float)
        r = np.diff(s)
        day_rows.append(
            {
                "day": int(day),
                "n": int(len(s)),
                "start": float(s[0]),
                "end": float(s[-1]),
                "min": float(np.min(s)),
                "max": float(np.max(s)),
                "stdev_step": float(np.std(r)),
                "mean_abs_step": float(np.mean(np.abs(r))),
            }
        )
    out["day_stats"] = day_rows

    s_all = under["mid_price"].to_numpy(dtype=float)
    returns = np.diff(s_all)
    out["return_autocorr"] = {str(lag): autocorr(returns, lag) for lag in [1, 2, 5, 10, 20, 50, 100]}

    horizons = [10, 25, 50, 100, 250, 500]
    ema_span = 80
    under["ema"] = under.groupby("day")["mid_price"].transform(lambda x: x.ewm(span=ema_span, adjust=False).mean())
    under["dev"] = under["mid_price"] - under["ema"]
    dev = under["dev"].to_numpy(dtype=float)
    price = under["mid_price"].to_numpy(dtype=float)
    q_low = np.nanpercentile(dev, 5)
    q_high = np.nanpercentile(dev, 95)
    ema_rows = []
    for h in horizons:
        future = np.empty_like(price)
        future[:] = np.nan
        for _, idxs in under.groupby("day").indices.items():
            idxs = np.asarray(idxs)
            valid = idxs[:-h] if len(idxs) > h else np.array([], dtype=int)
            if len(valid):
                future[valid] = price[valid + h] - price[valid]
        low_mask = dev <= q_low
        high_mask = dev >= q_high
        ema_rows.append(
            {
                "horizon": h,
                "low_n": int(np.isfinite(future[low_mask]).sum()),
                "low_future_move": float(np.nanmean(future[low_mask])),
                "low_up_pct": float(np.nanmean(future[low_mask] > 0) * 100),
                "high_n": int(np.isfinite(future[high_mask]).sum()),
                "high_future_move": float(np.nanmean(future[high_mask])),
                "high_down_pct": float(np.nanmean(future[high_mask] < 0) * 100),
            }
        )
    out["ema_reversion"] = {"span": ema_span, "low_dev_p05": float(q_low), "high_dev_p95": float(q_high), "rows": ema_rows}
    return out


def residual_autocorr(opt: pd.DataFrame) -> Dict:
    rows = []
    for product, g in opt.dropna(subset=["residual"]).groupby("product"):
        g = g.sort_values(["day", "timestamp"])
        residual = g["residual"].to_numpy(dtype=float)
        delta = np.diff(residual)
        rows.append(
            {
                "product": product,
                "n": int(len(g)),
                "resid_std": float(np.nanstd(residual)),
                "resid_p05": percentile(residual, 5),
                "resid_p95": percentile(residual, 95),
                "level_ac1": autocorr(residual, 1),
                "delta_ac1": autocorr(delta, 1),
                "delta_ac5": autocorr(delta, 5),
            }
        )
    return {"rows": rows}


def conditional_residual_reversion(opt: pd.DataFrame) -> Dict:
    horizons = [1, 5, 10, 25, 50, 100]
    entry_z = 1.25
    rows = []
    for product, g in opt.dropna(subset=["residual"]).groupby("product"):
        g = g.sort_values(["day", "timestamp"]).copy()
        resid = g["residual"].to_numpy(dtype=float)
        med = np.nanmedian(resid)
        std = np.nanstd(resid)
        if not math.isfinite(std) or std <= 1e-9:
            continue
        z = (resid - med) / std
        for h in horizons:
            future_change = np.full(len(g), np.nan)
            for _, idxs in g.groupby("day").indices.items():
                idxs = np.asarray(idxs)
                if len(idxs) > h:
                    local = np.arange(len(idxs) - h)
                    future_change[idxs[local]] = resid[idxs[local + h]] - resid[idxs[local]]
            low_mask = z <= -entry_z
            high_mask = z >= entry_z
            rows.append(
                {
                    "product": product,
                    "horizon": h,
                    "low_n": int(np.isfinite(future_change[low_mask]).sum()),
                    "low_future_resid_change": float(np.nanmean(future_change[low_mask])) if np.isfinite(future_change[low_mask]).any() else None,
                    "low_mean_revert_pct": float(np.nanmean(future_change[low_mask] > 0) * 100) if np.isfinite(future_change[low_mask]).any() else None,
                    "high_n": int(np.isfinite(future_change[high_mask]).sum()),
                    "high_future_resid_change": float(np.nanmean(future_change[high_mask])) if np.isfinite(future_change[high_mask]).any() else None,
                    "high_mean_revert_pct": float(np.nanmean(future_change[high_mask] < 0) * 100) if np.isfinite(future_change[high_mask]).any() else None,
                }
            )
    return {"entry_z": entry_z, "rows": rows}


def edge_after_spread(opt: pd.DataFrame) -> Dict:
    rows = []
    horizons = [5, 10, 25, 50, 100]
    thresholds = [0.0, 1.0, 2.0, 3.0, 5.0]
    for product, g in opt.dropna(subset=["model_price", "bid", "ask"]).groupby("product"):
        g = g.sort_values(["day", "timestamp"]).copy()
        mid = g["mid"].to_numpy(dtype=float)
        bid = g["bid"].to_numpy(dtype=float)
        ask = g["ask"].to_numpy(dtype=float)
        model = g["model_price"].to_numpy(dtype=float)
        for h in horizons:
            future_mid = np.full(len(g), np.nan)
            for _, idxs in g.groupby("day").indices.items():
                idxs = np.asarray(idxs)
                if len(idxs) > h:
                    local = np.arange(len(idxs) - h)
                    future_mid[idxs[local]] = mid[idxs[local + h]]
            for threshold in thresholds:
                buy_mask = model - ask >= threshold
                sell_mask = bid - model >= threshold
                buy_pnl = future_mid[buy_mask] - ask[buy_mask]
                sell_pnl = bid[sell_mask] - future_mid[sell_mask]
                combined = np.concatenate([buy_pnl[np.isfinite(buy_pnl)], sell_pnl[np.isfinite(sell_pnl)]])
                if combined.size == 0:
                    continue
                rows.append(
                    {
                        "product": product,
                        "horizon": h,
                        "threshold": threshold,
                        "signals": int(combined.size),
                        "buy_signals": int(np.isfinite(buy_pnl).sum()),
                        "sell_signals": int(np.isfinite(sell_pnl).sum()),
                        "mean_pnl": float(np.mean(combined)),
                        "median_pnl": float(np.median(combined)),
                        "win_pct": float(np.mean(combined > 0) * 100),
                        "p05": float(np.percentile(combined, 5)),
                    }
                )
    return {"rows": rows}


def option_summary(opt: pd.DataFrame) -> Dict:
    rows = []
    for product, g in opt.groupby("product"):
        rows.append(
            {
                "product": product,
                "strike": int(g["strike"].iloc[0]),
                "n": int(len(g)),
                "mid_median": percentile(g["mid"], 50),
                "spread_median": percentile(g["spread"], 50),
                "spread_p95": percentile(g["spread"], 95),
                "iv_valid_pct": float(g["iv"].notna().mean() * 100),
                "iv_median": percentile(g["iv"].dropna(), 50),
                "delta_median": percentile(g["delta"].dropna(), 50),
                "extrinsic_median": percentile(g["extrinsic"], 50),
                "smile_resid_std": percentile([np.nanstd(g["residual"])], 50),
            }
        )
    return {"rows": rows}


def trade_summary(trades: pd.DataFrame, prices: pd.DataFrame) -> Dict:
    if trades.empty:
        return {"rows": []}
    products = [UNDERLYING] + list(OPTIONS)
    mids = pivot_field(prices, "mid_price", products).reset_index()
    price_lookup = mids.set_index(["day", "timestamp"])

    rows = []
    for product, g in trades[trades["symbol"].isin(products)].groupby("symbol"):
        gaps = []
        qty = []
        for _, r in g.iterrows():
            try:
                mid = price_lookup.loc[(int(r["day"]), int(r["timestamp"])), product]
            except Exception:
                continue
            if pd.notna(mid):
                gaps.append(float(r["price"]) - float(mid))
                qty.append(float(r["quantity"]))
        rows.append(
            {
                "product": product,
                "trades": int(len(g)),
                "qty_mean": float(np.mean(qty)) if qty else None,
                "qty_counts": {str(int(k)): int(v) for k, v in g["quantity"].value_counts().sort_index().items()},
                "trade_minus_mid_mean": float(np.mean(gaps)) if gaps else None,
                "trade_minus_mid_p05": percentile(gaps, 5),
                "trade_minus_mid_p95": percentile(gaps, 95),
            }
        )
    return {"rows": rows}


def public_trade_markouts(trades: pd.DataFrame, opt: pd.DataFrame) -> Dict:
    if trades.empty:
        return {"rows": []}

    state = opt[["day", "timestamp", "product", "mid", "bid", "ask", "spread", "residual"]].rename(columns={"product": "symbol"})
    merged = trades.merge(state, on=["day", "timestamp", "symbol"], how="left")
    merged = merged[merged["symbol"].isin(OPTIONS)].dropna(subset=["mid"])
    rows = []
    horizons = [5, 10, 25, 50, 100, 250]

    for product, g in merged.groupby("symbol"):
        series = opt[opt["product"] == product].sort_values(["day", "timestamp"]).copy()
        for horizon in horizons:
            future_mid = {}
            for day, gd in series.groupby("day"):
                gd = gd.reset_index(drop=True)
                if len(gd) <= horizon:
                    continue
                for i in range(len(gd) - horizon):
                    future_mid[(int(day), int(gd.loc[i, "timestamp"]))] = float(gd.loc[i + horizon, "mid"])

            maker_pnl = []
            bid_hits = ask_hits = middle_prints = 0
            buy_trades = sell_trades = 0
            for _, row in g.iterrows():
                key = (int(row["day"]), int(row["timestamp"]))
                if key not in future_mid:
                    continue
                future = future_mid[key]

                if row["price"] <= row["mid"]:
                    maker_pnl.append((future - row["price"]) * row["quantity"])
                    buy_trades += 1
                    if row["price"] <= row["bid"] + 1e-9:
                        bid_hits += 1
                    else:
                        middle_prints += 1
                else:
                    maker_pnl.append((row["price"] - future) * row["quantity"])
                    sell_trades += 1
                    if row["price"] >= row["ask"] - 1e-9:
                        ask_hits += 1
                    else:
                        middle_prints += 1

            if maker_pnl:
                arr = np.asarray(maker_pnl, dtype=float)
                rows.append(
                    {
                        "product": product,
                        "horizon": horizon,
                        "trades": int(arr.size),
                        "bid_hits": int(bid_hits),
                        "ask_hits": int(ask_hits),
                        "middle_prints": int(middle_prints),
                        "maker_buy_trades": int(buy_trades),
                        "maker_sell_trades": int(sell_trades),
                        "mean_qty_pnl": float(np.mean(arr)),
                        "median_qty_pnl": float(np.median(arr)),
                        "win_pct": float(np.mean(arr > 0) * 100),
                        "p05": float(np.percentile(arr, 5)),
                    }
                )
    return {"rows": rows}


def best_edge_rows(edge: Dict) -> List[Dict]:
    rows = edge["rows"]
    useful = [
        r
        for r in rows
        if r["signals"] >= 50 and r["mean_pnl"] > 0 and r["win_pct"] >= 50 and r["p05"] > -30
    ]
    useful.sort(key=lambda r: (r["mean_pnl"] * math.sqrt(r["signals"]), r["mean_pnl"]), reverse=True)
    return useful[:30]


def make_report(results: Dict) -> str:
    lines = []
    lines.append("VELVETFRUIT_EXTRACT / VEV Options Research")
    lines.append("=" * 52)
    lines.append("")
    lines.append("Context from Frankfurt Hedgehogs 2025")
    lines.append("- Fit an IV smile across options, convert fitted IV back to model prices, and scalp option residuals.")
    lines.append("- Treat underlying mean reversion separately; it can work, but it is more volatile than IV residual scalping.")
    lines.append("- Prefer structural explanations and stable parameter regions over max historical PnL.")
    lines.append("")

    lines.append("Underlying Summary")
    lines.append(table(
        ["day", "n", "start", "end", "min", "max", "step_sd", "abs_step"],
        [
            [
                r["day"],
                r["n"],
                fmt(r["start"], 1),
                fmt(r["end"], 1),
                fmt(r["min"], 1),
                fmt(r["max"], 1),
                fmt(r["stdev_step"], 3),
                fmt(r["mean_abs_step"], 3),
            ]
            for r in results["underlying"]["day_stats"]
        ],
    ))
    lines.append("")
    lines.append("Underlying one-step return autocorrelation")
    lines.append(table(
        ["lag", "corr"],
        [[lag, fmt(corr, 4)] for lag, corr in results["underlying"]["return_autocorr"].items()],
    ))
    lines.append("")
    ema = results["underlying"]["ema_reversion"]
    lines.append(f"Underlying EMA reversion test: span={ema['span']}, low_dev_p05={fmt(ema['low_dev_p05'],2)}, high_dev_p95={fmt(ema['high_dev_p95'],2)}")
    lines.append(table(
        ["h", "low_n", "low_move", "low_up%", "high_n", "high_move", "high_down%"],
        [
            [
                r["horizon"],
                r["low_n"],
                fmt(r["low_future_move"], 2),
                fmt(r["low_up_pct"], 1),
                r["high_n"],
                fmt(r["high_future_move"], 2),
                fmt(r["high_down_pct"], 1),
            ]
            for r in ema["rows"]
        ],
    ))
    lines.append("")

    lines.append("Option Market Summary")
    lines.append(table(
        ["product", "K", "mid_med", "spr_med", "spr_p95", "iv_valid%", "iv_med", "delta_med", "extr_med", "resid_sd"],
        [
            [
                r["product"],
                r["strike"],
                fmt(r["mid_median"], 2),
                fmt(r["spread_median"], 2),
                fmt(r["spread_p95"], 2),
                fmt(r["iv_valid_pct"], 1),
                fmt(r["iv_median"], 3),
                fmt(r["delta_median"], 3),
                fmt(r["extrinsic_median"], 2),
                fmt(r["smile_resid_std"], 3),
            ]
            for r in results["option_summary"]["rows"]
        ],
    ))
    lines.append("")

    lines.append("Residual Autocorrelation")
    lines.append(table(
        ["product", "n", "resid_sd", "p05", "p95", "level_ac1", "d_ac1", "d_ac5"],
        [
            [
                r["product"],
                r["n"],
                fmt(r["resid_std"], 3),
                fmt(r["resid_p05"], 2),
                fmt(r["resid_p95"], 2),
                fmt(r["level_ac1"], 4),
                fmt(r["delta_ac1"], 4),
                fmt(r["delta_ac5"], 4),
            ]
            for r in results["residual_autocorr"]["rows"]
        ],
    ))
    lines.append("")

    lines.append("Residual Mean-Reversion Check (entry at +/-1.25 residual stdev)")
    interesting = []
    for r in results["conditional_reversion"]["rows"]:
        if r["horizon"] in (5, 10, 25, 50) and (r["low_n"] >= 30 or r["high_n"] >= 30):
            interesting.append(r)
    interesting = interesting[:80]
    lines.append(table(
        ["product", "h", "low_n", "low_dres", "low_rev%", "high_n", "high_dres", "high_rev%"],
        [
            [
                r["product"],
                r["horizon"],
                r["low_n"],
                fmt(r["low_future_resid_change"], 3),
                fmt(r["low_mean_revert_pct"], 1),
                r["high_n"],
                fmt(r["high_future_resid_change"], 3),
                fmt(r["high_mean_revert_pct"], 1),
            ]
            for r in interesting
        ],
    ))
    lines.append("")

    lines.append("Best Edge-After-Spread Tests")
    best = results["best_edge_after_spread"]
    lines.append(table(
        ["product", "h", "thr", "signals", "buy", "sell", "mean", "median", "win%", "p05"],
        [
            [
                r["product"],
                r["horizon"],
                fmt(r["threshold"], 1),
                r["signals"],
                r["buy_signals"],
                r["sell_signals"],
                fmt(r["mean_pnl"], 3),
                fmt(r["median_pnl"], 3),
                fmt(r["win_pct"], 1),
                fmt(r["p05"], 2),
            ]
            for r in best
        ],
    ))
    lines.append("")

    lines.append("Public Trade Summary")
    lines.append(table(
        ["product", "trades", "qty_mean", "gap_mean", "gap_p05", "gap_p95", "qty_counts"],
        [
            [
                r["product"],
                r["trades"],
                fmt(r["qty_mean"], 2),
                fmt(r["trade_minus_mid_mean"], 2),
                fmt(r["trade_minus_mid_p05"], 2),
                fmt(r["trade_minus_mid_p95"], 2),
                json.dumps(r["qty_counts"], separators=(",", ":")),
            ]
            for r in results["trade_summary"]["rows"]
        ],
    ))
    lines.append("")

    lines.append("Public Trade Maker Markouts")
    markout_rows = [
        r
        for r in results["public_trade_markouts"]["rows"]
        if r["horizon"] in (5, 25, 50, 100) and r["trades"] >= 20
    ]
    lines.append(table(
        ["product", "h", "trades", "bid_hits", "ask_hits", "maker_buy", "maker_sell", "mean_qty_pnl", "median", "win%", "p05"],
        [
            [
                r["product"],
                r["horizon"],
                r["trades"],
                r["bid_hits"],
                r["ask_hits"],
                r["maker_buy_trades"],
                r["maker_sell_trades"],
                fmt(r["mean_qty_pnl"], 3),
                fmt(r["median_qty_pnl"], 3),
                fmt(r["win_pct"], 1),
                fmt(r["p05"], 2),
            ]
            for r in markout_rows
        ],
    ))
    lines.append("")

    lines.append("Initial Interpretation")
    lines.append("- Prioritize IV residual scalping over outright underlying prediction if residual mean reversion survives spread costs.")
    lines.append("- Underlying mean reversion exists only if EMA-deviation tests show consistent opposite future moves; size it much smaller than option residual positions.")
    lines.append("- Ignore or heavily downweight options with poor IV validity / tiny extrinsic / very wide proportional spreads.")
    lines.append("- First algorithm should trade only the most liquid/high-vega vouchers with residuals large enough to beat spread, and optionally carry a small underlying mean-reversion sleeve.")
    return "\n".join(lines)


def main() -> None:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    prices = read_prices(DATA_DIR)
    trades = read_trades(DATA_DIR)
    opt = build_option_frame(prices)

    results = {
        "underlying": analyze_underlying(prices),
        "option_summary": option_summary(opt),
        "residual_autocorr": residual_autocorr(opt),
        "conditional_reversion": conditional_residual_reversion(opt),
        "edge_after_spread": edge_after_spread(opt),
        "trade_summary": trade_summary(trades, prices),
        "public_trade_markouts": public_trade_markouts(trades, opt),
    }
    results["best_edge_after_spread"] = best_edge_rows(results["edge_after_spread"])

    report = make_report(results)
    digest = hashlib.md5(report.encode("utf-8")).hexdigest()[:8]
    text_path = REPORT_DIR / f"velvet_options_research_{digest}.txt"
    json_path = REPORT_DIR / f"velvet_options_research_{digest}.json"
    csv_path = REPORT_DIR / f"velvet_option_residuals_{digest}.csv"

    text_path.write_text(report, encoding="utf-8")
    json_path.write_text(json.dumps(results, indent=2), encoding="utf-8")
    opt.to_csv(csv_path, index=False)

    print(report)
    print("")
    print(f"Wrote {text_path}")
    print(f"Wrote {json_path}")
    print(f"Wrote {csv_path}")


if __name__ == "__main__":
    main()
