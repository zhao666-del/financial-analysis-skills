# -*- coding: utf-8 -*-
"""分析维度层 — 资金面"""

from collectors.flow import volume_stats, northbound, shareholder_changes


def analyze(symbol: str) -> dict:
    """资金面分析：成交额统计 + 北向持股 + 股东变动"""
    vol = volume_stats(symbol, period=20)
    nb = northbound(symbol)
    sh = shareholder_changes(symbol)
    
    return {
        "volume_stats": vol,
        "northbound": nb,
        "shareholder_changes": sh,
    }
