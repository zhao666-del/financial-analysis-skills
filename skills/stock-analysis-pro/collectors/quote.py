# -*- coding: utf-8 -*-
"""实时行情 & 历史 K 线采集 — 腾讯 + 新浪"""

import re
import json
import subprocess
import requests
from datetime import datetime
from typing import List, Dict


def _decode_json_bytes(raw: bytes) -> dict:
    """Decode Chinese-market JSON responses across UTF-8/GB18030 paths."""
    last_error = None
    for encoding in ("utf-8-sig", "gb18030"):
        try:
            return json.loads(raw.decode(encoding))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            last_error = exc
    raise ValueError("Unable to decode market-data JSON") from last_error


def _prefix_symbol(symbol: str) -> str:
    """60xxxx -> sh60xxxx, 00/30xxxx -> sz00xxxx"""
    symbol = symbol.strip()
    if not re.fullmatch(r"\d{6}", symbol):
        raise ValueError(f"Invalid A-share symbol: {symbol}")
    if symbol.startswith(("6", "9")):
        return f"sh{symbol}"
    return f"sz{symbol}"


def _normalize_symbol(symbol: str) -> str:
    """统一股票代码为 sh/sz 前缀格式"""
    symbol = symbol.strip()
    if symbol[:2] in ('sh', 'sz'):
        return symbol
    return _prefix_symbol(symbol)


def realtime(symbol: str) -> Dict:
    """实时行情，腾讯不可用时自动回退到东方财富。"""
    sym = _prefix_symbol(symbol)
    url = f"https://qt.gtimg.cn/q={sym}"
    try:
        resp = requests.get(url, timeout=5)
        resp.raise_for_status()
        resp.encoding = "gbk"
        text = resp.text.strip()

        if "unknown" in text:
            raise ValueError(f"Symbol {symbol} not found")

        d = text.split("~")
        if len(d) < 53:
            raise ValueError("Unexpected Tencent response format")

        return {
            "name": d[1],
            "code": d[2],
            "price": float(d[3]),
            "prev_close": float(d[4]),
            "open": float(d[5]),
            "volume": int(d[6]),
            "high": float(d[33]),
            "low": float(d[34]),
            "change_pct": float(d[32]),
            "amplitude": float(d[43]),
            "turnover_rate": float(d[38]),
            "pe": float(d[39]),
            "pb": float(d[46]) if d[46] else 0,
            "total_mv": float(d[45]),
            "circ_mv": float(d[44]),
            "limit_up": float(d[47]),
            "limit_down": float(d[48]),
            "date": d[30],
            "source": "腾讯",
        }
    except (requests.RequestException, ValueError, IndexError):
        try:
            return _realtime_eastmoney(symbol)
        except (requests.RequestException, ValueError, subprocess.SubprocessError):
            return _realtime_sina(symbol)


