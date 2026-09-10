# -*- coding: utf-8 -*-
"""分析维度层 — 基本面"""

from collectors.finance import indicators, dividend_history, profit_forecast


def analyze(symbol: str) -> dict:
    """基本面分析：盈利能力/财务健康/成长能力/分红历史/一致预期"""
    data = indicators(symbol)
    divs = dividend_history(symbol, limit=3)
    forecast = profit_forecast(symbol)
    
    signals = []
    warnings = []
    
    roe = data.get("roe", 0)
    gm = data.get("gross_margin", 0)
    debt = data.get("debt_ratio", 0)
    rev_g = data.get("revenue_growth", 0)
    np_g = data.get("net_profit_growth", 0)
    
    if roe > 15:
        signals.append(f"高ROE({roe:.1f}%)")
    elif roe < 5:
        warnings.append(f"低ROE({roe:.1f}%)")
    
    if gm > 50:
        signals.append(f"高毛利({gm:.1f}%)")
    
    if debt < 30:
        signals.append(f"低负债({debt:.1f}%)")
    elif debt > 70:
        warnings.append(f"高负债({debt:.1f}%)")
    
    if rev_g > 30:
        signals.append(f"营收高增({rev_g:.1f}%)")
    elif rev_g < 0:
        warnings.append(f"营收下滑({rev_g:.1f}%)")
    
    if np_g > 30:
        signals.append(f"净利高增({np_g:.1f}%)")
    elif np_g < 0:
        warnings.append(f"净利下滑({np_g:.1f}%)")
    
    # 分红信号
    if divs:
        latest_div = divs[0].get("dividend", 0)
        if latest_div > 0:
            signals.append(f"近{len(divs)}年有分红(最近每10股派{latest_div}元)")
        else:
            warnings.append("无分红记录")
    
    return {
        "profitability": {
            "roe": {"value": round(roe, 2)},
            "gross_margin": {"value": round(gm, 4)},
            "net_margin": {"value": round(data.get("net_margin", 0), 4)},
        },
        "health": {
            "debt_ratio": {"value": round(debt, 4)},
            "current_ratio": {"value": round(data.get("current_ratio", 0), 2)},
        },
        "growth": {
            "revenue_growth": {"value": round(rev_g, 6)},
            "net_profit_growth": {"value": round(np_g, 6)},
        },
        "eps": round(data.get("eps", 0), 2),
        "nav_per_share": round(data.get("nav_per_share", 0), 2),
        "ocf_per_share": round(data.get("ocf_per_share", 0), 2),
        "dividend": {"history": divs},
        "forecast": forecast,
        "signals": signals,
        "warnings": warnings,
    }
