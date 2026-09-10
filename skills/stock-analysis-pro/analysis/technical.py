# -*- coding: utf-8 -*-
"""分析维度层 — 技术面

基于旧版 micro_old/analyzers/technicals.py 迁移 + 扩展
包含：MA(5/10/20/60/120/250) / MACD / KDJ / RSI / BOLL / 量比 / 价格分位 / 支撑压力
"""

from collectors.quote import kline, realtime


def analyze(symbol: str) -> dict:
    """技术面分析"""
    rt = realtime(symbol)
    price = rt["price"]
    kl = kline(symbol, days=250)
    
    if len(kl) < 30:
        return {"error": "K线数据不足"}
    
    closes = [b["close"] for b in kl]
    volumes = [b["volume"] for b in kl]
    highs = [b["high"] for b in kl]
    lows = [b["low"] for b in kl]
    
    result = {
        "price": price,
        "signals": [],
        "warnings": [],
    }
    
    # ── 1. 移动平均线 (MA5/10/20/60/120/250) ──
    for period in [5, 10, 20, 60, 120, 250]:
        if len(closes) >= period:
            ma = sum(closes[-period:]) / period
            result[f"ma{period}"] = round(ma, 2)
            result[f"ma{period}_signal"] = "above" if price > ma else "below"
            
            if price > ma:
                result["signals"].append(f"站上MA{period}")
            else:
                result["warnings"].append(f"跌破MA{period}")
    
    # ── 2. MACD (12, 26, 9) ──
    if len(closes) >= 35:
        ema12 = _ema(closes, 12)
        ema26 = _ema(closes, 26)
        dif_start = len(ema12) - len(ema26)
        dif = [ema12[i + dif_start] - ema26[i] for i in range(len(ema26))]
        dea_list = _ema(dif, 9)
        
        if len(dea_list) >= 1:
            dif_val = dif[-1]
            dea_val = dea_list[-1]
            histogram = 2 * (dif_val - dea_val)
            
            golden_cross = False
            dead_cross = False
            if len(dea_list) >= 2 and len(dif) >= 2:
                golden_cross = dif_val > dea_val and dif[-2] <= dea_list[-2]
                dead_cross = dif_val < dea_val and dif[-2] >= dea_list[-2]
            
            result["macd"] = {
                "dif": round(dif_val, 3),
                "dea": round(dea_val, 3),
                "histogram": round(histogram, 3),
                "signal": "bullish" if histogram > 0 else "bearish",
                "golden_cross": golden_cross,
                "dead_cross": dead_cross,
            }
            
            if histogram > 0:
                result["signals"].append("MACD多头")
            else:
                result["warnings"].append("MACD空头")
            
            if golden_cross:
                result["signals"].append("MACD金叉")
            if dead_cross:
                result["warnings"].append("MACD死叉")
    
    # ── 3. KDJ (9, 3, 3) ──
    if len(closes) >= 9:
        k, d, j = _kdj(highs, lows, closes, 9, 3, 3)
        result["kdj"] = {
            "k": round(k, 2),
            "d": round(d, 2),
            "j": round(j, 2),
        }
        
        if k > 80 or d > 80:
            result["warnings"].append(f"KDJ超买(K={k:.0f},D={d:.0f})")
        elif k < 20 or d < 20:
            result["signals"].append(f"KDJ超卖(K={k:.0f},D={d:.0f})")
        
        # 金叉死叉
        if len(closes) >= 12:
            prev_k, prev_d, _ = _kdj(highs[:-1], lows[:-1], closes[:-1], 9, 3, 3)
            if k > d and prev_k <= prev_d:
                result["signals"].append("KDJ金叉")
            elif k < d and prev_k >= prev_d:
                result["warnings"].append("KDJ死叉")
    
    # ── 4. RSI (6/12/24) ──
    for period in [6, 12, 24]:
        if len(closes) > period:
            rsi = _rsi(closes, period)
            result[f"rsi{period}"] = round(rsi, 2)
            
            if rsi > 70:
                result["warnings"].append(f"RSI{period}超买({rsi:.0f})")
            elif rsi < 30:
                result["signals"].append(f"RSI{period}超卖({rsi:.0f})")
    
    # ── 5. BOLL (20, 2) ──
    if len(closes) >= 20:
        upper, middle, lower = _boll(closes, 20, 2)
        result["boll"] = {
            "upper": round(upper, 2),
            "middle": round(middle, 2),
            "lower": round(lower, 2),
        }
        
        if price > upper:
            result["warnings"].append("突破BOLL上轨")
        elif price < lower:
            result["signals"].append("跌破BOLL下轨")
    
    # ── 6. 量比 (5日均量/20日均量) ──
    if len(volumes) >= 20:
        vol_5d = sum(volumes[-5:]) / 5
        vol_20d = sum(volumes[-20:]) / 20
        vol_ratio = vol_5d / vol_20d if vol_20d > 0 else 1
        result["volume_ratio"] = round(vol_ratio, 2)
        
        if vol_ratio > 1.5:
            result["signals"].append(f"放量(量比{vol_ratio:.2f})")
        elif vol_ratio < 0.5:
            result["warnings"].append(f"极度缩量(量比{vol_ratio:.2f})")
    
    # ── 7. 换手率分级 ──
    tr = rt.get("turnover_rate")
    if tr is not None:
        result["turnover_rate"] = tr
        if tr > 10:
            result["turnover_level"] = "extreme_high"
            result["warnings"].append(f"换手过高({tr}%)")
        elif tr > 5:
            result["turnover_level"] = "high"
        elif tr > 2:
            result["turnover_level"] = "normal"
        else:
            result["turnover_level"] = "low"
    
    # ── 8. 价格分位 (60d/250d) ──
    for window in [60, 250]:
        if len(closes) >= window:
            window_data = closes[-window:]
            low = min(window_data)
            high = max(window_data)
            pct = ((price - low) / (high - low) * 100) if high > low else 50.0
            label = "60d" if window == 60 else "250d"
            result[f"percentile_{label}"] = {
                "value": round(pct, 1),
                "low": round(low, 2),
                "high": round(high, 2),
            }
            
            if pct < 20:
                result["signals"].append(f"{label}超卖区")
            elif pct > 80:
                result["warnings"].append(f"{label}超买区")
    
    # ── 9. 近期高低点 / 支撑压力 ──
    if len(highs) >= 20:
        recent_high = max(highs[-20:])
        recent_low = min(lows[-20:])
        result["recent_20d"] = {
            "high": round(recent_high, 2),
            "low": round(recent_low, 2),
        }
        
        # 压力位 = 近期高点，支撑位 = 近期低点
        result["resistance"] = round(recent_high, 2)
        result["support"] = round(recent_low, 2)
        
        if price >= recent_high * 0.98:
            result["warnings"].append(f"接近压力位({recent_high:.2f})")
        elif price <= recent_low * 1.02:
            result["signals"].append(f"接近支撑位({recent_low:.2f})")
    
    return result


