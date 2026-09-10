#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""概念映射表对比检查 — 对比东财最新概念列表与本地映射表

用途:
1. 定时检查 (每90天): 发现新增/消失的概念
2. 手动触发: python3 scripts/check_concept_mapping.py

输出:
- 新增概念 (东财有, 映射表无)
- 消失概念 (映射表有, 东财无)
- 统计报告
"""

import json
import os
import re
import sys
import requests
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

_DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data')
_MAPPING_FILE = os.path.join(_DATA_DIR, 'concept_mapping.json')
_MANUAL_FILE = os.path.join(_DATA_DIR, 'hot_concepts_manual.json')
_EM_LIST_FILE = os.path.join(_DATA_DIR, 'em_concept_list.json')


def fetch_em_concepts() -> dict:
    """从东财HTML页面抓取最新概念列表"""
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
    url = 'https://data.eastmoney.com/bkzj/gn.html'
    
    try:
        r = requests.get(url, headers=headers, timeout=15)
        r.raise_for_status()
        pairs = re.findall(r'/bkzj/(BK\d{4})\.html">([^<]+)</a>', r.text)
        return {name: code for code, name in pairs}
    except Exception as e:
        print(f"❌ 获取东财概念列表失败: {e}")
        return {}


def load_local_mapping() -> dict:
    """加载本地映射表中的所有概念名"""
    names = set()
    
    if os.path.exists(_MAPPING_FILE):
        with open(_MAPPING_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
        names.update(data.get('concepts', {}).keys())
    
    if os.path.exists(_MANUAL_FILE):
        with open(_MANUAL_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
        names.update(data.get('concepts', {}).keys())
    
    return names


def check(verbose=True) -> dict:
    """执行对比检查"""
    # 获取东财最新概念
    em_concepts = fetch_em_concepts()
    if not em_concepts:
        return {'error': '无法获取东财概念列表'}
    
    # 加载本地映射
    local_names = load_local_mapping()
    
    # 过滤东财概念 (排除风格/市值类)
    exclude_kw = ['风格', '成长', '价值', '大盘', '小盘', '中盘', '微盘', '权重', '红利',
                  '破发', '破增', '超跌', '新高', '趋势', '反转', '题材', '预增', '预减', '扭亏']
    em_filtered = {name: code for name, code in em_concepts.items()
                   if not any(k in name for k in exclude_kw)}
    
    em_names = set(em_filtered.keys())
    
    # 对比
    new_concepts = em_names - local_names  # 东财有, 本地无
    removed_concepts = local_names - em_names  # 本地有, 东财无
    common = em_names & local_names
    
    result = {
        'check_time': datetime.now().strftime('%Y-%m-%d %H:%M'),
        'em_total': len(em_concepts),
        'em_filtered': len(em_filtered),
        'local_total': len(local_names),
        'common': len(common),
        'new_count': len(new_concepts),
        'removed_count': len(removed_concepts),
        'new_concepts': sorted([
            {'name': n, 'em_code': em_filtered[n]} for n in new_concepts
        ], key=lambda x: x['name']),
        'removed_concepts': sorted(list(removed_concepts)),
    }
    
    if verbose:
        print(f"📊 概念映射表检查报告 ({result['check_time']})")
        print(f"{'='*50}")
        print(f"东财概念总数: {result['em_total']} (过滤后: {result['em_filtered']})")
        print(f"本地映射概念: {result['local_total']}")
        print(f"共同概念: {result['common']}")
        print()
        
        if new_concepts:
            print(f"🆕 新增概念 ({len(new_concepts)}个, 东财有但本地无):")
            for item in result['new_concepts'][:30]:
                print(f"  {item['em_code']} {item['name']}")
            if len(new_concepts) > 30:
                print(f"  ... 还有 {len(new_concepts) - 30} 个")
        
        if removed_concepts:
            print(f"\n🗑️ 消失概念 ({len(removed_concepts)}个, 本地有但东财无):")
            for name in result['removed_concepts'][:20]:
                print(f"  {name}")
            if len(removed_concepts) > 20:
                print(f"  ... 还有 {len(removed_concepts) - 20} 个")
        
        if not new_concepts and not removed_concepts:
            print("✅ 映射表与东财一致, 无需更新")
    
    # 更新东财概念列表缓存
    os.makedirs(_DATA_DIR, exist_ok=True)
    with open(_EM_LIST_FILE, 'w', encoding='utf-8') as f:
        json.dump({
            'concepts': [{'code': c, 'name': n} for n, c in em_filtered.items()],
            'updated_at': datetime.now().strftime('%Y-%m-%d'),
        }, f, ensure_ascii=False, indent=2)
    
    return result


def format_report(result: dict) -> str:
    """格式化为文本报告"""
    if 'error' in result:
        return f"❌ 错误: {result['error']}"
    
    lines = [
        f"📊 概念映射表检查 ({result['check_time']})",
        f"东财{result['em_filtered']}个概念, 本地{result['local_total']}个, 共同{result['common']}个",
    ]
    
    if result['new_count'] > 0:
        lines.append(f"\n🆕 新增 {result['new_count']}个:")
        for item in result['new_concepts'][:20]:
            lines.append(f"  {item['em_code']} {item['name']}")
    
    if result['removed_count'] > 0:
        lines.append(f"\n🗑️ 消失 {result['removed_count']}个:")
        for name in result['removed_concepts'][:10]:
            lines.append(f"  {name}")
    
    if result['new_count'] == 0 and result['removed_count'] == 0:
        lines.append("\n✅ 映射表与东财一致")
    
    return '\n'.join(lines)


if __name__ == '__main__':
    result = check(verbose=True)
    
    # 也输出JSON
    if '--json' in sys.argv:
        print(json.dumps(result, ensure_ascii=False, indent=2))
