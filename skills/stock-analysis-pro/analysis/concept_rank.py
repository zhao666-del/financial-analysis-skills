# -*- coding: utf-8 -*-
"""概念板块排名计算引擎 — 基于东方财富push2实时数据

流程:
1. 从东财push2获取概念板块 (按资金流入排序, 过滤非行业, 保留10个)
2. 获取每个概念的成分股 (按涨幅, 前100只, 合并到离线缓存)
3. 在线失败时用离线缓存兜底
4. 按成分股平均涨幅排序输出

随逐次获取, 离线缓存的概念和成分股会越来越完整
"""

import time
from typing import Optional

from collectors.em_concept import (
    fetch_concept_list,
    fetch_concept_stocks,
    get_cached_stocks,
    _load_cache,
)


def rank_concepts(
    top_n: int = 10,
    min_stocks: int = 5,
    verbose: bool = False,
    fetch_stocks: bool = True,
) -> list:
    """
    获取概念板块实时排名
    
    Args:
        top_n: 保留前N个有效概念 (过滤非行业后)
        min_stocks: 概念至少有N只成分股才纳入
        verbose: 是否打印进度
    
    Returns:
        [
            {
                'name': '存储芯片',
                'bk_code': 'BK1137',
                'change_pct': 4.25,
                'avg_pct': 4.25,  # 成分股平均涨幅
                'net_inflow': 1234567890,
                'up_count': 35,
                'down_count': 15,
                'total': 50,
                'up_ratio': 70.0,
                'total_amount_yi': 500.0,
                'leader': '兆易创新',
                'leader_code': 'sh603986',
                'leader_pct': 8.5,
                'stocks': [...],
                'source': 'eastmoney',
            },
            ...
        ]
    """
    # Step 1: 获取概念列表 (按资金流入排序, 过滤非行业, 保留top_n个)
    concepts = fetch_concept_list(top_n=top_n, verbose=verbose)
    if not concepts:
        return []
    
    if verbose:
        print(f"  概念列表: {len(concepts)} 个 (按资金流入排序)")
    
    results = []
    
    for i, c in enumerate(concepts):
        bk_code = c['bk_code']
        name = c['name']
        
        if fetch_stocks:
            # ── 完整模式: 拉成分股，计算精确统计 ──
            stocks = fetch_concept_stocks(bk_code, name=name, limit=100, verbose=verbose)
            
            if len(stocks) < min_stocks:
                if verbose:
                    print(f"  跳过 {name}: 成分股{len(stocks)}只 < {min_stocks}")
                continue
            
            # 计算统计
            up_count = 0
            down_count = 0
            pct_sum = 0.0
            amount_sum = 0.0
            valid_count = 0
            
            for s in stocks:
                try:
                    pct = float(s.get('change_pct', 0) or 0)
                except (ValueError, TypeError):
                    pct = 0
                try:
                    amount = float(s.get('amount', 0) or 0)
                except (ValueError, TypeError):
                    amount = 0
                
                valid_count += 1
                pct_sum += pct
                amount_sum += amount
                
                if pct > 0:
                    up_count += 1
                elif pct < 0:
                    down_count += 1
            
            if valid_count < min_stocks:
                continue
            
            avg_pct = round(pct_sum / valid_count, 2)
            up_ratio = round(up_count / valid_count * 100, 1) if valid_count > 0 else 0
            
            # 成分股详情
            stock_details = []
            for s in stocks:
                try:
                    amount_val = float(s.get('amount', 0) or 0)
                except (ValueError, TypeError):
                    amount_val = 0
                try:
                    pct_val = float(s.get('change_pct', 0) or 0)
                except (ValueError, TypeError):
                    pct_val = 0
                try:
                    turnover_val = float(s.get('turnover', 0) or 0)
                except (ValueError, TypeError):
                    turnover_val = 0
                    
                stock_details.append({
                    'symbol': s['symbol'],
                    'name': s.get('name', ''),
                    'pct': round(pct_val, 2),
                    'price': s.get('price', 0),
                    'amount_yi': round(amount_val / 1e8, 2),
                    'turnover': turnover_val,
                })
            
            stock_details.sort(key=lambda x: -x['pct'])
            
            results.append({
                'name': name,
                'bk_code': bk_code,
                'em_code': bk_code,
                'change_pct': c['change_pct'],
                'avg_pct': avg_pct,
                'up_count': up_count,
                'down_count': down_count,
                'total': valid_count,
                'up_ratio': up_ratio,
                'net_inflow': c.get('net_inflow', 0),
                'total_amount_yi': round(amount_sum / 1e8, 1),
                'leader': c.get('leader', ''),
                'leader_code': c.get('leader_code', ''),
                'leader_pct': c.get('leader_pct', 0),
                'stocks': stock_details,
                'source': 'eastmoney',
            })
        else:
            # ── 轻量模式: 不拉成分股，用API涨跌家数填充 ──
            api_up = c.get('up_count', 0) or 0
            api_dn = c.get('down_count', 0) or 0
            total = api_up + api_dn
            
            if total < min_stocks:
                if verbose:
                    print(f"  跳过 {name}: 成分股{total}只 < {min_stocks}")
                continue
            
            avg_pct = c.get('change_pct', 0)
            up_ratio = round(api_up / total * 100, 1) if total > 0 else 0
            
            results.append({
                'name': name,
                'bk_code': bk_code,
                'em_code': bk_code,
                'change_pct': c['change_pct'],
                'avg_pct': avg_pct,
                'up_count': api_up,
                'down_count': api_dn,
                'total': total,
                'up_ratio': up_ratio,
                'net_inflow': c.get('net_inflow', 0),
                'total_amount_yi': 0,
                'leader': c.get('leader', ''),
                'leader_code': c.get('leader_code', ''),
                'leader_pct': c.get('leader_pct', 0),
                'stocks': [],
                'source': 'eastmoney',
            })
        
        if verbose:
            print(f"  [{i+1}/{len(concepts)}] {name} {'均涨' if fetch_stocks else '涨跌'}{results[-1]['avg_pct']:+.2f}% 成分{results[-1]['total']}只")
    
    # 按成分股平均涨幅排序 (反映当日真实热度)
    results.sort(key=lambda x: -x['avg_pct'])
    
    if verbose:
        cache = _load_cache()
        print(f"  排名完成: {len(results)} 个概念 | 离线缓存: {len(cache)} 个概念")
    
    return results


