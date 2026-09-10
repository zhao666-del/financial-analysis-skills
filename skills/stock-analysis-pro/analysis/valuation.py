# -*- coding: utf-8 -*-
"""分析维度层 — 估值面"""

from collectors.quote import realtime


def analyze(symbol: str) -> dict:
    """估值分析：PE/PB/市值/换手率"""
    rt = realtime(symbol)
    
    pe = rt.get("pe", 0)
    pb = rt.get("pb", 0)
    total_mv = rt.get("total_mv", 0)
    circ_mv = rt.get("circ_mv", 0)
    turnover = rt.get("turnover_rate", 0)
    
    signals = []
    warnings = []
    
    # 简单估值判断
    if 0 < pe < 15:
        signals.append(f"低PE({pe:.1f})")
    elif pe < 0:
        warnings.append("公司处于亏损状态，PE不适用")
    elif pe > 100:
        warnings.append(f"高PE({pe:.1f})")
    elif pe == 0:
        warnings.append("PE数据缺失")
    
    if 0 < pb < 2:
        signals.append(f"低PB({pb:.1f})")
    elif pb > 10:
        warnings.append(f"高PB({pb:.1f})")
    elif pb == 0:
        warnings.append("PB数据缺失")
    
    if turnover > 5:
        warnings.append(f"高换手({turnover:.1f}%)")
    elif 0 < turnover < 0.5:
        signals.append(f"低换手({turnover:.1f}%)")
    
    return {
        "pe": pe,
        "pb": pb,
        "total_mv": total_mv,
        "circ_mv": circ_mv,
        "turnover_rate": turnover,
        "signals": signals,
        "warnings": warnings,
    }
