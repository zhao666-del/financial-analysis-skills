#!/usr/bin/env python3
"""Calculate reproducible fund and benchmark metrics from normalized CSV."""

from __future__ import annotations

import argparse
import csv
import json
import math
import statistics
from datetime import datetime
from pathlib import Path


TRADING_DAYS = 252


def load_series(path: Path) -> tuple[list[str], list[float], list[float | None]]:
    dates: list[str] = []
    nav: list[float] = []
    benchmark: list[float | None] = []
    with path.open(encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            if not row.get("date") or not row.get("nav"):
                continue
            dates.append(row["date"])
            nav.append(float(row["nav"]))
            benchmark.append(float(row["benchmark"]) if row.get("benchmark") else None)
    order = sorted(range(len(dates)), key=dates.__getitem__)
    return (
        [dates[i] for i in order],
        [nav[i] for i in order],
        [benchmark[i] for i in order],
    )


def returns(values: list[float]) -> list[float]:
    return [values[i] / values[i - 1] - 1.0 for i in range(1, len(values))]


def annualized_return(values: list[float], dates: list[str]) -> float | None:
    if len(values) < 2 or values[0] <= 0:
        return None
    days = (datetime.fromisoformat(dates[-1]) - datetime.fromisoformat(dates[0])).days
    if days <= 0:
        return None
    return (values[-1] / values[0]) ** (365.25 / days) - 1.0


def annualized_volatility(r: list[float]) -> float | None:
    return statistics.stdev(r) * math.sqrt(TRADING_DAYS) if len(r) >= 2 else None


def max_drawdown(values: list[float]) -> dict:
    peak = values[0]
    peak_i = 0
    trough_i = 0
    best = 0.0
    best_peak_i = 0
    for i, value in enumerate(values):
        if value > peak:
            peak = value
            peak_i = i
        drawdown = value / peak - 1.0
        if drawdown < best:
            best = drawdown
            best_peak_i = peak_i
            trough_i = i
    recovery_i = None
    peak_value = values[best_peak_i]
    for i in range(trough_i + 1, len(values)):
        if values[i] >= peak_value:
            recovery_i = i
            break
    return {
        "max_drawdown": best,
        "peak_index": best_peak_i,
        "trough_index": trough_i,
        "recovery_index": recovery_i,
        "recovery_observations": None if recovery_i is None else recovery_i - trough_i,
        "recovered": recovery_i is not None,
    }


def downside_volatility(r: list[float], daily_rf: float) -> float | None:
    downside = [min(x - daily_rf, 0.0) for x in r]
    if len(downside) < 2:
        return None
    return math.sqrt(sum(x * x for x in downside) / len(downside)) * math.sqrt(TRADING_DAYS)


def covariance(x: list[float], y: list[float]) -> float:
    mx, my = statistics.mean(x), statistics.mean(y)
    return sum((a - mx) * (b - my) for a, b in zip(x, y)) / (len(x) - 1)


def regression_metrics(fund_r: list[float], bench_r: list[float]) -> dict:
    if len(fund_r) < 30 or len(fund_r) != len(bench_r):
        return {}
    var_b = statistics.variance(bench_r)
    beta = covariance(fund_r, bench_r) / var_b if var_b else None
    alpha_daily = statistics.mean(fund_r) - (beta or 0.0) * statistics.mean(bench_r)
    active = [a - b for a, b in zip(fund_r, bench_r)]
    te = statistics.stdev(active) * math.sqrt(TRADING_DAYS)
    active_ann = statistics.mean(active) * TRADING_DAYS
    up = [(a, b) for a, b in zip(fund_r, bench_r) if b > 0]
    down = [(a, b) for a, b in zip(fund_r, bench_r) if b < 0]
    return {
        "beta": beta,
        "alpha_annualized_arithmetic": alpha_daily * TRADING_DAYS,
        "tracking_error_annualized": te,
        "active_return_annualized_arithmetic": active_ann,
        "information_ratio": active_ann / te if te else None,
        "up_capture": (
            statistics.mean(a for a, _ in up) / statistics.mean(b for _, b in up)
            if up and statistics.mean(b for _, b in up)
            else None
        ),
        "down_capture": (
            statistics.mean(a for a, _ in down) / statistics.mean(b for _, b in down)
            if down and statistics.mean(b for _, b in down)
            else None
        ),
    }


def month_key(date: str) -> str:
    return date[:7]


def monthly_returns(dates: list[str], values: list[float]) -> dict[str, float]:
    endpoints: dict[str, tuple[float, float]] = {}
    for date, value in zip(dates, values):
        key = month_key(date)
        if key not in endpoints:
            endpoints[key] = (value, value)
        else:
            endpoints[key] = (endpoints[key][0], value)
    return {key: end / start - 1.0 for key, (start, end) in endpoints.items() if start}


def analyze(path: Path, risk_free: float) -> dict:
    dates, nav, benchmark = load_series(path)
    if len(nav) < 2:
        raise ValueError("At least two valid NAV observations are required")
    fund_r = returns(nav)
    ann = annualized_return(nav, dates)
    vol = annualized_volatility(fund_r)
    daily_rf = (1.0 + risk_free) ** (1.0 / TRADING_DAYS) - 1.0
    down_vol = downside_volatility(fund_r, daily_rf)
    dd = max_drawdown(nav)

    result = {
        "data": {
            "start_date": dates[0],
            "end_date": dates[-1],
            "observations": len(nav),
            "nav_basis": "由输入文件定义；应使用累计净值或总回报口径",
        },
        "performance": {
            "total_return": nav[-1] / nav[0] - 1.0,
            "annualized_return": ann,
            "annualized_volatility": vol,
            "positive_day_ratio": sum(x > 0 for x in fund_r) / len(fund_r),
        },
        "risk": {
            **dd,
            "downside_volatility": down_vol,
            "sharpe": (ann - risk_free) / vol if ann is not None and vol else None,
            "sortino": (ann - risk_free) / down_vol if ann is not None and down_vol else None,
            "calmar": ann / abs(dd["max_drawdown"]) if ann is not None and dd["max_drawdown"] else None,
            "risk_free_rate_assumption": risk_free,
        },
    }

    if all(value is not None for value in benchmark):
        bench = [float(value) for value in benchmark if value is not None]
        bench_r = returns(bench)
        result["benchmark"] = {
            "total_return": bench[-1] / bench[0] - 1.0,
            "annualized_return": annualized_return(bench, dates),
            "tracking_difference_total": nav[-1] / nav[0] - bench[-1] / bench[0],
            **regression_metrics(fund_r, bench_r),
        }
        fund_monthly = monthly_returns(dates, nav)
        bench_monthly = monthly_returns(dates, bench)
        common = sorted(set(fund_monthly) & set(bench_monthly))
        result["benchmark"]["monthly_excess_hit_ratio"] = (
            sum(fund_monthly[m] > bench_monthly[m] for m in common) / len(common)
            if common
            else None
        )
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("input", type=Path)
    parser.add_argument("--risk-free", type=float, default=0.02)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    result = analyze(args.input, args.risk_free)
    text = json.dumps(result, ensure_ascii=False, indent=2)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text, encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
