from __future__ import annotations

import csv
import io
import json
import math
import statistics
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parent
REPO_ROOT = ROOT.parents[1]
RUNS = REPO_ROOT / "tools" / "backtester" / "Runs"
OUT = ROOT / "optimizer_reports"
OUT.mkdir(exist_ok=True)

STRATEGIES = [
    "ColdSteel",
    "ColdSteelSkew0Probe",
    "ColdSteelSkew030Probe",
    "ColdSteelDynamic1500",
    "ColdSteelPairFairProbe",
    "ColdSteelPairProbe",
    "ColdSteelFactorProbe",
    "ColdSteelAllTrendProbe",
    "ColdSteelOffset2Probe",
    "ColdSteelOffset0Probe",
    "BoneSaw",
    "Alternative_from_IMC",
    "GutHook",
]


def latest_archive(strategy: str) -> Path | None:
    matches = sorted(
        RUNS.glob(f"bt_{strategy}_stitched_*.zip"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    return matches[0] if matches else None


def payload(path: Path) -> dict:
    with zipfile.ZipFile(path) as archive:
        names = archive.namelist()
        for name in names:
            if name.endswith(".json") and not name.endswith("_summary.json"):
                data = json.loads(archive.read(name).decode("utf-8", errors="replace"))
                if data.get("graphLog"):
                    return data
        for name in names:
            if name.endswith(".log"):
                data = json.loads(archive.read(name).decode("utf-8", errors="replace"))
                if data.get("graphLog"):
                    return data
    raise RuntimeError(f"No graphLog found in {path}")


def graph_points(data: dict) -> list[tuple[int, float]]:
    rows = csv.DictReader(io.StringIO(data["graphLog"]), delimiter=";")
    return [(int(float(row["timestamp"])), float(row["value"])) for row in rows]


def max_drawdown(values: list[float]) -> float:
    peak = values[0]
    out = 0.0
    for value in values:
        if value > peak:
            peak = value
        out = max(out, peak - value)
    return out


def sharpe(values: list[float]) -> float:
    diffs = [values[i] - values[i - 1] for i in range(1, len(values))]
    if len(diffs) < 2:
        return 0.0
    sd = statistics.pstdev(diffs)
    if sd <= 1e-12:
        return 0.0
    return statistics.mean(diffs) / sd * math.sqrt(len(diffs))


def percentile(values: list[float], q: float) -> float:
    if not values:
        return 0.0
    vals = sorted(values)
    pos = (len(vals) - 1) * q
    lo = int(math.floor(pos))
    hi = int(math.ceil(pos))
    if lo == hi:
        return vals[lo]
    return vals[lo] * (hi - pos) + vals[hi] * (pos - lo)


def rolling_windows(points: list[tuple[int, float]], window: int, stride: int) -> list[dict]:
    ts = [p[0] for p in points]
    vals = [p[1] for p in points]
    rows = []
    for start in range(0, len(vals) - window + 1, stride):
        end = start + window - 1
        segment = vals[start : end + 1]
        pnl = segment[-1] - segment[0]
        dd = max_drawdown(segment)
        rows.append(
            {
                "start_idx": start,
                "end_idx": end,
                "start_ts": ts[start],
                "end_ts": ts[end],
                "pnl": pnl,
                "max_dd": dd,
                "sharpe": sharpe(segment),
                "return_over_dd": pnl / dd if dd > 1e-12 else 0.0,
            }
        )
    return rows


def summarize(name: str, archive: Path, windows: list[dict], total: float, full_dd: float) -> dict:
    pnls = [row["pnl"] for row in windows]
    dds = [row["max_dd"] for row in windows]
    sharpes = [row["sharpe"] for row in windows]
    score = percentile(pnls, 0.10) + 0.25 * statistics.median(pnls) - 0.35 * percentile(dds, 0.95)
    return {
        "strategy": name,
        "archive": str(archive),
        "total_pnl": total,
        "full_max_dd": full_dd,
        "windows": len(windows),
        "positive_windows": sum(1 for pnl in pnls if pnl > 0),
        "worst_pnl": min(pnls),
        "p01_pnl": percentile(pnls, 0.01),
        "p05_pnl": percentile(pnls, 0.05),
        "p10_pnl": percentile(pnls, 0.10),
        "median_pnl": statistics.median(pnls),
        "mean_pnl": statistics.mean(pnls),
        "best_pnl": max(pnls),
        "mean_dd": statistics.mean(dds),
        "p95_dd": percentile(dds, 0.95),
        "worst_dd": max(dds),
        "median_sharpe": statistics.median(sharpes),
        "mean_sharpe": statistics.mean(sharpes),
        "terminal_first_score": score,
    }


def write_csv(path: Path, rows: list[dict]) -> None:
    if not rows:
        return
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    window = 10_000
    stride = 100
    summaries = []
    detail = {}
    for strategy in STRATEGIES:
        archive = latest_archive(strategy)
        if archive is None:
            continue
        data = payload(archive)
        points = graph_points(data)
        if len(points) < window:
            continue
        values = [p[1] for p in points]
        windows = rolling_windows(points, window, stride)
        summary = summarize(strategy, archive, windows, values[-1], max_drawdown(values))
        summaries.append(summary)
        detail[strategy] = {
            "summary": summary,
            "worst_windows": sorted(windows, key=lambda row: row["pnl"])[:10],
            "best_windows": sorted(windows, key=lambda row: row["pnl"], reverse=True)[:10],
            "worst_drawdown_windows": sorted(windows, key=lambda row: row["max_dd"], reverse=True)[:10],
        }
        write_csv(OUT / f"rolling_10k_{strategy}.csv", windows)

    summaries.sort(key=lambda row: row["terminal_first_score"], reverse=True)
    (OUT / "r5_10k_decision_summary.json").write_text(json.dumps(summaries, indent=2), encoding="utf-8")
    (OUT / "r5_10k_decision_detail.json").write_text(json.dumps(detail, indent=2), encoding="utf-8")
    write_csv(OUT / "r5_10k_decision_summary.csv", summaries)

    print("Top by terminal-first 10k distribution score:")
    for row in summaries[:12]:
        print(
            f"{row['strategy']:28s} total={row['total_pnl']:10.1f} "
            f"median10k={row['median_pnl']:9.1f} p10={row['p10_pnl']:9.1f} "
            f"worst={row['worst_pnl']:9.1f} p95dd={row['p95_dd']:8.1f} "
            f"score={row['terminal_first_score']:9.1f}"
        )
    print(f"Wrote {OUT / 'r5_10k_decision_summary.json'}")


if __name__ == "__main__":
    main()
