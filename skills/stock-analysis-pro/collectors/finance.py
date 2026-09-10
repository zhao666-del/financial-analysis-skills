# -*- coding: utf-8 -*-
"""财务指标采集 — akshare THS 财务摘要 + 分红历史"""

import os
import akshare as ak
from typing import Dict, List


def _ensure_proxy():
    """确保代理已设置"""
    if "HTTPS_PROXY" not in os.environ and "https_proxy" not in os.environ:
        try:
            from config import get_proxy
            proxy = get_proxy()
            if proxy:
                os.environ["HTTPS_PROXY"] = proxy
        except Exception:
            pass


def _get_latest_metric(df, keyword: str) -> Dict:
    """从 THS 财务数据中提取最新指标"""
    if df is None or df.empty:
        return {"value": 0.0}
    match = df[df["metric_name"].str.contains(keyword, na=False)]
    if match.empty:
        return {"value": 0.0}
    match = match.sort_values("report_date", ascending=False)
    latest = match.iloc[0]
    try:
        val = float(latest.get("value", 0))
    except (ValueError, TypeError):
        val = 0.0
    return {"value": val}


def indicators(symbol: str) -> Dict:
    """获取基本面指标：ROE/毛利率/负债率/营收增速/净利增速/EPS/每股净资产/经营现金流/一致预期"""
    _ensure_proxy()
    result = {}
    
    try:
        df = ak.stock_financial_abstract_new_ths(symbol=symbol)
        
        result["roe"] = _get_latest_metric(df, "index_weighted_avg_roe")["value"]
        result["gross_margin"] = _get_latest_metric(df, "sale_gross_margin")["value"]
        result["net_margin"] = _get_latest_metric(df, "sale_net_interest_ratio")["value"]
        result["debt_ratio"] = _get_latest_metric(df, "assets_debt_ratio")["value"]
        result["current_ratio"] = _get_latest_metric(df, "current_ratio")["value"]
        result["revenue_growth"] = _get_latest_metric(df, "calculate_operating_income_total_yoy_growth_ratio")["value"]
        result["net_profit_growth"] = _get_latest_metric(df, "calculate_parent_holder_net_profit_yoy_growth_ratio")["value"]
        result["eps"] = _get_latest_metric(df, "basic_eps")["value"]
        result["nav_per_share"] = _get_latest_metric(df, "calc_per_net_assets")["value"]
        result["ocf_per_share"] = _get_latest_metric(df, "index_per_operating_cash_flow_net")["value"]
    except Exception:
        result = {
            "roe": 0.0, "gross_margin": 0.0, "net_margin": 0.0,
            "debt_ratio": 0.0, "current_ratio": 0.0,
            "revenue_growth": 0.0, "net_profit_growth": 0.0,
            "eps": 0.0, "nav_per_share": 0.0, "ocf_per_share": 0.0,
        }
    
    return result


def profit_forecast(symbol: str) -> list:
    """获取一致预期（机构盈利预测）"""
    _ensure_proxy()
    try:
        df = ak.stock_profit_forecast_ths(symbol=symbol)
        if df is None or df.empty:
            return []
        forecasts = []
        for _, row in df.head(3).iterrows():
            forecasts.append({
                "year": str(row.get("年度", "")),
                "count": int(row.get("预测机构数", 0)),
                "mean_eps": round(float(row.get("均值", 0)), 2),
                "min": round(float(row.get("最小值", 0)), 2),
                "max": round(float(row.get("最大值", 0)), 2),
            })
        return forecasts
    except Exception:
        return []


def dividend_history(symbol: str, limit: int = 5) -> List[Dict]:
    """获取分红历史"""
    _ensure_proxy()
    try:
        df = ak.stock_history_dividend_detail(symbol=symbol)
        if df is None or df.empty:
            return []
        
        divs = []
        for _, row in df.head(limit).iterrows():
            divs.append({
                "date": str(row.get("公告日期", "")),
                "dividend": float(row.get("派息", 0)),  # 每10股
                "ex_date": str(row.get("除权除息日", ""))[:10],
                "status": str(row.get("进度", "")),
            })
        return divs
    except Exception:
        return []
