#!/usr/bin/env python3
"""Estimate portfolio liquidity, market impact, and redemption stress."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


def _bool_series(series: pd.Series) -> pd.Series:
    return series.fillna(False).astype(str).str.lower().isin({"1", "true", "yes", "y", "是"})


def _weighted_quantile(values: np.ndarray, weights: np.ndarray, quantile: float) -> float | None:
    valid = np.isfinite(values) & np.isfinite(weights) & (weights > 0)
    if not valid.any():
        return None
    sorted_index = np.argsort(values[valid])
    sorted_values = values[valid][sorted_index]
    sorted_weights = weights[valid][sorted_index]
    cumulative = np.cumsum(sorted_weights) / sorted_weights.sum()
    return float(sorted_values[np.searchsorted(cumulative, quantile, side="left")])


def _impact_rate(
    trade_value: pd.Series,
    adv20: pd.Series,
    daily_volatility: pd.Series,
    coefficient: float,
) -> pd.Series:
    participation_multiple = (trade_value / adv20.replace(0, np.nan)).clip(lower=0)
    return coefficient * daily_volatility * np.sqrt(participation_multiple)


def analyze(
    input_path: Path,
    participations: list[float],
    redemptions: list[float],
    impact_coefficient: float,
) -> dict[str, Any]:
    frame = pd.read_csv(input_path, encoding="utf-8-sig")
    required = {"asset_code", "market_value", "adv20", "volatility_daily"}
    missing = required - set(frame.columns)
    if missing:
        raise ValueError(f"缺少字段: {', '.join(sorted(missing))}")
    for column in ["market_value", "adv20", "volatility_daily"]:
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    frame = frame.dropna(subset=["asset_code", "market_value"])
    if frame.empty or frame["market_value"].sum() <= 0:
        raise ValueError("组合市值必须为正")
    for column in ["restricted", "limit_down", "suspended", "cash"]:
        frame[column] = _bool_series(frame[column]) if column in frame else False
    frame["untradeable"] = frame["restricted"] | frame["limit_down"] | frame["suspended"]
    frame.loc[frame["cash"], "untradeable"] = False
    frame["weight"] = frame["market_value"] / frame["market_value"].sum()
    total_value = float(frame["market_value"].sum())
    cash_value = float(frame.loc[frame["cash"], "market_value"].sum())

    liquidity: dict[str, Any] = {}
    for participation in participations:
        if participation <= 0 or participation > 1:
            raise ValueError("参与率必须位于(0,1]区间")
        daily_capacity = frame["adv20"] * participation
        days = frame["market_value"] / daily_capacity.replace(0, np.nan)
        days = days.where(~frame["untradeable"], np.inf)
        finite_days = np.isfinite(days.to_numpy(dtype=float))
        weighted_average = (
            float(
                np.average(
                    days.to_numpy(dtype=float)[finite_days],
                    weights=frame["market_value"].to_numpy(dtype=float)[finite_days],
                )
            )
            if finite_days.any()
            else None
        )
        liquidity[f"{participation:.0%}"] = {
            "weighted_average_days_excluding_untradeable": weighted_average,
            "days_to_liquidate_50pct": _weighted_quantile(
                days.to_numpy(dtype=float), frame["market_value"].to_numpy(dtype=float), 0.50
            ),
            "days_to_liquidate_75pct": _weighted_quantile(
                days.to_numpy(dtype=float), frame["market_value"].to_numpy(dtype=float), 0.75
            ),
            "days_to_liquidate_90pct": _weighted_quantile(
                days.to_numpy(dtype=float), frame["market_value"].to_numpy(dtype=float), 0.90
            ),
            "days_to_liquidate_95pct": _weighted_quantile(
                days.to_numpy(dtype=float), frame["market_value"].to_numpy(dtype=float), 0.95
            ),
            "weight_over_5_days": float(frame.loc[days > 5, "weight"].sum()),
            "weight_over_10_days": float(frame.loc[days > 10, "weight"].sum()),
            "weight_over_20_days": float(frame.loc[days > 20, "weight"].sum()),
        }

    stress: dict[str, Any] = {}
    tradable_non_cash = (~frame["untradeable"]) & (~frame["cash"]) & (frame["adv20"] > 0)
    tradable_value = float(frame.loc[tradable_non_cash, "market_value"].sum())
    base_participation = participations[0]
    for redemption in redemptions:
        required_cash = total_value * redemption
        remaining = max(0.0, required_cash - cash_value)
        can_fund = remaining <= tradable_value
        sales = pd.Series(0.0, index=frame.index)
        if remaining > 0 and tradable_value > 0:
            sales.loc[tradable_non_cash] = (
                frame.loc[tradable_non_cash, "market_value"] / tradable_value * min(remaining, tradable_value)
            )
        daily_capacity = frame["adv20"] * base_participation
        sale_days = sales / daily_capacity.replace(0, np.nan)
        completion_days = float(sale_days.max()) if sales.sum() > 0 else 0.0
        impact_rate = _impact_rate(
            sales,
            frame["adv20"],
            frame["volatility_daily"],
            impact_coefficient,
        ).fillna(0.0)
        impact_cost = float((sales * impact_rate).sum())
        post_weight = (frame["market_value"] - sales).clip(lower=0)
        stress[f"{redemption:.0%}"] = {
            "redemption_value": required_cash,
            "cash_used": min(cash_value, required_cash),
            "securities_to_sell": float(sales.sum()),
            "can_fund_without_untradeable_assets": can_fund,
            "estimated_completion_days_at_base_participation": completion_days,
            "estimated_market_impact_cost": impact_cost,
            "impact_cost_as_pct_of_redemption": impact_cost / required_cash if required_cash > 0 else 0.0,
            "remaining_untradeable_weight": (
                float(post_weight.loc[frame["untradeable"]].sum() / post_weight.sum())
                if post_weight.sum() > 0
                else None
            ),
        }

    most_illiquid = frame.assign(
        days_at_base=frame["market_value"] / (frame["adv20"] * base_participation).replace(0, np.nan)
    )
    most_illiquid.loc[most_illiquid["untradeable"], "days_at_base"] = np.inf
    columns = ["asset_code", "weight", "days_at_base", "restricted", "limit_down", "suspended"]

    return {
        "data": {
            "input": str(input_path),
            "assets": int(len(frame)),
            "portfolio_market_value": total_value,
            "cash_weight": cash_value / total_value,
        },
        "assumptions": {
            "participation_rates": participations,
            "redemption_rates": redemptions,
            "impact_coefficient": impact_coefficient,
            "impact_model": "冲击系数×日波动率×sqrt(交易额/20日平均成交额)",
            "redemption_sale_rule": "现金优先，剩余按可交易非现金资产市值比例出售",
        },
        "liquidity": liquidity,
        "untradeable_weight": float(frame.loc[frame["untradeable"], "weight"].sum()),
        "redemption_stress": stress,
        "most_illiquid_assets": most_illiquid.sort_values("days_at_base", ascending=False)[columns]
        .head(20)
        .replace([np.inf, -np.inf], None)
        .to_dict(orient="records"),
        "warnings": [
            "这是公开持仓与成交量口径的近似压力测试，不是管理人真实交易成本。",
            "季度持仓、平均成交额和受限状态存在时点差，结果应做多情景敏感性分析。",
            "未建模市场共同冲击、成交额内生下降和卖出顺序对价格的反馈。",
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument("--participation", nargs="+", type=float, default=[0.10, 0.20])
    parser.add_argument("--redemption", nargs="+", type=float, default=[0.05, 0.10, 0.20])
    parser.add_argument("--impact-coefficient", type=float, default=0.50)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    result = analyze(args.input, args.participation, args.redemption, args.impact_coefficient)
    text = json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text, encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
