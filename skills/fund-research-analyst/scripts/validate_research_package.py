#!/usr/bin/env python3
"""Validate an institutional fund research package and apply rating gates."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


MINIMUM_COVERAGE = {
    "annual_reports": 3,
    "quarterly_reports": 8,
    "legal_documents": 3,
    "independent_method_sources": 8,
}


def _truthy(mapping: dict[str, Any], key: str) -> bool:
    return bool(mapping.get(key, False))


def validate(package: dict[str, Any]) -> dict[str, Any]:
    coverage = package.get("source_coverage", {})
    due_diligence = package.get("due_diligence", {})
    attribution = package.get("alpha_attribution", {})
    capacity = package.get("capacity", {})
    peer = package.get("peer_universe", {})
    red_team = package.get("red_team", {})
    claims = package.get("claims", [])

    coverage_gaps: list[str] = []
    for field, minimum in MINIMUM_COVERAGE.items():
        actual = int(coverage.get(field, 0) or 0)
        if actual < minimum:
            coverage_gaps.append(f"{field}: {actual}/{minimum}")
    if not _truthy(coverage, "fund_contract_current"):
        coverage_gaps.append("缺少当前有效基金合同")
    if not _truthy(coverage, "benchmark_method_current"):
        coverage_gaps.append("缺少当前基准或指数方法")

    vetoes: list[dict[str, str]] = []
    if not _truthy(attribution, "major_alpha_sources_distinguished"):
        vetoes.append(
            {
                "code": "ALPHA_UNEXPLAINED",
                "reason": "未能区分主要超额来自因子、证券选择或特殊收益",
                "remedy": "补充完整持仓、因子序列、特殊收益和费用交易成本归因",
            }
        )
    governance_ok = _truthy(due_diligence, "team_governance_assessed") and _truthy(
        due_diligence, "model_or_process_governance_assessed"
    )
    if not governance_ok:
        vetoes.append(
            {
                "code": "GOVERNANCE_UNVERIFIED",
                "reason": "团队职责、投研流程或模型治理无法充分核验",
                "remedy": "完成People/Process/Parent、运营尽调和关键RFI",
            }
        )
    if not _truthy(capacity, "quantified"):
        vetoes.append(
            {
                "code": "CAPACITY_UNQUANTIFIED",
                "reason": "策略容量、流动性或赎回冲击未量化",
                "remedy": "补充完整持仓、成交量、受限状态、申赎和相似策略规模",
            }
        )

    claim_gaps: list[str] = []
    if not claims:
        claim_gaps.append("缺少核心声明台账")
    for index, claim in enumerate(claims):
        claim_id = str(claim.get("claim_id") or f"claim_{index + 1}")
        required = ["question", "claim", "evidence_for", "evidence_against", "confidence"]
        missing = [field for field in required if not claim.get(field)]
        if missing:
            claim_gaps.append(f"{claim_id}: 缺少 {', '.join(missing)}")

    peer_gaps: list[str] = []
    if not _truthy(peer, "share_classes_deduplicated"):
        peer_gaps.append("同基金多份额未去重")
    if not _truthy(peer, "same_end_date_and_return_basis"):
        peer_gaps.append("同类截止日期或收益口径不统一")
    if not _truthy(peer, "passive_alternatives_included"):
        peer_gaps.append("未纳入低费率被动替代品")
    if not _truthy(peer, "dead_or_transformed_funds_considered"):
        peer_gaps.append("未考虑清盘或转型样本，存在幸存者偏差")

    red_team_gaps: list[str] = []
    if not _truthy(red_team, "completed"):
        red_team_gaps.append("未完成Red Team审查")
    if len(red_team.get("strongest_rejection_arguments", [])) < 3:
        red_team_gaps.append("少于三项最强拒绝理由")
    if not red_team.get("responses"):
        red_team_gaps.append("未回应最强反方观点")

    complete = not (coverage_gaps or vetoes or claim_gaps or peer_gaps or red_team_gaps)
    if complete:
        status = "完整尽调"
        rating_ceiling = "准入"
    elif not vetoes and _truthy(red_team, "completed"):
        status = "公开资料尽调"
        rating_ceiling = "条件准入"
    else:
        status = "研究草案"
        rating_ceiling = "观察" if vetoes else "条件准入"

    return {
        "validation_status": status,
        "rating_ceiling": rating_ceiling,
        "hard_vetoes": vetoes,
        "coverage_gaps": coverage_gaps,
        "claim_ledger_gaps": claim_gaps,
        "peer_universe_gaps": peer_gaps,
        "red_team_gaps": red_team_gaps,
        "can_label_complete_due_diligence": complete,
        "summary": (
            "达到机构级完整尽调门槛"
            if complete
            else "仍有关键证据或流程缺口，结论必须受评级上限约束"
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    package = json.loads(args.input.read_text(encoding="utf-8-sig"))
    result = validate(package)
    text = json.dumps(result, ensure_ascii=False, indent=2)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text, encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
