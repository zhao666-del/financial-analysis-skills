# -*- coding: utf-8 -*-
"""Validate the evidence register used by deep research projects."""

import argparse
import csv
import sys
from collections import Counter
from datetime import date, datetime
from pathlib import Path


REQUIRED_COLUMNS = [
    "claim_id",
    "claim",
    "claim_type",
    "importance",
    "source_grade",
    "source_title",
    "url_or_file",
    "page_or_section",
    "data_date",
    "supports_or_challenges",
    "confidence",
    "review_status",
]
VALID_TYPES = {"事实", "推断", "预测", "fact", "inference", "forecast"}
VALID_GRADES = {"甲", "乙", "丙", "丁", "戊", "A", "B", "C", "D", "E"}
PRIMARY_GRADES = {"甲", "乙", "A", "B"}
DECISIVE = {"决定性", "decisive", "critical"}


def parse_date(value):
    value = value.strip()
    for pattern in ("%Y-%m-%d", "%Y/%m/%d", "%Y-%m", "%Y"):
        try:
            return datetime.strptime(value, pattern).date()
        except ValueError:
            pass
    return None


def main():
    parser = argparse.ArgumentParser(description="检查深度研究证据台账")
    parser.add_argument("register", help="evidence_register.csv 路径")
    parser.add_argument("--as-of", help="报告数据截止日，YYYY-MM-DD")
    args = parser.parse_args()

    path = Path(args.register).resolve()
    if not path.exists():
        print(f"错误：文件不存在：{path}")
        return 2

    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        missing_columns = [name for name in REQUIRED_COLUMNS if name not in (reader.fieldnames or [])]
        if missing_columns:
            print("错误：缺少字段：" + ", ".join(missing_columns))
            return 2
        rows = list(reader)

    errors = []
    warnings = []
    if not rows:
        warnings.append("证据台账只有表头，尚无证据记录")

    as_of = parse_date(args.as_of) if args.as_of else date.today()
    claim_sources = Counter()
    decisive_primary = Counter()
    challenges = Counter()

    for number, row in enumerate(rows, start=2):
        prefix = f"第{number}行"
        for field in REQUIRED_COLUMNS:
            if not (row.get(field) or "").strip():
                errors.append(f"{prefix}缺少 {field}")
        claim_id = (row.get("claim_id") or "").strip()
        claim_type = (row.get("claim_type") or "").strip()
        grade = (row.get("source_grade") or "").strip()
        importance = (row.get("importance") or "").strip()
        direction = (row.get("supports_or_challenges") or "").strip().lower()
        if claim_type and claim_type not in VALID_TYPES:
            warnings.append(f"{prefix}结论类型不规范：{claim_type}")
        if grade and grade not in VALID_GRADES:
            warnings.append(f"{prefix}来源等级不规范：{grade}")
        if claim_id:
            claim_sources[claim_id] += 1
            if importance in DECISIVE and grade in PRIMARY_GRADES:
                decisive_primary[claim_id] += 1
            if direction in {"反对", "混合", "challenge", "challenges", "mixed"}:
                challenges[claim_id] += 1
        parsed = parse_date(row.get("data_date") or "")
        if parsed and as_of and parsed > as_of:
            errors.append(f"{prefix}数据日期晚于截止日：{parsed}")

    decisive_ids = {
        (row.get("claim_id") or "").strip()
        for row in rows
        if (row.get("importance") or "").strip() in DECISIVE
    }
    for claim_id in sorted(decisive_ids):
        if decisive_primary[claim_id] == 0:
            errors.append(f"决定性结论 {claim_id} 没有甲/乙级证据")
        if claim_sources[claim_id] < 2:
            warnings.append(f"决定性结论 {claim_id} 只有一个证据来源")
        if challenges[claim_id] == 0:
            warnings.append(f"决定性结论 {claim_id} 没有反向或混合证据")

    print(f"证据记录：{len(rows)}")
    print(f"结论数量：{len(claim_sources)}")
    print(f"错误：{len(errors)}")
    for item in errors:
        print("ERROR: " + item)
    print(f"警告：{len(warnings)}")
    for item in warnings:
        print("WARN: " + item)

    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
