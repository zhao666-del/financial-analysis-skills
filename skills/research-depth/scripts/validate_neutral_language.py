#!/usr/bin/env python3
"""Audit Chinese investment research drafts for subjective or promotional language."""

from __future__ import annotations

import argparse
import json
import re
import sys
import zipfile
from pathlib import Path
from xml.etree import ElementTree


HARD_RULES: dict[str, tuple[tuple[str, str], ...]] = {
    "第一人称立场": (
        ("我认为", "改为基于事实、计算和条件的判断"),
        ("我们认为", "改为基于事实、计算和条件的判断"),
        ("笔者认为", "删除写作者自我指涉，直接给出证据与条件"),
        ("在我看来", "删除写作者自我指涉，直接给出证据与条件"),
        ("我们相信", "改为说明支持该判断的证据和置信度"),
        ("我们坚信", "改为说明支持该判断的证据和置信度"),
    ),
    "无条件确定性": (
        ("毫无疑问", "改为条件化结论并标注置信度"),
        ("显而易见", "列出证据和推理过程"),
        ("毋庸置疑", "改为条件化结论并标注置信度"),
        ("一定会", "改为情景、概率或条件表达"),
        ("必然上涨", "删除确定性价格预测"),
        ("必然下跌", "删除确定性价格预测"),
        ("肯定上涨", "删除确定性价格预测"),
        ("肯定下跌", "删除确定性价格预测"),
    ),
    "投资煽动或收益承诺": (
        ("稳赚", "删除收益承诺"),
        ("保赚", "删除收益承诺"),
        ("必买", "改为投资结论与适用条件"),
        ("闭眼买", "改为投资结论与适用条件"),
        ("无脑买", "改为投资结论与适用条件"),
        ("坚决买入", "改为有条件评级并披露假设"),
        ("强烈推荐", "改为有条件评级并披露假设"),
    ),
    "营销化标签": (
        ("黄金赛道", "改为可复算的需求、供给和资本回报判断"),
        ("行业盛宴", "改为行业景气与盈利条件"),
        ("王者归来", "改为市场份额、盈利或竞争位置变化"),
        ("无敌", "改为具体竞争指标"),
        ("伟大公司", "改为公司质量与资本回报的可核验描述"),
        ("完美标的", "改为优势、风险与适用条件"),
        ("绝佳机会", "改为估值区间、假设与风险收益条件"),
        ("超级风口", "改为需求驱动、持续期与供给响应"),
        ("十倍股", "删除未经模型支持的收益标签"),
        ("颠覆性机会", "改为技术路线、商业化阶段与经济性"),
        ("革命性机会", "改为技术路线、商业化阶段与经济性"),
    ),
}

SOFT_RULES: dict[str, tuple[tuple[str, str], ...]] = {
    "无基准程度词": (
        ("非常", "补充数值和比较基准，或删除程度词"),
        ("极其", "补充数值和比较基准，或删除程度词"),
        ("大幅", "补充变动幅度、期间和比较基准"),
        ("强劲", "补充增长率、盈利或订单等量化证据"),
        ("爆发式", "补充增长率、持续期和基数影响"),
        ("空间巨大", "补充需求公式、口径和区间"),
    ),
    "无证据评价词": (
        ("优秀", "改为具体指标及同业或历史比较"),
        ("优质", "改为具体指标及同业或历史比较"),
        ("卓越", "改为具体指标及同业或历史比较"),
        ("明显低估", "补充估值模型、假设和敏感性"),
        ("严重高估", "补充估值模型、假设和敏感性"),
        ("高度确定", "披露条件、反证和置信度"),
        ("确定性强", "披露条件、反证和置信度"),
        ("充分证明", "说明证据边界和替代解释"),
        ("核心资产", "说明定义、比较范围和可核验指标"),
    ),
    "修辞性引导": (
        ("不难看出", "直接陈述数据、推理和结论"),
        ("值得注意的是", "直接说明重要性及其财务或风险影响"),
        ("令人担忧", "改为风险触发因素、传导路径和阈值"),
        ("令人振奋", "改为已确认进展、财务影响和待验证条件"),
    ),
}

QUOTE_PATTERN = re.compile(
    r"“[^”]*”|‘[^’]*’|\"[^\"\n]*\"|'[^'\n]*'|《[^》]*》",
    flags=re.DOTALL,
)


def read_docx(path: Path) -> str:
    with zipfile.ZipFile(path) as archive:
        xml = archive.read("word/document.xml")
    root = ElementTree.fromstring(xml)
    paragraphs: list[str] = []
    for paragraph in root.iter():
        if not paragraph.tag.endswith("}p"):
            continue
        fragments = [
            node.text or ""
            for node in paragraph.iter()
            if node.tag.endswith("}t")
        ]
        if fragments:
            paragraphs.append("".join(fragments))
    return "\n".join(paragraphs)


def read_report(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix == ".docx":
        return read_docx(path)
    if suffix in {".md", ".txt"}:
        return path.read_text(encoding="utf-8-sig")
    raise ValueError("仅支持 .md、.txt 和 .docx")


def mask_quoted_text(line: str) -> str:
    return QUOTE_PATTERN.sub(lambda match: " " * len(match.group(0)), line)


def excerpt(line: str, start: int, length: int, radius: int = 24) -> str:
    left = max(0, start - radius)
    right = min(len(line), start + length + radius)
    return line[left:right].strip()


def audit_text(text: str) -> dict[str, object]:
    findings: list[dict[str, object]] = []
    for line_number, original_line in enumerate(text.splitlines(), start=1):
        line = mask_quoted_text(original_line)
        for severity, groups in (("error", HARD_RULES), ("warning", SOFT_RULES)):
            for category, rules in groups.items():
                for term, suggestion in rules:
                    for match in re.finditer(re.escape(term), line):
                        findings.append(
                            {
                                "severity": severity,
                                "category": category,
                                "term": term,
                                "line": line_number,
                                "column": match.start() + 1,
                                "excerpt": excerpt(
                                    original_line, match.start(), len(term)
                                ),
                                "suggestion": suggestion,
                            }
                        )
    errors = sum(item["severity"] == "error" for item in findings)
    warnings = sum(item["severity"] == "warning" for item in findings)
    return {
        "status": "fail" if errors else ("review" if warnings else "pass"),
        "error_count": errors,
        "warning_count": warnings,
        "findings": findings,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="检查研究报告中的第一人称、确定性、营销化和无基准评价词"
    )
    parser.add_argument("report", type=Path, help="待检查的 .md、.txt 或 .docx")
    parser.add_argument("--out", type=Path, help="可选 JSON 审计结果路径")
    parser.add_argument(
        "--fail-on-warning",
        action="store_true",
        help="存在限制性用词警告时也返回失败",
    )
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

    result = audit_text(text)
    result["report"] = str(path)
    rendered = json.dumps(result, ensure_ascii=False, indent=2)
    if args.out:
        output_path = args.out.expanduser().resolve()
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(rendered + "\n", encoding="utf-8")
    print(rendered)

    if int(result["error_count"]) > 0:
        return 1
    if args.fail_on_warning and int(result["warning_count"]) > 0:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
