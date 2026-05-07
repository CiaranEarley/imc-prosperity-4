from __future__ import annotations

import csv
import json
import math
from collections import defaultdict
from pathlib import Path
from statistics import NormalDist
from typing import Dict, Iterable, List, Optional, Tuple

import numpy as np


ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / "Price & Trade Data"
REPORTS_DIR = ROOT / "Reports"
OUT_TXT = REPORTS_DIR / "pca_price_research.txt"
OUT_JSON = REPORTS_DIR / "pca_price_research.json"

UNDERLYING = "VELVETFRUIT_EXTRACT"
HYDROGEL = "HYDROGEL_PACK"
OPTIONS = {
    "VEV_4000": 4000.0,
    "VEV_4500": 4500.0,
    "VEV_5000": 5000.0,
    "VEV_5100": 5100.0,
    "VEV_5200": 5200.0,
    "VEV_5300": 5300.0,
    "VEV_5400": 5400.0,
    "VEV_5500": 5500.0,
    "VEV_6000": 6000.0,
    "VEV_6500": 6500.0,
}
SMILE_PRODUCTS = ["VEV_5000", "VEV_5100", "VEV_5200", "VEV_5300", "VEV_5400", "VEV_5500"]
CORE_PRODUCTS = [HYDROGEL, UNDERLYING] + list(OPTIONS)
HORIZONS = [1, 10, 50, 100]
GLOBAL_DAY_STRIDE = 1_000_000
NORMAL = NormalDist()


def as_float(value: str) -> Optional[float]:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except Exception:
        return None


def parse_day_from_name(path: Path) -> int:
    stem = path.stem
    marker = "_day_"
    if marker not in stem:
        return 0
    return int(stem.split(marker, 1)[1].split("_", 1)[0])


def deepest_mid(row: dict) -> Optional[float]:
    bid = None
    ask = None
    for level in (1, 2, 3):
        candidate = as_float(row.get(f"bid_price_{level}"))
        if candidate is not None:
            bid = candidate
        candidate = as_float(row.get(f"ask_price_{level}"))
        if candidate is not None:
            ask = candidate
    if bid is None or ask is None:
        return as_float(row.get("mid_price"))
    return (bid + ask) / 2.0


def top_mid(row: dict) -> Optional[float]:
    bid = as_float(row.get("bid_price_1"))
    ask = as_float(row.get("ask_price_1"))
    if bid is None or ask is None:
        return as_float(row.get("mid_price"))
    return (bid + ask) / 2.0


def book_features(row: dict) -> dict:
    bid1 = as_float(row.get("bid_price_1"))
    ask1 = as_float(row.get("ask_price_1"))
    mid = top_mid(row)
    wall_mid = deepest_mid(row)
    spread = ask1 - bid1 if bid1 is not None and ask1 is not None else None
    bid_vols = []
    ask_vols = []
    for level in (1, 2, 3):
        bv = as_float(row.get(f"bid_volume_{level}"))
        av = as_float(row.get(f"ask_volume_{level}"))
        if bv is not None:
            bid_vols.append(bv)
        if av is not None:
            ask_vols.append(av)
    top_bid_vol = bid_vols[0] if bid_vols else None
    top_ask_vol = ask_vols[0] if ask_vols else None
    top_imbalance = None
    if top_bid_vol is not None and top_ask_vol is not None and top_bid_vol + top_ask_vol > 0:
        top_imbalance = (top_bid_vol - top_ask_vol) / (top_bid_vol + top_ask_vol)
    bid_depth = sum(bid_vols)
    ask_depth = sum(ask_vols)
    depth_imbalance = None
    if bid_depth + ask_depth > 0:
        depth_imbalance = (bid_depth - ask_depth) / (bid_depth + ask_depth)
    residual = None
    if mid is not None and wall_mid is not None:
        residual = mid - wall_mid
    return {
        "mid": mid,
        "wall_mid": wall_mid,
        "spread": spread,
        "top_imbalance": top_imbalance,
        "depth_imbalance": depth_imbalance,
        "mid_wall_residual": residual,
        "bid1": bid1,
        "ask1": ask1,
    }


