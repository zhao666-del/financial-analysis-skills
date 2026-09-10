#!/usr/bin/env python3
"""Run institutional diagnostics on fund and benchmark total-return series."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


TRADING_DAYS = 252


def _finite(value: float | np.floating[Any]) -> float | None:
    number = float(value)
    return number if math.isfinite(number) else None


def _max_drawdown(values: pd.Series) -> dict[str, Any]:
    running_peak = values.cummax()
    drawdown = values / running_peak - 1.0
    trough_date = drawdown.idxmin()
    peak_date = values.loc[:trough_date].idxmax()
    peak_value = float(values.loc[peak_date])
    later = values.loc[trough_date:]
    recovered = later[later >= peak_value]
    recovery_date = recovered.index[0] if not recovered.empty else None
    return {
        "max_drawdown": _finite(drawdown.min()),
        "peak_date": peak_date.strftime("%Y-%m-%d"),
        "trough_date": trough_date.strftime("%Y-%m-%d"),
        "recovery_date": recovery_date.strftime("%Y-%m-%d") if recovery_date is not None else None,
        "recovery_calendar_days": (
            int((recovery_date - trough_date).days) if recovery_date is not None else None
        ),
        "recovered": recovery_date is not None,
    }


def _newey_west_regression(
    fund_returns: np.ndarray,
    benchmark_returns: np.ndarray,
    annual_rf: float,
    lags: int | None = None,
) -> dict[str, Any]:
    if len(fund_returns) < 60:
        return {"available": False, "reason": "有效日收益少于60个"}
    daily_rf = (1.0 + annual_rf) ** (1.0 / TRADING_DAYS) - 1.0
    y = fund_returns - daily_rf
    x_market = benchmark_returns - daily_rf
    x = np.column_stack([np.ones(len(y)), x_market])
    inv_xx = np.linalg.pinv(x.T @ x)
    coefficients = inv_xx @ x.T @ y
    residuals = y - x @ coefficients
    n = len(y)
    nw_lags = lags if lags is not None else max(1, int(4 * (n / 100) ** (2 / 9)))

    meat = np.zeros((2, 2), dtype=float)
    for t in range(n):
        xt = x[t][:, None]
        meat += residuals[t] ** 2 * (xt @ xt.T)
    for lag in range(1, nw_lags + 1):
        weight = 1.0 - lag / (nw_lags + 1.0)
        gamma = np.zeros((2, 2), dtype=float)
        for t in range(lag, n):
            xt = x[t][:, None]
            xl = x[t - lag][:, None]
            gamma += residuals[t] * residuals[t - lag] * (xt @ xl.T)
        meat += weight * (gamma + gamma.T)

    covariance = inv_xx @ meat @ inv_xx
    standard_errors = np.sqrt(np.maximum(np.diag(covariance), 0.0))
    alpha_daily = float(coefficients[0])
    alpha_se_daily = float(standard_errors[0])
    t_value = alpha_daily / alpha_se_daily if alpha_se_daily > 0 else math.nan
    p_value = math.erfc(abs(t_value) / math.sqrt(2.0)) if math.isfinite(t_value) else math.nan
    alpha_annual = alpha_daily * TRADING_DAYS
    alpha_se_annual = alpha_se_daily * TRADING_DAYS
    fitted = x @ coefficients
    ss_total = float(np.sum((y - y.mean()) ** 2))
    ss_residual = float(np.sum((y - fitted) ** 2))
    r_squared = 1.0 - ss_residual / ss_total if ss_total > 0 else math.nan

    return {
        "available": True,
        "observations": n,
        "newey_west_lags": nw_lags,
        "alpha_annualized_arithmetic": _finite(alpha_annual),
        "alpha_standard_error_annualized": _finite(alpha_se_annual),
        "alpha_t_value": _finite(t_value),
        "alpha_p_value_normal_approx": _finite(p_value),
        "alpha_95pct_confidence_interval": [
            _finite(alpha_annual - 1.96 * alpha_se_annual),
            _finite(alpha_annual + 1.96 * alpha_se_annual),
        ],
        "beta": _finite(coefficients[1]),
        "r_squared": _finite(r_squared),
        "method": "日频单因子回归；Newey-West异方差和自相关稳健标准误",
    }


def _moving_block_bootstrap_alpha(
    fund_returns: np.ndarray,
    benchmark_returns: np.ndarray,
    annual_rf: float,
    iterations: int,
    block_size: int,
    seed: int,
) -> dict[str, Any]:
    n = len(fund_returns)
    if n < 60 or iterations <= 0:
        return {"available": False, "reason": "样本不足或迭代次数为零"}
    rng = np.random.default_rng(seed)
    daily_rf = (1.0 + annual_rf) ** (1.0 / TRADING_DAYS) - 1.0
    alphas: list[float] = []
    max_start = max(1, n - block_size + 1)
    for _ in range(iterations):
        indices: list[int] = []
        while len(indices) < n:
            start = int(rng.integers(0, max_start))
            indices.extend(range(start, min(start + block_size, n)))
        sample = np.asarray(indices[:n])
        y = fund_returns[sample] - daily_rf
        x_market = benchmark_returns[sample] - daily_rf
        x = np.column_stack([np.ones(n), x_market])
        alpha = float((np.linalg.pinv(x.T @ x) @ x.T @ y)[0])
        alphas.append(alpha * TRADING_DAYS)
    lower, median, upper = np.quantile(np.asarray(alphas), [0.025, 0.5, 0.975])
    return {
        "available": True,
        "iterations": iterations,
        "block_size": block_size,
        "seed": seed,
        "alpha_annualized_median": _finite(median),
        "alpha_95pct_confidence_interval": [_finite(lower), _finite(upper)],
        "positive_alpha_probability": _finite(np.mean(np.asarray(alphas) > 0)),
        "method": "移动区块自助法，保留短期序列相关性",
    }


def _longest_negative_streak(values: pd.Series) -> int:
    longest = current = 0
    for value in values:
        if value < 0:
            current += 1
            longest = max(longest, current)
        else:
            current = 0
    return longest


def _rolling_diagnostics(monthly: pd.DataFrame) -> dict[str, Any]:
    output: dict[str, Any] = {}
    if len(monthly) >= 36:
        alpha36 = monthly["fund"].rolling(36).mean() * 12 - monthly["benchmark"].rolling(36).mean() * 12
        valid = alpha36.dropna()
        output["rolling_36m_arithmetic_excess"] = {
            "latest": _finite(valid.iloc[-1]),
            "median": _finite(valid.median()),
            "positive_ratio": _finite((valid > 0).mean()),
            "minimum": _finite(valid.min()),
            "maximum": _finite(valid.max()),
            "observations": int(len(valid)),
        }
    if len(monthly) >= 60:
        active = monthly["fund"] - monthly["benchmark"]
        rolling_mean = active.rolling(60).mean() * 12
        rolling_te = active.rolling(60).std(ddof=1) * math.sqrt(12)
        ir60 = (rolling_mean / rolling_te.replace(0, np.nan)).dropna()
        output["rolling_60m_information_ratio"] = {
            "latest": _finite(ir60.iloc[-1]),
            "median": _finite(ir60.median()),
            "positive_ratio": _finite((ir60 > 0).mean()),
            "minimum": _finite(ir60.min()),
            "maximum": _finite(ir60.max()),
            "observations": int(len(ir60)),
        }
    return output


def _non_overlapping_three_years(monthly: pd.DataFrame) -> list[dict[str, Any]]:
    windows: list[dict[str, Any]] = []
    for start in range(0, len(monthly) - 35, 36):
        block = monthly.iloc[start : start + 36]
        fund_growth = float((1.0 + block["fund"]).prod())
        benchmark_growth = float((1.0 + block["benchmark"]).prod())
        active = block["fund"] - block["benchmark"]
        tracking_error = float(active.std(ddof=1) * math.sqrt(12))
        annual_active = float(active.mean() * 12)
        windows.append(
            {
                "start": block.index[0].strftime("%Y-%m"),
                "end": block.index[-1].strftime("%Y-%m"),
                "fund_total_return": _finite(fund_growth - 1.0),
                "benchmark_total_return": _finite(benchmark_growth - 1.0),
                "geometric_excess": _finite(fund_growth / benchmark_growth - 1.0),
                "information_ratio": _finite(annual_active / tracking_error) if tracking_error > 0 else None,
            }
        )
    return windows


def _period_metrics(frame: pd.DataFrame) -> dict[str, Any]:
    if frame.empty:
        return {"available": False, "observations": 0, "reason": "该条件下没有有效观察值"}
    fund = frame["fund_return"]
    benchmark = frame["benchmark_return"]
    active = fund - benchmark
    tracking_error = float(active.std(ddof=1) * math.sqrt(TRADING_DAYS)) if len(frame) > 1 else math.nan
    return {
        "start": frame.index[0].strftime("%Y-%m-%d"),
        "end": frame.index[-1].strftime("%Y-%m-%d"),
        "observations": int(len(frame)),
        "fund_annualized_arithmetic": _finite(fund.mean() * TRADING_DAYS),
        "benchmark_annualized_arithmetic": _finite(benchmark.mean() * TRADING_DAYS),
        "active_annualized_arithmetic": _finite(active.mean() * TRADING_DAYS),
        "tracking_error": _finite(tracking_error),
        "information_ratio": _finite(active.mean() * TRADING_DAYS / tracking_error)
        if tracking_error > 0
        else None,
    }


def analyze(
    input_path: Path,
    annual_rf: float,
    bootstrap_iterations: int,
    block_size: int | None,
    seed: int,
    nw_lags: int | None,
) -> dict[str, Any]:
    raw = pd.read_csv(input_path, encoding="utf-8-sig")
    required = {"date", "nav", "benchmark"}
    missing = required - set(raw.columns)
    if missing:
        raise ValueError(f"缺少字段: {', '.join(sorted(missing))}")
    raw["date"] = pd.to_datetime(raw["date"], errors="coerce")
    raw["nav"] = pd.to_numeric(raw["nav"], errors="coerce")
    raw["benchmark"] = pd.to_numeric(raw["benchmark"], errors="coerce")
    frame = raw.dropna(subset=["date", "nav", "benchmark"]).sort_values("date").drop_duplicates("date")
    if len(frame) < 61:
        raise ValueError("至少需要61个基金与基准共同有效观察值")
    if (frame[["nav", "benchmark"]] <= 0).any().any():
        raise ValueError("净值与基准序列必须为正数")
    frame = frame.set_index("date")
    frame["fund_return"] = frame["nav"].pct_change()
    frame["benchmark_return"] = frame["benchmark"].pct_change()
    returns = frame.dropna(subset=["fund_return", "benchmark_return"]).copy()

    normalized_fund = frame["nav"] / frame["nav"].iloc[0]
    normalized_benchmark = frame["benchmark"] / frame["benchmark"].iloc[0]
    active_nav = normalized_fund / normalized_benchmark
    monthly_levels = frame[["nav", "benchmark"]].resample("ME").last().dropna()
    monthly = monthly_levels.pct_change().dropna()
    monthly.columns = ["fund", "benchmark"]
    monthly["active"] = monthly["fund"] - monthly["benchmark"]

    fund_r = returns["fund_return"].to_numpy(dtype=float)
    benchmark_r = returns["benchmark_return"].to_numpy(dtype=float)
    block = block_size or max(5, int(round(math.sqrt(len(returns)))))

    rolling_5d = (1.0 + returns["fund_return"]).rolling(5).apply(np.prod, raw=True) - 1.0
    rolling_3m = (1.0 + monthly["fund"]).rolling(3).apply(np.prod, raw=True) - 1.0
    var_5 = float(returns["fund_return"].quantile(0.05))
    expected_shortfall = float(returns.loc[returns["fund_return"] <= var_5, "fund_return"].mean())

    result: dict[str, Any] = {
        "data": {
            "input": str(input_path),
            "start_date": frame.index[0].strftime("%Y-%m-%d"),
            "end_date": frame.index[-1].strftime("%Y-%m-%d"),
            "level_observations": int(len(frame)),
            "return_observations": int(len(returns)),
            "basis": "输入应为基金累计净值/总回报与同频基准总回报",
        },
        "active_performance": {
            "active_nav_end": _finite(active_nav.iloc[-1]),
            "geometric_excess_total": _finite(active_nav.iloc[-1] - 1.0),
            "active_drawdown": _max_drawdown(active_nav),
            "positive_excess_month_ratio": _finite((monthly["active"] > 0).mean()),
            "longest_negative_excess_month_streak": _longest_negative_streak(monthly["active"]),
        },
        "tail_risk": {
            "daily_skewness": _finite(returns["fund_return"].skew()),
            "daily_excess_kurtosis": _finite(returns["fund_return"].kurt()),
            "historical_var_95_daily": _finite(var_5),
            "historical_expected_shortfall_95_daily": _finite(expected_shortfall),
            "worst_1d": _finite(returns["fund_return"].min()),
            "worst_5d": _finite(rolling_5d.min()),
            "worst_1m": _finite(monthly["fund"].min()),
            "worst_3m": _finite(rolling_3m.min()),
        },
        "alpha_significance": _newey_west_regression(fund_r, benchmark_r, annual_rf, nw_lags),
        "bootstrap_alpha": _moving_block_bootstrap_alpha(
            fund_r, benchmark_r, annual_rf, bootstrap_iterations, block, seed
        ),
        "rolling": _rolling_diagnostics(monthly),
        "non_overlapping_3y": _non_overlapping_three_years(monthly),
        "conditional_periods": {
            "benchmark_up_days": _period_metrics(returns[returns["benchmark_return"] > 0]),
            "benchmark_down_days": _period_metrics(returns[returns["benchmark_return"] < 0]),
            "benchmark_worst_decile_days": _period_metrics(
                returns[returns["benchmark_return"] <= returns["benchmark_return"].quantile(0.10)]
            ),
        },
        "warnings": [
            "回归为单因子诊断，不替代包含风格、行业和特殊收益的完整归因。",
            "自助法置信区间依赖区块长度与样本稳定性，应做参数敏感性分析。",
        ],
    }

    if "regime" in frame.columns:
        regimes: dict[str, Any] = {}
        regime_frame = frame.dropna(subset=["fund_return", "benchmark_return", "regime"])
        for label, group in regime_frame.groupby("regime", sort=False):
            regimes[str(label)] = (
                _period_metrics(group)
                if len(group) >= 30
                else {"available": False, "observations": int(len(group)), "reason": "少于30个观察值"}
            )
        result["manager_or_model_regimes"] = regimes
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path, help="CSV字段: date,nav,benchmark，可选regime")
    parser.add_argument("--risk-free", type=float, default=0.02, help="年化无风险利率")
    parser.add_argument("--bootstrap", type=int, default=1000, help="区块自助法迭代次数")
    parser.add_argument("--block-size", type=int, help="移动区块长度")
    parser.add_argument("--seed", type=int, default=20260724)
    parser.add_argument("--nw-lags", type=int, help="Newey-West滞后阶数")
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    result = analyze(
        args.input,
        args.risk_free,
        args.bootstrap,
        args.block_size,
        args.seed,
        args.nw_lags,
    )
    text = json.dumps(result, ensure_ascii=False, indent=2)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text, encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
