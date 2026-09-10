# -*- coding: utf-8 -*-
"""资金流采集 — 成交额统计 + 北向持股"""

import os
import akshare as ak
from datetime import datetime
from typing import Dict

from collectors.quote import kline, realtime


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


def volume_stats(symbol: str, period: int = 20) -> Dict:
    """成交额统计：当日 + 近 N 日高/低/中位/量比"""
    # 当日成交额估算 = 流通市值(亿) * 换手率(%) * 1e8 / 100
    rt = realtime(symbol)
    circ_mv_yi = rt.get("circ_mv", 0)
    turnover = rt.get("turnover_rate", 0)
    latest_amount_yi = circ_mv_yi * turnover / 100
    
    # 历史 K 线计算成交额统计
    kl = kline(symbol, days=period * 2)
    
    amounts = []
    for bar in kl[-period:]:
        # 成交额 = 收盘价 * 成交量（股） / 1e8 → 亿
        amt = bar["close"] * bar["volume"] / 1e8
        amounts.append(amt)
    
    if not amounts:
        return {
            "latest": {"amount_yi": round(latest_amount_yi, 2)},
            "stats": {},
            "period_days": period,
        }
    
    amounts.sort()
    median = amounts[len(amounts) // 2]
    volume_ratio = latest_amount_yi / median if median > 0 else 1
    
    return {
        "latest": {"amount_yi": round(latest_amount_yi, 2)},
        "stats": {
            "high": round(max(amounts), 2),
            "low": round(min(amounts), 2),
            "median": round(median, 2),
            "volume_ratio": round(volume_ratio, 2),
        },
        "period_days": period,
    }


def northbound(symbol: str, days: int = 30) -> Dict:
    """北向持股数据 — 使用 stock_hsgt_individual_em (全量历史，取最近 N 天)
    
    注意：港交所自 2024-08-16 起停止披露个股级北向持股数据，
    此接口数据可能已过时，仅供历史参考。
    """
    # 代理从环境变量 HTTPS_PROXY 或 config.yaml 读取
    _ensure_proxy()
    try:
        df = ak.stock_hsgt_individual_em(symbol=symbol)
        
        if df is None or df.empty:
            return {"error": "无北向持股数据"}
        
        # 按日期排序，取最近 N 天
        df = df.sort_values("持股日期").tail(days)
        last_date = str(df.iloc[-1]["持股日期"])
        
        # 检查数据新鲜度
        try:
            last_dt = datetime.strptime(last_date[:10], "%Y-%m-%d")
            stale = (datetime.now() - last_dt).days > 7
        except Exception:
            stale = True
        
        ratios = df["持股数量占A股百分比"].dropna().tolist()
        shares = df["持股数量"].dropna().tolist()
        adds = df["今日增持股数"].dropna().tolist()
        
        if not ratios:
            return {"error": "北向持股占比数据为空"}
        
        # 近 5 日增持天数
        recent_adds = adds[-5:] if len(adds) >= 5 else adds
        up_days = sum(1 for a in recent_adds if a > 0)
        
        return {
            "summary": {
                "period": f"{df.iloc[0]['持股日期']} ~ {last_date}",
                "trading_days": len(df),
                "stale": stale,
                "stale_note": "港交所 2024-08 起停止披露个股北向持股，数据仅供参考" if stale else None,
                "ratio": {
                    "current": round(ratios[-1], 4),
                    "high": round(max(ratios), 4),
                    "low": round(min(ratios), 4),
                    "median": round(sorted(ratios)[len(ratios)//2], 4),
                },
                "shares": {"current": int(shares[-1])},
                "recent_adds_5d": int(sum(recent_adds)) if recent_adds else 0,
            },
            "trend": {
                "up_days_5d": up_days,
                "signal": "inflow" if len(ratios) > 1 and ratios[-1] > ratios[-2] else "outflow",
            }
        }
    except Exception as e:
        return {"error": str(e)}


def shareholder_changes(symbol: str) -> Dict:
    """大股东变动数据 (同花顺, via akshare)"""
    # 代理从环境变量 HTTPS_PROXY 或 config.yaml 读取
    _ensure_proxy()
    try:
        df = ak.stock_shareholder_change_ths(symbol=symbol)
        if df is None or df.empty:
            return {"changes": [], "total": 0}
        
        # 取最近 5 条
        recent = df.head(5)
        changes = []
        for _, row in recent.iterrows():
            changes.append({
                "date": str(row.get("公告日期", ""))[:10],
                "shareholder": str(row.get("变动股东", ""))[:20],
                "change": str(row.get("变动数量", "")),
                "method": str(row.get("变动途径", "")),
            })
        
        # 统计增减方向
        increase_count = sum(1 for c in changes if "增持" in c["change"])
        decrease_count = sum(1 for c in changes if "减持" in c["change"])
        
        return {
            "changes": changes,
            "total": len(df),
            "recent_increase": increase_count,
            "recent_decrease": decrease_count,
            "signal": "increase" if increase_count > decrease_count else ("decrease" if decrease_count > increase_count else "neutral"),
        }
    except Exception as e:
        return {"error": str(e)}