def load_price_panel(data_dir: Path) -> Tuple[List[int], List[int], Dict[str, Dict[str, np.ndarray]]]:
    timestamp_days: Dict[int, int] = {}
    rows: Dict[Tuple[int, str], dict] = {}
    products = set()
    for path in sorted(data_dir.glob("prices_*.csv"), key=parse_day_from_name):
        with path.open(newline="") as handle:
            reader = csv.DictReader(handle, delimiter=";")
            for row in reader:
                day = int(float(row["day"]))
                timestamp = int(float(row["timestamp"]))
                global_ts = day * GLOBAL_DAY_STRIDE + timestamp
                product = row["product"]
                timestamp_days[global_ts] = day
                products.add(product)
                rows[(global_ts, product)] = book_features(row)

    timestamps = sorted(timestamp_days)
    days = [timestamp_days[ts] for ts in timestamps]
    features = ["mid", "wall_mid", "spread", "top_imbalance", "depth_imbalance", "mid_wall_residual", "bid1", "ask1"]
    panel: Dict[str, Dict[str, np.ndarray]] = {}
    for product in sorted(products):
        panel[product] = {feature: np.full(len(timestamps), np.nan) for feature in features}

    index = {ts: i for i, ts in enumerate(timestamps)}
    for (ts, product), feature_row in rows.items():
        i = index[ts]
        for feature, value in feature_row.items():
            if value is not None:
                panel[product][feature][i] = value
    return timestamps, days, panel


def load_trade_features(data_dir: Path, timestamps: List[int], days: List[int], panel: Dict[str, Dict[str, np.ndarray]]) -> Dict[str, Dict[str, np.ndarray]]:
    index = {ts: i for i, ts in enumerate(timestamps)}
    features: Dict[str, Dict[str, np.ndarray]] = {}
    for product in panel:
        features[product] = {
            "trade_count": np.zeros(len(timestamps)),
            "trade_qty": np.zeros(len(timestamps)),
            "signed_trade_qty": np.zeros(len(timestamps)),
        }

    for path in sorted(data_dir.glob("trades_*.csv"), key=parse_day_from_name):
        day = parse_day_from_name(path)
        with path.open(newline="") as handle:
            reader = csv.DictReader(handle)
            for row in reader:
                product = row.get("symbol")
                if product not in panel:
                    continue
                timestamp = int(float(row["timestamp"]))
                global_ts = day * GLOBAL_DAY_STRIDE + timestamp
                i = index.get(global_ts)
                if i is None:
                    continue
                qty = float(row.get("quantity") or 0.0)
                price = float(row.get("price") or 0.0)
                mid = panel[product]["mid"][i]
                bid = panel[product]["bid1"][i]
                ask = panel[product]["ask1"][i]
                sign = 0.0
                if not math.isnan(ask) and price >= ask:
                    sign = 1.0
                elif not math.isnan(bid) and price <= bid:
                    sign = -1.0
                elif not math.isnan(mid):
                    sign = 1.0 if price > mid else -1.0 if price < mid else 0.0
                features[product]["trade_count"][i] += 1.0
                features[product]["trade_qty"][i] += qty
                features[product]["signed_trade_qty"][i] += sign * qty
    return features


def valid_same_day(days: List[int], start: int, horizon: int) -> bool:
    return start + horizon < len(days) and days[start] == days[start + horizon]


def returns_matrix(
    panel: Dict[str, Dict[str, np.ndarray]],
    products: Iterable[str],
    days: List[int],
    feature: str = "wall_mid",
) -> Tuple[np.ndarray, List[str], np.ndarray]:
    product_list = [product for product in products if product in panel]
    if not product_list:
        return np.empty((0, 0)), [], np.array([], dtype=int)
    series = [panel[product][feature] for product in product_list]
    n = len(series[0])
    valid_indices = []
    rows = []
    for i in range(1, n):
        if days[i] != days[i - 1]:
            continue
        row = []
        ok = True
        for values in series:
            if math.isnan(values[i]) or math.isnan(values[i - 1]):
                ok = False
                break
            row.append(values[i] - values[i - 1])
        if ok:
            valid_indices.append(i)
            rows.append(row)
    return np.asarray(rows, dtype=float), product_list, np.asarray(valid_indices, dtype=int)


