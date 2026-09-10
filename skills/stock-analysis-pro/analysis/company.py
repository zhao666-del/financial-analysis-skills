# -*- coding: utf-8 -*-
"""分析维度层 — 公司概况"""

from collectors.info import company_info


def _parse_f10_raw(data: dict) -> dict:
    """解析 Playwright 拦截到的 F10 原始 JSON (兼容新旧字段名)"""
    base = data.get("jbzl", {})
    if isinstance(base, list):
        base = base[0] if base else {}
    fxxg = data.get("fxxg", {})
    if isinstance(fxxg, list):
        fxxg = fxxg[0] if fxxg else {}

    # 兼容新旧字段名 (新版 PageAjax 用大写，旧版 CompanySurveyAjax 用小写)
    def _get(d, *keys, default=""):
        for k in keys:
            v = d.get(k)
            if v is not None and v != "":
                return v
        return default

    result = {
        "full_name": _get(base, "ORG_NAME", "gsmc"),
        "short_name": _get(base, "SECURITY_NAME_ABBR", "agjc"),
        "industry": _get(base, "EM2016", "sshy"),
        "csrc_industry": _get(base, "INDUSTRYCSRC1", "sszjhhy"),
        "controller": _get(base, "PRESIDENT", "zjl"),
        "legal_rep": _get(base, "LEGAL_PERSON", "frdb"),
        "registered_capital": _get(base, "REG_CAPITAL", "zczb"),
        "listing_date": _get(fxxg, "LISTING_DATE", "ssrq"),
        "employees": _get(base, "EMP_NUM", "gyrs"),
        "main_business": _get(base, "BUSINESS_SCOPE", "ywmc"),
        "product_type": "",
        "product_names": "",
        "summary": _get(base, "ORG_PROFILE", "gsjj"),
        "province": _get(base, "PROVINCE"),
    }

    # 尝试用 akshare 补充主营业务
    code = _get(fxxg, "SECURITY_CODE") or _get(base, "SECURITY_CODE", "STR_CODEA")
    if code:
        try:
            import akshare as ak
            zyjs = ak.stock_zyjs_ths(symbol=code)
            if zyjs is not None and len(zyjs) > 0:
                row = zyjs.iloc[0]
                result["main_business"] = str(row.get("主营业务", ""))
                result["product_type"] = str(row.get("产品类型", ""))
                result["product_names"] = str(row.get("产品名称", ""))
        except Exception:
            pass

    return result


def analyze(symbol: str, em_data: dict = None) -> dict:
    """公司概况分析
    
    Args:
        symbol: 股票代码
        em_data: Playwright 预获取的 F10 原始数据 (可选)
    """
    if em_data and em_data.get("jbzl"):
        info = _parse_f10_raw(em_data)
    else:
        info = company_info(symbol)
    
    return {
        "full_name": info.get("full_name", ""),
        "short_name": info.get("short_name", ""),
        "industry": info.get("industry", ""),
        "csrc_industry": info.get("csrc_industry", ""),
        "province": info.get("province", ""),
        "listing_date": info.get("listing_date", ""),
        "main_business": info.get("main_business", ""),
        "product_type": info.get("product_type", ""),
        "product_names": info.get("product_names", ""),
        "summary": info.get("summary", ""),
        "business_scope": info.get("business_scope", ""),
    }