def _realtime_eastmoney(symbol: str) -> Dict:
    """东方财富免 Cookie 行情接口，作为腾讯行情的容错源。"""
    market = "1" if symbol.startswith(("6", "9")) else "0"
    fields = (
        "f43,f44,f45,f46,f47,f48,f51,f52,f57,f58,f60,"
        "f116,f117,f124,f162,f167,f168,f170,f171"
    )
    url = (
        "https://push2.eastmoney.com/api/qt/stock/get"
        f"?secid={market}.{symbol}&fields={fields}"
    )
    headers = {
        "User-Agent": "Mozilla/5.0",
        "Referer": "https://quote.eastmoney.com/",
    }
    try:
        resp = requests.get(url, headers=headers, timeout=10)
        resp.raise_for_status()
        payload = _decode_json_bytes(resp.content)
    except (requests.RequestException, ValueError):
        # Some Windows networks terminate Python TLS connections to this
        # endpoint while the system curl client remains available. The
        # command is fixed, shell=False, and the stock code is validated.
        completed = subprocess.run(
            [
                "curl.exe",
                "-fsSL",
                "--max-time",
                "10",
                "--retry",
                "3",
                "--retry-all-errors",
                "--retry-delay",
                "1",
                "-H",
                "User-Agent: Mozilla/5.0",
                "-H",
                "Referer: https://quote.eastmoney.com/",
                url,
            ],
            check=True,
            capture_output=True,
        )
        payload = _decode_json_bytes(completed.stdout)

    data = payload.get("data")
    if not data:
        raise ValueError(f"Symbol {symbol} not found")

    def scaled(field: str, divisor: float = 100) -> float:
        value = data.get(field)
        if value in (None, "-"):
            return 0
        return round(float(value) / divisor, 4)

    timestamp = data.get("f124")
    quote_time = (
        datetime.fromtimestamp(timestamp).strftime("%Y%m%d%H%M%S")
        if isinstance(timestamp, (int, float)) and timestamp > 0
        else ""
    )
    return {
        "name": data.get("f58", ""),
        "code": data.get("f57", symbol),
        "price": scaled("f43"),
        "prev_close": scaled("f60"),
        "open": scaled("f46"),
        "volume": int(data.get("f47") or 0),
        "amount": float(data.get("f48") or 0),
        "high": scaled("f44"),
        "low": scaled("f45"),
        "change_pct": scaled("f170"),
        "amplitude": scaled("f171"),
        "turnover_rate": scaled("f168"),
        "pe": scaled("f162"),
        "pb": scaled("f167"),
        "total_mv": round(float(data.get("f116") or 0) / 1e8, 2),
        "circ_mv": round(float(data.get("f117") or 0) / 1e8, 2),
        "limit_up": scaled("f51"),
        "limit_down": scaled("f52"),
        "date": quote_time,
        "source": "东方财富",
    }


def _realtime_sina(symbol: str) -> Dict:
    """新浪实时行情兜底；不提供 PE/PB 和市值。"""
    sym = _prefix_symbol(symbol)
    url = f"https://hq.sinajs.cn/list={sym}"
    headers = {
        "User-Agent": "Mozilla/5.0",
        "Referer": "https://finance.sina.com.cn/",
    }
    resp = requests.get(url, headers=headers, timeout=10)
    resp.raise_for_status()
    resp.encoding = "gb18030"
    text = resp.text.strip()
    if '="' not in text:
        raise ValueError("Unexpected Sina response format")
    d = text.split('="', 1)[1].rsplit('"', 1)[0].split(",")
    if len(d) < 32 or not d[0]:
        raise ValueError(f"Symbol {symbol} not found")

    open_price = float(d[1] or 0)
    prev_close = float(d[2] or 0)
    price = float(d[3] or 0)
    high = float(d[4] or 0)
    low = float(d[5] or 0)
    change_pct = round((price - prev_close) / prev_close * 100, 2) if prev_close else 0
    amplitude = round((high - low) / prev_close * 100, 2) if prev_close else 0
    return {
        "name": d[0],
        "code": symbol,
        "price": price,
        "prev_close": prev_close,
        "open": open_price,
        "volume": int(float(d[8] or 0)),
        "amount": float(d[9] or 0),
        "high": high,
        "low": low,
        "change_pct": change_pct,
        "amplitude": amplitude,
        "turnover_rate": 0,
        "pe": 0,
        "pb": 0,
        "total_mv": 0,
        "circ_mv": 0,
        "limit_up": 0,
        "limit_down": 0,
        "date": f"{d[30].replace('-', '')}{d[31].replace(':', '')}",
        "source": "新浪",
    }