def zscore_matrix(matrix: np.ndarray) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    mean = np.mean(matrix, axis=0)
    std = np.std(matrix, axis=0)
    keep = std > 1e-12
    z = (matrix[:, keep] - mean[keep]) / std[keep]
    return z, mean, std


def pca(matrix: np.ndarray, names: List[str], max_components: int = 6) -> dict:
    if matrix.shape[0] < 5 or matrix.shape[1] < 2:
        return {"ok": False, "reason": "not enough rows or columns"}
    z, mean, std = zscore_matrix(matrix)
    names_kept = [name for name, keep in zip(names, std > 1e-12) if keep]
    if z.shape[1] < 2:
        return {"ok": False, "reason": "not enough non-constant columns"}
    u, s, vt = np.linalg.svd(z, full_matrices=False)
    eigenvalues = (s ** 2) / max(1, z.shape[0] - 1)
    explained = eigenvalues / np.sum(eigenvalues)
    scores = u * s
    components = vt
    component_rows = []
    for comp_idx in range(min(max_components, len(explained))):
        loadings = {name: float(components[comp_idx, i]) for i, name in enumerate(names_kept)}
        sorted_loadings = sorted(loadings.items(), key=lambda item: abs(item[1]), reverse=True)
        component_rows.append({
            "component": comp_idx + 1,
            "explained_variance": float(explained[comp_idx]),
            "top_loadings": sorted_loadings[:8],
            "loadings": loadings,
        })
    return {
        "ok": True,
        "rows": int(z.shape[0]),
        "columns": names_kept,
        "explained": [float(x) for x in explained[:max_components]],
        "components": component_rows,
        "scores": scores[:, : min(max_components, scores.shape[1])],
    }


def correlation(x: np.ndarray, y: np.ndarray) -> Optional[float]:
    mask = np.isfinite(x) & np.isfinite(y)
    if int(np.sum(mask)) < 30:
        return None
    xs = x[mask]
    ys = y[mask]
    if np.std(xs) <= 1e-12 or np.std(ys) <= 1e-12:
        return None
    return float(np.corrcoef(xs, ys)[0, 1])


def future_return(values: np.ndarray, indices: np.ndarray, days: List[int], horizon: int) -> np.ndarray:
    out = np.full(len(indices), np.nan)
    for row_idx, i in enumerate(indices):
        if valid_same_day(days, int(i), horizon):
            start = values[i]
            end = values[i + horizon]
            if not math.isnan(start) and not math.isnan(end):
                out[row_idx] = end - start
    return out


def pc_predictive_tests(
    pca_result: dict,
    indices: np.ndarray,
    panel: Dict[str, Dict[str, np.ndarray]],
    products: Iterable[str],
    days: List[int],
    horizons: Iterable[int] = HORIZONS,
) -> List[dict]:
    if not pca_result.get("ok"):
        return []
    scores = pca_result["scores"]
    rows = []
    for comp in range(min(4, scores.shape[1])):
        pc_score = scores[:, comp]
        for product in products:
            if product not in panel:
                continue
            values = panel[product]["wall_mid"]
            for horizon in horizons:
                fut = future_return(values, indices, days, horizon)
                corr = correlation(pc_score, fut)
                if corr is None:
                    continue
                lo_cut = np.nanpercentile(pc_score, 5)
                hi_cut = np.nanpercentile(pc_score, 95)
                lo_mean = float(np.nanmean(fut[pc_score <= lo_cut]))
                hi_mean = float(np.nanmean(fut[pc_score >= hi_cut]))
                rows.append({
                    "component": comp + 1,
                    "product": product,
                    "horizon": horizon,
                    "corr": corr,
                    "bottom_5pct_future_return": lo_mean,
                    "top_5pct_future_return": hi_mean,
                    "spread_top_minus_bottom": hi_mean - lo_mean,
                })
    rows.sort(key=lambda row: abs(row["corr"]), reverse=True)
    return rows