def _ema(data, period):
    """指数移动平均"""
    if len(data) < period:
        return []
    multiplier = 2 / (period + 1)
    ema = [sum(data[:period]) / period]
    for price in data[period:]:
        ema.append((price - ema[-1]) * multiplier + ema[-1])
    return ema


def _kdj(highs, lows, closes, n=9, m1=3, m2=3):
    """KDJ 指标计算"""
    if len(closes) < n:
        return 50, 50, 50
    
    rsv_list = []
    for i in range(n - 1, len(closes)):
        high_n = max(highs[i - n + 1:i + 1])
        low_n = min(lows[i - n + 1:i + 1])
        if high_n == low_n:
            rsv = 50
        else:
            rsv = (closes[i] - low_n) / (high_n - low_n) * 100
        rsv_list.append(rsv)
    
    # 初始 K/D = 50
    k = 50
    d = 50
    for rsv in rsv_list:
        k = (m1 - 1) / m1 * k + 1 / m1 * rsv
        d = (m2 - 1) / m2 * d + 1 / m2 * k
    
    j = 3 * k - 2 * d
    return k, d, j


def _rsi(closes, period=14):
    """RSI 相对强弱指标"""
    if len(closes) < period + 1:
        return 50
    
    gains = []
    losses = []
    for i in range(1, len(closes)):
        diff = closes[i] - closes[i - 1]
        gains.append(max(diff, 0))
        losses.append(max(-diff, 0))
    
    avg_gain = sum(gains[-period:]) / period
    avg_loss = sum(losses[-period:]) / period
    
    if avg_loss == 0:
        return 100
    
    rs = avg_gain / avg_loss
    return 100 - 100 / (1 + rs)


def _boll(closes, period=20, num_std=2):
    """布林带"""
    if len(closes) < period:
        return 0, 0, 0
    
    recent = closes[-period:]
    middle = sum(recent) / period
    variance = sum((x - middle) ** 2 for x in recent) / period
    std = variance ** 0.5
    
    upper = middle + num_std * std
    lower = middle - num_std * std
    return upper, middle, lower
