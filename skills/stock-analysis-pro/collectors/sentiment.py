# -*- coding: utf-8 -*-
"""舆情采集 — 股吧热帖 + 东财新闻搜索 + 分析师评级"""

import re
import json
import requests
from typing import List, Dict
from urllib.parse import quote
from datetime import datetime, timedelta


def guba_posts(symbol: str, limit: int = 10) -> List[Dict]:
    """获取东方财富股吧热帖"""
    code = symbol.zfill(6)
    url = f"https://guba.eastmoney.com/list,{code}.html"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Referer": f"https://guba.eastmoney.com/list,{code}.html",
    }
    resp = requests.get(url, headers=headers, timeout=15)
    resp.encoding = "utf-8"
    
    posts = []
    pattern = r'<a[^>]*href="(/news,[^"]+)"[^>]*>([^<]+)</a>'
    matches = re.findall(pattern, resp.text)
    
    for href, title in matches[:limit]:
        title = title.strip()
        if title and len(title) > 5:
            posts.append({
                "title": title,
                "url": f"https://guba.eastmoney.com{href}",
                "source": "guba",
            })
    
    return posts


def stock_news(keyword: str, limit: int = 5) -> List[Dict]:
    """东财搜索API — 按关键词获取个股/概念新闻"""
    param_json = json.dumps({
        "uid": "",
        "keyword": keyword,
        "type": ["cmsArticleWebOld"],
        "client": "web",
        "clientType": "web",
        "clientVersion": "curr",
        "param": {
            "cmsArticleWebOld": {
                "searchScope": "default",
                "sort": "default",
                "pageIndex": 1,
                "pageSize": limit,
            }
        }
    }, ensure_ascii=False)

    url = f"https://search-api-web.eastmoney.com/search/jsonp?cb=jQuery&param={quote(param_json)}"
    headers = {
        "User-Agent": "Mozilla/5.0",
        "Referer": "https://so.eastmoney.com/",
    }
    resp = requests.get(url, headers=headers, timeout=10)
    text = resp.text.strip()

    try:
        start = text.index("(") + 1
        end = text.rindex(")")
        data = json.loads(text[start:end])
    except (ValueError, json.JSONDecodeError):
        return []

    articles = data.get("result", {}).get("cmsArticleWebOld", [])
    if not isinstance(articles, list):
        return []

    results = []
    for a in articles[:limit]:
        title = a.get("title", "").replace("<em>", "").replace("</em>", "")
        content = a.get("content", "").replace("<em>", "").replace("</em>", "")
        results.append({
            "title": title,
            "date": a.get("date", "")[:10],
            "media": a.get("mediaName", ""),
            "content": content[:200],
            "url": a.get("url", ""),
            "source": "eastmoney_search",
        })

    return results


def interactive_qa(symbol: str, limit: int = 10) -> List[Dict]:
    """东财互动易 — 投资者问答 (guba.eastmoney.com/qa/)

    Args:
        symbol: 股票代码 (如 "603893")
        limit: 返回条数上限

    Returns:
        [{question, answer, date, user}] 列表
    """
    code = symbol.zfill(6)
    url = f"https://guba.eastmoney.com/qa/qa_search.aspx?company={code}&keyword=&questioner=&qatype=1"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Referer": "https://guba.eastmoney.com/",
    }

    try:
        resp = requests.get(url, headers=headers, timeout=10)
        resp.encoding = "utf-8"
        html = resp.text
    except Exception:
        return []

    # Extract JSON block
    match = re.search(r'var\s+\w+\s*=\s*(\{.*?\});', html, re.S)
    if not match:
        return []

    try:
        data = json.loads(match.group(1))
    except json.JSONDecodeError:
        return []

    posts = data.get("re", [])
    results = []
    for p in posts[:limit]:
        q = p.get("ask_question", "") or p.get("post_title", "")
        a = p.get("ask_answer", "") or p.get("post_content", "")
        date = p.get("post_publish_time", "")[:10]
        user = p.get("user_nickname", "")

        if q and a:
            results.append({
                "question": q,
                "answer": a,
                "date": date,
                "user": user,
            })

    return results