def norm_cdf(x: float) -> float:
    return NORMAL.cdf(x)


def black_scholes_call(spot: float, strike: float, t: float, vol: float) -> float:
    if t <= 0:
        return max(0.0, spot - strike)
    if vol <= 1e-8:
        return max(0.0, spot - strike)
    root_t = math.sqrt(t)
    d1 = (math.log(spot / strike) + 0.5 * vol * vol * t) / (vol * root_t)
    d2 = d1 - vol * root_t
    return spot * norm_cdf(d1) - strike * norm_cdf(d2)


def implied_vol_call(price: float, spot: float, strike: float, t: float) -> Optional[float]:
    if spot <= 0 or strike <= 0 or t <= 0:
        return None
    intrinsic = max(0.0, spot - strike)
    if price < intrinsic + 0.02:
        return None
    lo = 1e-4
    hi = 5.0
    hi_price = black_scholes_call(spot, strike, t, hi)
    if price > hi_price + 1e-6:
        return None
    for _ in range(50):
        mid = (lo + hi) / 2.0
        model = black_scholes_call(spot, strike, t, mid)
        if model < price:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2.0


def historical_tte(day: int) -> float:
    return max(0.25, 8.0 - day)


def build_iv_panel(timestamps: List[int], days: List[int], panel: Dict[str, Dict[str, np.ndarray]]) -> Tuple[np.ndarray, List[str], Dict[str, np.ndarray]]:
    names = [product for product in SMILE_PRODUCTS if product in panel]
    ivs = {product: np.full(len(timestamps), np.nan) for product in names}
    residuals = {product: np.full(len(timestamps), np.nan) for product in names}
    spot_series = panel[UNDERLYING]["wall_mid"] if UNDERLYING in panel else None
    if spot_series is None:
        return np.empty((0, 0)), [], residuals

    for i, day in enumerate(days):
        spot = spot_series[i]
        if math.isnan(spot) or spot <= 0:
            continue
        t = historical_tte(day) / 365.0
        xs = []
        ys = []
        valid_products = []
        for product in names:
            price = panel[product]["wall_mid"][i]
            if math.isnan(price):
                continue
            strike = OPTIONS[product]
            iv = implied_vol_call(float(price), float(spot), strike, t)
            if iv is None:
                continue
            moneyness = math.log(strike / spot) / math.sqrt(max(t, 1e-12))
            ivs[product][i] = iv
            xs.append(moneyness)
            ys.append(iv)
            valid_products.append(product)
        if len(xs) >= 4:
            coeffs = np.polyfit(np.asarray(xs), np.asarray(ys), 2)
            for product, x, y in zip(valid_products, xs, ys):
                fitted = float(coeffs[0] * x * x + coeffs[1] * x + coeffs[2])
                residuals[product][i] = y - fitted

    rows = []
    valid_indices = []
    for i in range(len(timestamps)):
        row = [ivs[product][i] for product in names]
        if all(np.isfinite(row)):
            rows.append(row)
            valid_indices.append(i)
    return np.asarray(rows, dtype=float), names, {"ivs": ivs, "residuals": residuals, "indices": np.asarray(valid_indices, dtype=int)}


def smile_residual_tests(
    iv_data: Dict[str, np.ndarray],
    panel: Dict[str, Dict[str, np.ndarray]],
    days: List[int],
    horizons: Iterable[int] = HORIZONS,
) -> List[dict]:
    residuals = iv_data["residuals"]
    rows = []
    for product, resid in residuals.items():
        if product not in panel:
            continue
        values = panel[product]["wall_mid"]
        for horizon in horizons:
            x_vals = []
            y_vals = []
            for i in range(len(values) - horizon):
                if days[i] != days[i + horizon]:
                    continue
                if np.isfinite(resid[i]) and np.isfinite(values[i]) and np.isfinite(values[i + horizon]):
                    x_vals.append(resid[i])
                    y_vals.append(values[i + horizon] - values[i])
            if len(x_vals) < 30:
                continue
            x = np.asarray(x_vals)
            y = np.asarray(y_vals)
            corr = correlation(x, y)
            if corr is None:
                continue
            lo_cut = np.nanpercentile(x, 5)
            hi_cut = np.nanpercentile(x, 95)
            rows.append({
                "product": product,
                "horizon": horizon,
                "corr_residual_to_future_price_return": corr,
                "bottom_5pct_future_return": float(np.nanmean(y[x <= lo_cut])),
                "top_5pct_future_return": float(np.nanmean(y[x >= hi_cut])),
                "residual_std": float(np.nanstd(x)),
            })
    rows.sort(key=lambda row: abs(row["corr_residual_to_future_price_return"]), reverse=True)
    return rows