def get_concept_detail(bk_code: str, concept_name: str = '') -> Optional[dict]:
    """获取单个概念的详细数据 (成分股行情)"""
    stocks = fetch_concept_stocks(bk_code, name=concept_name, limit=100)
    
    stock_details = []
    for s in stocks:
        try:
            pct_val = float(s.get('change_pct', 0) or 0)
        except (ValueError, TypeError):
            pct_val = 0
        try:
            amount_val = float(s.get('amount', 0) or 0)
        except (ValueError, TypeError):
            amount_val = 0
            
        stock_details.append({
            'symbol': s['symbol'],
            'name': s.get('name', ''),
            'pct': round(pct_val, 2),
            'price': s.get('price', 0),
            'amount_yi': round(amount_val / 1e8, 2),
            'turnover': s.get('turnover', 0),
        })
    
    stock_details.sort(key=lambda x: -x['pct'])
    
    return {
        'name': concept_name,
        'bk_code': bk_code,
        'em_code': bk_code,
        'stocks': stock_details,
        'total': len(stock_details),
    }


def get_cache_stats() -> dict:
    """查看离线缓存统计"""
    cache = _load_cache()
    total_stocks = sum(len(info.get('stocks', [])) for info in cache.values())
    return {
        'concept_count': len(cache),
        'total_stocks': total_stocks,
        'concepts': [
            {'bk_code': k, 'name': v.get('name', ''), 'stock_count': len(v.get('stocks', []))}
            for k, v in sorted(cache.items(), key=lambda x: -len(x[1].get('stocks', [])))
        ]
    }


# ── 兼容旧接口 ──

def load_concept_mapping() -> dict:
    """兼容接口: 旧代码可能调用此函数, 返回离线缓存"""
    return _load_cache()
