# -*- coding: utf-8 -*-
"""Initialize a reproducible deep-research workspace without overwriting files."""

import argparse
import csv
import re
from pathlib import Path


EVIDENCE_COLUMNS = [
    "claim_id",
    "claim",
    "claim_type",
    "importance",
    "source_grade",
    "source_title",
    "url_or_file",
    "page_or_section",
    "data_date",
    "original_metric_definition",
    "supports_or_challenges",
    "confidence",
    "review_status",
    "notes",
]

ASSUMPTION_COLUMNS = [
    "assumption_id",
    "business_or_segment",
    "driver",
    "historical_base",
    "pressure_case",
    "base_case",
    "upside_case",
    "unit",
    "source_or_rationale",
    "confidence",
]


def safe_name(value):
    cleaned = re.sub(r'[<>:"/\\|?*]+', "_", value).strip(" .")
    return cleaned or "deep_research"


def write_text(path, content):
    if path.exists():
        return False
    path.write_text(content, encoding="utf-8")
    return True


def write_csv(path, columns):
    if path.exists():
        return False
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        csv.writer(handle).writerow(columns)
    return True


def main():
    parser = argparse.ArgumentParser(description="初始化证券与产业深度研究目录")
    parser.add_argument("--target", required=True, help="公司或行业名称")
    parser.add_argument("--type", choices=["company", "industry"], default="company")
    parser.add_argument("--sector", default="general", help="行业模块名称")
    parser.add_argument("--output", required=True, help="输出目录或其父目录")
    args = parser.parse_args()

    output = Path(args.output).expanduser().resolve()
    if output.suffix:
        raise SystemExit("--output 必须是目录")
    if output.name in (".", ""):
        output = output / safe_name(args.target)
    output.mkdir(parents=True, exist_ok=True)

    for name in ("sources", "data", "charts", "draft", "output"):
        (output / name).mkdir(exist_ok=True)

    created = []
    brief = f"""# 研究任务书

- 研究对象：{args.target}
- 类型：{args.type}
- 行业模块：{args.sector}
- 数据截止日：待填写
- 可投资证券/法律主体：待核验
- 目标读者与风险承受：待填写

## 核心争议

1. 待填写
2. 待填写
3. 待填写

## 暂定多头假设

- 待填写

## 暂定空头假设

- 待填写

## 结论失效条件

- 待填写
"""
    thesis = """# 论点图

|编号|决定性结论|关键证据|财务影响|最强反方|失效阈值|跟踪指标|
|---|---|---|---|---|---|---|
|C01|待填写|待填写|待填写|待填写|待填写|待填写|
"""
    outline = """# 报告大纲与图表清单

|章节|要回答的问题|主要证据|模型或图表|状态|
|---|---|---|---|---|
|投资摘要|核心结论与估值是什么|待填写|结论矩阵|待开始|
|产业研究|需求、供给、周期和利润池如何变化|待填写|需求/供给模型|待开始|
|公司研究|业务如何兑现为利润和现金|待填写|分业务模型|待开始|
|估值与反证|当前价格隐含什么|待填写|情景与反向估值|待开始|
"""
    checks = """# 模型检查

- [ ] 分业务收入合计等于总收入
- [ ] 毛利润与综合毛利率一致
- [ ] 产量不超过有效产能
- [ ] 隐含份额与行业规模匹配
- [ ] 少数股东、税率和稀释股本已反映
- [ ] 经营现金流连接营运资金
- [ ] 自由现金流扣除资本开支
- [ ] 三种情景只修改明确假设
- [ ] 当前价格已完成反向估值
- [ ] 所有关键假设有来源或标记为分析师假设
"""
    log = f"""# 研究日志

## 初始化

- 研究对象：{args.target}
- 类型：{args.type}
- 行业模块：{args.sector}
- 说明：记录检索、口径冲突、假设变化和模型版本。
"""

    files = {
        output / "draft" / "research_brief.md": brief,
        output / "draft" / "thesis_map.md": thesis,
        output / "draft" / "report_outline.md": outline,
        output / "data" / "model_checks.md": checks,
        output / "research_log.md": log,
    }
    for path, content in files.items():
        if write_text(path, content):
            created.append(str(path))
    if write_csv(output / "evidence_register.csv", EVIDENCE_COLUMNS):
        created.append(str(output / "evidence_register.csv"))
    if write_csv(output / "assumptions.csv", ASSUMPTION_COLUMNS):
        created.append(str(output / "assumptions.csv"))

    print(f"研究目录：{output}")
    print(f"新增文件：{len(created)}")
    for path in created:
        print(path)


if __name__ == "__main__":
    main()