def feature_matrix_for_product(
    product: str,
    panel: Dict[str, Dict[str, np.ndarray]],
    trades: Dict[str, Dict[str, np.ndarray]],
    days: List[int],
) -> Tuple[np.ndarray, List[str], np.ndarray]:
    if product not in panel:
        return np.empty((0, 0)), [], np.array([], dtype=int)
    p = panel[product]
    t = trades.get(product, {})
    mid = p["wall_mid"]
    features = {
        "return_1": np.full(len(mid), np.nan),
        "return_5": np.full(len(mid), np.nan),
        "spread": p["spread"],
        "top_imbalance": p["top_imbalance"],
        "depth_imbalance": p["depth_imbalance"],
        "mid_wall_residual": p["mid_wall_residual"],
        "trade_count": t.get("trade_count", np.zeros(len(mid))),
        "trade_qty": t.get("trade_qty", np.zeros(len(mid))),
        "signed_trade_qty": t.get("signed_trade_qty", np.zeros(len(mid))),
    }
    for i in range(1, len(mid)):
        if days[i] == days[i - 1] and np.isfinite(mid[i]) and np.isfinite(mid[i - 1]):
            features["return_1"][i] = mid[i] - mid[i - 1]
    for i in range(5, len(mid)):
        if days[i] == days[i - 5] and np.isfinite(mid[i]) and np.isfinite(mid[i - 5]):
            features["return_5"][i] = mid[i] - mid[i - 5]
    names = list(features)
    rows = []
    indices = []
    for i in range(len(mid)):
        row = [features[name][i] for name in names]
        if all(np.isfinite(row)):
            rows.append(row)
            indices.append(i)
    return np.asarray(rows, dtype=float), names, np.asarray(indices, dtype=int)


def direct_feature_tests(
    product: str,
    matrix: np.ndarray,
    names: List[str],
    indices: np.ndarray,
    panel: Dict[str, Dict[str, np.ndarray]],
    days: List[int],
) -> List[dict]:
    rows = []
    if product not in panel or matrix.size == 0:
        return rows
    values = panel[product]["wall_mid"]
    for col, name in enumerate(names):
        x = matrix[:, col]
        for horizon in HORIZONS:
            y = future_return(values, indices, days, horizon)
            corr = correlation(x, y)
            if corr is not None:
                rows.append({"product": product, "feature": name, "horizon": horizon, "corr": corr})
    rows.sort(key=lambda row: abs(row["corr"]), reverse=True)
    return rows


def feature_day_stability(
    product: str,
    feature: str,
    horizon: int,
    panel: Dict[str, Dict[str, np.ndarray]],
    trades: Dict[str, Dict[str, np.ndarray]],
    days: List[int],
) -> dict:
    matrix, names, indices = feature_matrix_for_product(product, panel, trades, days)
    if matrix.size == 0 or feature not in names:
        return {"product": product, "feature": feature, "horizon": horizon, "days": []}
    values = panel[product]["wall_mid"]
    col = names.index(feature)
    pooled = correlation(matrix[:, col], future_return(values, indices, days, horizon))
    day_rows = []
    for day in sorted(set(days)):
        mask = np.asarray([days[int(i)] == day for i in indices])
        corr = correlation(matrix[mask, col], future_return(values, indices[mask], days, horizon))
        day_rows.append({"day": int(day), "corr": corr, "samples": int(np.sum(mask))})
    return {
        "product": product,
        "feature": feature,
        "horizon": horizon,
        "pooled_corr": pooled,
        "days": day_rows,
    }