def kline(symbol: str, days: int = 250) -> List[Dict]:
    """新浪历史 K 线，返回 [{date, open, high, low, close, volume}]"""
    sym = _prefix_symbol(symbol)
    url = (
        "http://money.finance.sina.com.cn/quotes_service/api/json_v2.php/"
        f"CN_MarketData.getKLineData?symbol={sym}&scale=240&ma=no&datalen={days}"
    )
    headers = {
        "User-Agent": "Mozilla/5.0",
        "Referer": "https://finance.sina.com.cn",
    }
    resp = requests.get(url, headers=headers, timeout=15)
    resp.raise_for_status()
    
    raw = re.sub(r'(\w+):', r'"\1":', resp.text.strip())
    data = __import__("json").loads(raw)
    
    return [
        {
            "date": item.get("day", ""),
            "open": float(item.get("open", 0)),
            "high": float(item.get("high", 0)),
            "low": float(item.get("low", 0)),
            "close": float(item.get("close", 0)),
            "volume": float(item.get("volume", 0)),
        }
        for item in data
    ]


def market_indices() -> Dict:
    """大盘指数 (新浪) — 上证/深证/创业板"""
    url = "https://hq.sinajs.cn/list=sh000001,sz399001,sz399006"
    try:
        r = requests.get(url, headers={"Referer": "https://finance.sina.com.cn"}, timeout=10)
        result = {}
        index_map = {
            "sh000001": "上证指数",
            "sz399001": "深证成指",
            "sz399006": "创业板指",
        }
        for line in r.text.strip().split("\n"):
            for code, name in index_map.items():
                if code in line and '"' in line:
                    parts = line.split('"')[1].split(",")
                    if len(parts) > 8:
                        result[name] = {
                            "name": parts[0],
                            "price": float(parts[3]),
                            "change": float(parts[3]) - float(parts[2]),
                            "change_pct": round((float(parts[3]) - float(parts[2])) / float(parts[2]) * 100, 2) if float(parts[2]) > 0 else 0,
                            "volume_yi": round(float(parts[9]) / 1e8, 1) if len(parts) > 9 else 0,
                        }
        return result
    except Exception:
        return {}


def batch_quotes_tencent(symbols: list) -> dict:
    """
    腾讯批量行情 — 一次请求多只股票
    
    Args:
        symbols: ['sh600519', 'sz000001', ...] 或 ['600519', '000001', ...]
    
    Returns:
        {symbol: {name, price, pct, amount, turnover, high, low, ...}, ...}
        symbol 保持输入格式
    """
    if not symbols:
        return {}
    
    # 标准化
    norm_map = {}  # normalized -> original
    for s in symbols:
        n = _normalize_symbol(s)
        norm_map[n] = s
    
    query = ','.join(norm_map.keys())
    url = f"https://qt.gtimg.cn/q={query}"
    resp = requests.get(url, timeout=10)
    resp.encoding = "gbk"
    
    result = {}
    for line in resp.text.strip().split(";"):
        line = line.strip()
        if not line or "unknown" in line:
            continue
        
        # v_sh600519="1~贵州茅台~600519~..."
        if "=" not in line:
            continue
        
        var_part, data_part = line.split("=", 1)
        # 提取代码: v_sh600519 -> sh600519
        sym_key = var_part.replace("v_", "").strip()
        
        data = data_part.strip('"')
        parts = data.split("~")
        if len(parts) < 50:
            continue
        
        try:
            price = float(parts[3]) if parts[3] else 0
            prev_close = float(parts[4]) if parts[4] else 0
            pct = float(parts[32]) if parts[32] else 0
            amount = float(parts[37]) if parts[37] else 0  # 成交额(万)
            
            info = {
                'name': parts[1],
                'code': parts[2],
                'price': price,
                'prev_close': prev_close,
                'open': float(parts[5]) if parts[5] else 0,
                'high': float(parts[33]) if parts[33] else 0,
                'low': float(parts[34]) if parts[34] else 0,
                'pct': pct,
                'amount': amount * 10000,  # 万 → 元
                'turnover': float(parts[38]) if parts[38] else 0,
                'volume': int(float(parts[6])) if parts[6] else 0,
            }
            
            # 用原始symbol作key
            orig = norm_map.get(sym_key, sym_key)
            result[orig] = info
        except (ValueError, IndexError):
            continue
    
    return result
