#!/usr/bin/env python3
"""Check whether a draft is industry-centric and contains core research modules."""

from __future__ import annotations

import argparse
import re
import sys
import zipfile
from pathlib import Path
from xml.etree import ElementTree


REQUIRED_MODULES = {
    "产业边界": ("产业边界", "研究边界", "研究范围", "纳入范围"),
    "可证伪命题": ("产业命题", "研究命题", "反证条件", "证伪", "反证阈值"),
    "周期定位": ("周期定位", "长周期", "中周期", "短周期", "库存周期"),
    "需求模型": ("需求模型", "需求测算", "终端数量", "单机用量", "渗透率"),
    "有效供给": ("有效供给", "名义产能", "良率", "产能爬坡", "供给模型"),
    "技术路线": ("技术路线", "路线对比", "工程瓶颈", "科技原理"),
    "技术变现": ("技术变现", "单机价值", "单位价值", "物料清单", "利润池迁移"),
    "竞争与利润池": ("利润池", "议价权", "资本回报", "竞争格局", "控制点"),
    "情景推演": ("悲观情景", "基准情景", "乐观情景", "情景推演", "三种情景"),
    "产业投资地图": ("产业投资地图", "产业链投资", "受益环节", "投资映射"),
    "风险阈值": ("触发阈值", "警戒阈值", "反证阈值", "传导路径"),
    "资料口径": ("数据截止日", "资料来源", "来源登记", "数据口径"),
}

CHAIN_REQUIRED_MODULES = {
    "产业链全景": ("全产业链", "产业链全景", "产业链总图", "价值链全景", "价值交付链"),
    "产业链节点经济性": ("产业链节点", "节点经济性", "环节经济性", "节点功能", "输入与输出"),
    "跨节点流向": ("资金流", "产品流", "服务流", "数据流", "知识产权流", "责任流", "风险流"),
    "横向能力层": ("横向能力", "工具层", "基础设施层", "外包服务", "许可授权", "标准监管"),
    "公司角色矩阵": ("公司角色矩阵", "产业链角色", "产业链位置", "跨环节覆盖", "主角色"),
    "瓶颈与风险传导": ("单点瓶颈", "瓶颈传导", "风险传导", "依赖集中", "首个受影响节点"),
}

FORBIDDEN_MAIN_HEADINGS = (
    "公司概况",
    "公司简介",
    "公司发展历程",
    "股权结构",
    "管理层分析",
    "公司盈利预测",
    "三张财务",
    "目标价",
    "公司估值",
)


def read_docx(path: Path) -> str:
    with zipfile.ZipFile(path) as archive:
        xml = archive.read("word/document.xml")
    root = ElementTree.fromstring(xml)
    texts = [node.text for node in root.iter() if node.tag.endswith("}t") and node.text]
    return "\n".join(texts)


def read_report(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix == ".docx":
        return read_docx(path)
    if suffix in {".md", ".txt"}:
        return path.read_text(encoding="utf-8-sig")
    raise ValueError("仅支持 .md、.txt 和 .docx")


def markdown_headings(text: str) -> list[str]:
    return [match.group(1).strip() for match in re.finditer(r"(?m)^#{1,3}\s+(.+)$", text)]


def main() -> int:
    parser = argparse.ArgumentParser(description="校验产业深度报告的研究层级和核心模块")
    parser.add_argument("report", type=Path, help="待检查的 .md、.txt 或 .docx 文件")
    args = parser.parse_args()

    path = args.report.expanduser().resolve()
    if not path.is_file():
        print(f"错误：文件不存在：{path}")
        return 2

    try:
        text = read_report(path)
    except Exception as exc:
        print(f"错误：无法读取报告：{exc}")
        return 2

    compact = re.sub(r"\s+", "", text)
    headings = markdown_headings(text)
    hits = {
        module: any(term in compact for term in terms)
        for module, terms in REQUIRED_MODULES.items()
    }
    chain_hits = {
        module: any(term in compact for term in terms)
        for module, terms in CHAIN_REQUIRED_MODULES.items()
    }
    chain_hits["全链条层级覆盖"] = (
        any(term in compact for term in ("上游", "基础投入", "使能层"))
        and any(term in compact for term in ("中游", "价值创造层", "转化层"))
        and any(term in compact for term in ("下游", "交付层", "运营层"))
        and any(term in compact for term in ("终端需求", "终端客户", "付费方"))
    )
    missing = [module for module, present in hits.items() if not present]
    chain_missing = [module for module, present in chain_hits.items() if not present]
    forbidden = [
        heading
        for heading in headings
        if any(term in heading for term in FORBIDDEN_MAIN_HEADINGS)
    ]

    warnings: list[str] = []
    if len(compact) < 6000:
        warnings.append("正文少于约 6000 个字符，可能尚未达到深度报告的信息密度。")
    if "事实" not in compact or ("估算" not in compact and "预测" not in compact):
        warnings.append("尚未清楚区分事实与估算/预测。")
    if "公司" in compact and "案例" not in compact and "代表性" not in compact:
        warnings.append("正文提到公司，但未明确采用案例卡或代表性样本方式。")
    chain_positions = [
        compact.find(term)
        for term in CHAIN_REQUIRED_MODULES["产业链全景"]
        if compact.find(term) >= 0
    ]
    if chain_positions and min(chain_positions) / max(len(compact), 1) > 0.35:
        warnings.append("全产业链分析出现较晚；应置于产业边界之后、周期和供需分析之前。")

    total_modules = len(REQUIRED_MODULES) + len(chain_hits)
    total_missing = len(missing) + len(chain_missing)
    score = round(100 * (total_modules - total_missing) / total_modules)
    chain_score = round(100 * (len(chain_hits) - len(chain_missing)) / len(chain_hits))
    print(f"产业研究完整度：{score}/100")
    print("已覆盖：" + "、".join(module for module, present in hits.items() if present))
    print(f"产业链完整度：{chain_score}/100")
    print("产业链已覆盖：" + "、".join(module for module, present in chain_hits.items() if present))

    if missing:
        print("缺失模块：" + "、".join(missing))
    if chain_missing:
        print("产业链缺失模块：" + "、".join(chain_missing))
    if forbidden:
        print("层级错误：发现公司研究式主标题：" + "；".join(forbidden))
    for warning in warnings:
        print("提醒：" + warning)

    if forbidden or len(missing) >= 3 or chain_missing:
        print("结论：未通过。请先补齐全产业链主骨架、产业系统论证并移除公司中心主章节。")
        return 1

    print("结论：通过基础结构校验。仍需人工核验数字、来源和因果关系。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