def smile_residual_day_stability(
    product: str,
    horizon: int,
    iv_data: Dict[str, np.ndarray],
    panel: Dict[str, Dict[str, np.ndarray]],
    days: List[int],
) -> dict:
    residuals = iv_data.get("residuals", {})
    if product not in residuals or product not in panel:
        return {"product": product, "horizon": horizon, "days": []}
    resid = residuals[product]
    values = panel[product]["wall_mid"]
    day_rows = []
    all_x = []
    all_y = []
    for day in sorted(set(days)):
        xs = []
        ys = []
        for i in range(len(values) - horizon):
            if days[i] != day or days[i + horizon] != day:
                continue
            if np.isfinite(resid[i]) and np.isfinite(values[i]) and np.isfinite(values[i + horizon]):
                xs.append(resid[i])
                ys.append(values[i + horizon] - values[i])
        if xs:
            all_x.extend(xs)
            all_y.extend(ys)
        corr = correlation(np.asarray(xs), np.asarray(ys)) if xs else None
        day_rows.append({"day": int(day), "corr": corr, "samples": len(xs)})
    return {
        "product": product,
        "horizon": horizon,
        "pooled_corr": correlation(np.asarray(all_x), np.asarray(all_y)) if all_x else None,
        "days": day_rows,
    }


def format_component(component: dict) -> str:
    parts = [f"{name}:{loading:+.3f}" for name, loading in component["top_loadings"]]
    return f"PC{component['component']} ({component['explained_variance']*100:.1f}%): " + ", ".join(parts)


def top_rows(rows: List[dict], key: str, n: int = 10) -> List[dict]:
    return sorted(rows, key=lambda row: abs(row.get(key, 0.0)), reverse=True)[:n]


