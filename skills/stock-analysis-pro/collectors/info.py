# -*- coding: utf-8 -*-
"""公司信息采集 — 东财 F10 + 同花顺"""

import requests
from typing import Dict


def company_info(symbol: str) -> Dict:
    """东财 F10 公司基本信息 + 同花顺主营业务"""
    code = f"{symbol}.SH" if symbol.startswith("6") else f"{symbol}.SZ"
    url = f"https://emweb.securities.eastmoney.com/PC_HSF10/CompanySurvey/CompanySurveyAjax?code={code}"
    headers = {
        "User-Agent": "Mozilla/5.0",
        "Referer": "https://emweb.securities.eastmoney.com/",
    }
    resp = requests.get(url, headers=headers, timeout=10)
    resp.raise_for_status()
    data = resp.json()
    
    base = data.get("jbzl", {})
    if isinstance(base, list):
        base = base[0] if base else {}
    
    fxxg = data.get("fxxg", {})
    
    result = {
        "full_name": base.get("gsmc", ""),
        "short_name": base.get("agjc", ""),
        "industry": base.get("sshy", ""),
        "csrc_industry": base.get("sszjhhy", ""),
        "controller": base.get("zjl", ""),
        "legal_rep": base.get("frdb", ""),
        "registered_capital": base.get("zczb", ""),
        "listing_date": fxxg.get("ssrq", ""),
        "employees": base.get("gyrs", ""),
        "main_business": base.get("ywmc", ""),
        "product_type": "",
        "downstream": "",
        "summary": base.get("gsjj", ""),
    }
    
    # 同花顺主营业务
    try:
        import akshare as ak
        zyjs = ak.stock_zyjs_ths(symbol=symbol)
        if zyjs is not None and len(zyjs) > 0:
            row = zyjs.iloc[0]
            result["main_business"] = str(row.get("主营业务", ""))
            result["product_type"] = str(row.get("产品类型", ""))
            result["product_names"] = str(row.get("产品名称", ""))
    except Exception:
        result["main_business"] = ""
        result["product_type"] = ""
        result["product_names"] = ""
    
    return result