def analyst_ratings(symbol: str, days: int = 180, limit: int = 10) -> Dict:
    """分析师评级 — 东财研报接口 (reportapi.eastmoney.com)

    Args:
        symbol: 股票代码
        days: 回溯天数 (默认180天)
        limit: 返回研报上限

    Returns:
        {
            "reports": [{date, org, title, rating, target_pe, eps_this_year, eps_next_year, researcher}],
            "summary": {total, buy, overweight, hold, sell, avg_eps_this_year, avg_eps_next_year},
        }
    """
    end = datetime.now().strftime("%Y-%m-%d")
    start = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
    url = (
        f"https://reportapi.eastmoney.com/report/list"
        f"?industryCode=*&pageNo=1&pageSize={limit}"
        f"&code={symbol}&beginTime={start}&endTime={end}&qType=0"
    )
    headers = {
        "User-Agent": "Mozilla/5.0",
        "Referer": "https://data.eastmoney.com/",
    }

    try:
        resp = requests.get(url, headers=headers, timeout=10)
        data = resp.json()
    except Exception:
        return {"reports": [], "summary": {"total": 0}}

    raw_list = data.get("data", [])
    if not raw_list:
        return {"reports": [], "summary": {"total": 0}}

    reports = []
    rating_counts = {}

    for r in raw_list:
        rating = r.get("emRatingName", "")
        rating_counts[rating] = rating_counts.get(rating, 0) + 1

        report = {
            "date": r.get("publishDate", "")[:10],
            "org": r.get("orgSName", ""),
            "title": r.get("title", ""),
            "rating": rating,
            "s_rating": r.get("sRatingName", ""),
            "researcher": r.get("researcher", ""),
        }

        # EPS预测
        eps_this = r.get("predictThisYearEps")
        eps_next = r.get("predictNextYearEps")
        eps_next2 = r.get("predictNextTwoYearEps")
        if eps_this:
            try:
                report["eps_this_year"] = round(float(eps_this), 2)
            except (ValueError, TypeError):
                report["eps_this_year"] = None
        if eps_next:
            try:
                report["eps_next_year"] = round(float(eps_next), 2)
            except (ValueError, TypeError):
                report["eps_next_year"] = None
        if eps_next2:
            try:
                report["eps_next2_year"] = round(float(eps_next2), 2)
            except (ValueError, TypeError):
                report["eps_next2_year"] = None

        # PE预测
        pe_this = r.get("predictThisYearPe")
        pe_next = r.get("predictNextYearPe")
        if pe_this:
            try:
                report["pe_this_year"] = round(float(pe_this), 2)
            except (ValueError, TypeError):
                pass
        if pe_next:
            try:
                report["pe_next_year"] = round(float(pe_next), 2)
            except (ValueError, TypeError):
                pass

        reports.append(report)

    # 汇总
    eps_this_vals = [r.get("eps_this_year") for r in reports if r.get("eps_this_year")]
    eps_next_vals = [r.get("eps_next_year") for r in reports if r.get("eps_next_year")]

    summary = {
        "total": len(reports),
        "rating_distribution": rating_counts,
        "period": f"{start} ~ {end}",
    }

    if eps_this_vals:
        summary["avg_eps_this_year"] = round(sum(eps_this_vals) / len(eps_this_vals), 2)
        summary["eps_this_year_count"] = len(eps_this_vals)
    if eps_next_vals:
        summary["avg_eps_next_year"] = round(sum(eps_next_vals) / len(eps_next_vals), 2)
        summary["eps_next_year_count"] = len(eps_next_vals)

    # 一致评级
    buy = rating_counts.get("买入", 0) + rating_counts.get("强烈推荐", 0)
    overweight = rating_counts.get("增持", 0) + rating_counts.get("推荐", 0)
    hold = rating_counts.get("持有", 0) + rating_counts.get("中性", 0)
    sell = rating_counts.get("减持", 0) + rating_counts.get("卖出", 0)

    summary["buy"] = buy
    summary["overweight"] = overweight
    summary["hold"] = hold
    summary["sell"] = sell

    # 一致性判断
    total_rated = buy + overweight + hold + sell
    if total_rated > 0:
        bull_ratio = (buy + overweight) / total_rated
        if bull_ratio >= 0.8:
            summary["consensus"] = "强烈看多"
        elif bull_ratio >= 0.6:
            summary["consensus"] = "偏多"
        elif bull_ratio >= 0.4:
            summary["consensus"] = "分歧"
        else:
            summary["consensus"] = "偏空"
    else:
        summary["consensus"] = "无评级"

    return {
        "reports": reports,
        "summary": summary,
    }