def main() -> None:
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    timestamps, days, panel = load_price_panel(DATA_DIR)
    trades = load_trade_features(DATA_DIR, timestamps, days, panel)

    report = {
        "data_points": len(timestamps),
        "products": sorted(panel),
        "return_pca": {},
        "iv_pca": {},
        "feature_pca": {},
        "day_stability": {},
    }
    lines = []
    lines.append("PCA Price Research")
    lines.append("=" * 80)
    lines.append(f"Data points: {len(timestamps):,}")
    lines.append(f"Products: {', '.join(sorted(panel))}")
    lines.append("")

    for label, products in [
        ("all_products", CORE_PRODUCTS),
        ("velvet_complex", [UNDERLYING] + list(OPTIONS)),
        ("smile_options", SMILE_PRODUCTS),
    ]:
        matrix, names, indices = returns_matrix(panel, products, days)
        result = pca(matrix, names)
        report["return_pca"][label] = {k: v for k, v in result.items() if k != "scores"}
        lines.append(f"Return PCA: {label}")
        lines.append("-" * 80)
        if not result.get("ok"):
            lines.append(f"Skipped: {result.get('reason')}")
            lines.append("")
            continue
        for component in result["components"][:5]:
            lines.append(format_component(component))
        pred_rows = pc_predictive_tests(result, indices, panel, names, days)
        report["return_pca"][label]["predictive_tests"] = pred_rows[:40]
        lines.append("Top PC -> future return correlations:")
        for row in top_rows(pred_rows, "corr", 10):
            lines.append(
                f"  PC{row['component']} {row['product']} h={row['horizon']}: "
                f"corr={row['corr']:+.4f}, top-bottom={row['spread_top_minus_bottom']:+.4f}"
            )
        lines.append("")

    iv_matrix, iv_names, iv_data = build_iv_panel(timestamps, days, panel)
    iv_result = pca(iv_matrix, iv_names)
    report["iv_pca"] = {k: v for k, v in iv_result.items() if k != "scores"}
    lines.append("IV PCA: smile products")
    lines.append("-" * 80)
    if iv_result.get("ok"):
        for component in iv_result["components"][:5]:
            lines.append(format_component(component))
    else:
        lines.append(f"Skipped: {iv_result.get('reason')}")
    smile_tests = smile_residual_tests(iv_data, panel, days)
    report["iv_pca"]["smile_residual_tests"] = smile_tests[:50]
    lines.append("Top smile-residual -> future option price correlations:")
    for row in top_rows(smile_tests, "corr_residual_to_future_price_return", 12):
        lines.append(
            f"  {row['product']} h={row['horizon']}: "
            f"corr={row['corr_residual_to_future_price_return']:+.4f}, "
            f"bottom5={row['bottom_5pct_future_return']:+.4f}, top5={row['top_5pct_future_return']:+.4f}"
        )
    lines.append("")

    for product in [HYDROGEL, UNDERLYING, "VEV_4000", "VEV_5400", "VEV_5500"]:
        matrix, names, indices = feature_matrix_for_product(product, panel, trades, days)
        result = pca(matrix, names)
        direct = direct_feature_tests(product, matrix, names, indices, panel, days)
        pc_pred = pc_predictive_tests(result, indices, panel, [product], days) if result.get("ok") else []
        report["feature_pca"][product] = {
            "pca": {k: v for k, v in result.items() if k != "scores"},
            "direct_feature_tests": direct[:30],
            "pc_predictive_tests": pc_pred[:30],
        }
        lines.append(f"Microstructure Feature PCA: {product}")
        lines.append("-" * 80)
        if result.get("ok"):
            for component in result["components"][:4]:
                lines.append(format_component(component))
            lines.append("Top direct feature correlations:")
            for row in top_rows(direct, "corr", 8):
                lines.append(f"  {row['feature']} h={row['horizon']}: corr={row['corr']:+.4f}")
            lines.append("Top feature-PC correlations:")
            for row in top_rows(pc_pred, "corr", 8):
                lines.append(f"  PC{row['component']} h={row['horizon']}: corr={row['corr']:+.4f}")
        else:
            lines.append(f"Skipped: {result.get('reason')}")
        lines.append("")

    stability_checks = [
        (UNDERLYING, "top_imbalance", 1),
        (UNDERLYING, "mid_wall_residual", 1),
        ("VEV_5400", "return_1", 1),
        ("VEV_5400", "mid_wall_residual", 1),
        ("VEV_5400", "top_imbalance", 1),
        ("VEV_5500", "return_1", 1),
        ("VEV_5500", "return_5", 10),
        ("VEV_5500", "return_5", 50),
        ("VEV_5500", "mid_wall_residual", 1),
        ("VEV_5500", "top_imbalance", 1),
        (HYDROGEL, "mid_wall_residual", 1),
    ]
    feature_stability = [
        feature_day_stability(product, feature, horizon, panel, trades, days)
        for product, feature, horizon in stability_checks
    ]
    smile_stability = [
        smile_residual_day_stability(product, horizon, iv_data, panel, days)
        for product, horizon in [("VEV_5500", 10), ("VEV_5400", 1), ("VEV_5200", 1), ("VEV_5000", 1)]
    ]
    report["day_stability"] = {
        "features": feature_stability,
        "smile_residuals": smile_stability,
    }
    lines.append("Day-By-Day Stability Checks")
    lines.append("-" * 80)
    for row in feature_stability:
        pooled = row["pooled_corr"]
        day_text = ", ".join(
            f"d{day_row['day']}={day_row['corr']:+.4f}" if day_row["corr"] is not None else f"d{day_row['day']}=NA"
            for day_row in row["days"]
        )
        lines.append(
            f"{row['product']} {row['feature']} h={row['horizon']}: "
            f"pooled={pooled:+.4f} | {day_text}"
        )
    lines.append("")
    lines.append("Smile residual day stability:")
    for row in smile_stability:
        pooled = row["pooled_corr"]
        day_text = ", ".join(
            f"d{day_row['day']}={day_row['corr']:+.4f}" if day_row["corr"] is not None else f"d{day_row['day']}=NA"
            for day_row in row["days"]
        )
        lines.append(f"{row['product']} h={row['horizon']}: pooled={pooled:+.4f} | {day_text}")
    lines.append("")

    OUT_TXT.write_text("\n".join(lines), encoding="utf-8")
    OUT_JSON.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"Wrote {OUT_TXT}")
    print(f"Wrote {OUT_JSON}")


if __name__ == "__main__":
    main()
