#!/usr/bin/env python3
"""Initialize a deterministic research package with effective-reading gates."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from datetime import date
from pathlib import Path


PROFILES = {
    "quick": {
        "source_budget": 15,
        "iteration_budget": 2,
        "max_depth": 1,
        "max_parallel_branches": 4,
        "minimum_deep_read": 3,
        "minimum_primary_ratio": 0.50,
        "minimum_independent_ratio": 0.35,
        "minimum_locator_ratio": 0.80,
    },
    "standard": {
        "source_budget": 40,
        "iteration_budget": 3,
        "max_depth": 2,
        "max_parallel_branches": 6,
        "minimum_deep_read": 8,
        "minimum_primary_ratio": 0.55,
        "minimum_independent_ratio": 0.40,
        "minimum_locator_ratio": 0.85,
    },
    "deep": {
        "source_budget": 80,
        "iteration_budget": 4,
        "max_depth": 3,
        "max_parallel_branches": 8,
        "minimum_deep_read": 15,
        "minimum_primary_ratio": 0.60,
        "minimum_independent_ratio": 0.45,
        "minimum_locator_ratio": 0.90,
    },
    "institutional": {
        "source_budget": 150,
        "iteration_budget": 5,
        "max_depth": 3,
        "max_parallel_branches": 10,
        "minimum_deep_read": 25,
        "minimum_primary_ratio": 0.65,
        "minimum_independent_ratio": 0.50,
        "minimum_locator_ratio": 0.95,
    },
}

EFFECTIVE_READ_MINIMUMS = {
    "company": {"quick": 8, "standard": 20, "deep": 40, "institutional": 60},
    "fund": {"quick": 8, "standard": 20, "deep": 35, "institutional": 50},
    "industry": {"quick": 10, "standard": 25, "deep": 50, "institutional": 80},
}

# category, minimum by profile, minimum primary ratio, minimum independent ratio
COVERAGE = {
    "company": [
        ("annual_reports", (1, 3, 5, 5), 1.00, 0.00),
        ("interim_or_current_reports", (1, 2, 4, 6), 1.00, 0.00),
        ("material_announcements", (1, 2, 4, 6), 1.00, 0.00),
        ("business_segments_and_commercialization", (1, 2, 3, 5), 0.80, 0.00),
        ("governance_and_capital_allocation", (1, 2, 3, 5), 0.80, 0.20),
        ("peer_primary_filings", (1, 2, 4, 5), 0.80, 0.50),
        ("industry_technology_and_policy", (1, 3, 6, 10), 0.60, 0.50),
        ("independent_cross_checks", (1, 3, 5, 8), 0.40, 1.00),
        ("valuation_and_counterevidence", (1, 2, 3, 5), 0.40, 0.50),
    ],
    "fund": [
        ("legal_and_product_documents", (1, 3, 4, 5), 1.00, 0.00),
        ("periodic_reports", (1, 4, 8, 12), 1.00, 0.00),
        ("manager_and_team_changes", (1, 2, 3, 5), 0.80, 0.20),
        ("process_parent_and_operations", (1, 2, 3, 5), 0.70, 0.30),
        ("attribution_and_holdings", (1, 3, 5, 8), 0.60, 0.40),
        ("capacity_liquidity_and_redemption", (1, 2, 3, 5), 0.60, 0.40),
        ("peer_universe_and_alternatives", (1, 2, 3, 5), 0.50, 0.60),
        ("independent_methods", (1, 3, 6, 10), 0.50, 0.80),
        ("counterevidence", (1, 2, 3, 5), 0.40, 0.80),
    ],
    "industry": [
        ("boundary_and_history", (1, 2, 4, 6), 0.60, 0.50),
        ("demand_sources", (2, 4, 8, 12), 0.60, 0.60),
        ("supply_sources", (2, 4, 8, 12), 0.60, 0.60),
        ("technology_primary_sources", (1, 3, 6, 10), 0.70, 0.50),
        ("price_inventory_and_cycle", (1, 3, 5, 8), 0.50, 0.60),
        ("competition_and_profit_pools", (1, 3, 5, 8), 0.50, 0.60),
        ("policy_standards_and_global_trade", (1, 2, 4, 6), 0.80, 0.60),
        ("company_primary_filings", (1, 3, 5, 8), 0.80, 0.50),
        ("independent_cross_checks", (1, 3, 5, 8), 0.40, 1.00),
        ("counterevidence", (1, 2, 4, 6), 0.40, 0.80),
    ],
}

BRANCHES = {
    "company": [
        ("filings", "核验法律主体、历史披露、股本与重大事件", "critical"),
        ("business_financials", "穿透业务分部、财务质量与现金流", "critical"),
        ("current_events", "核验最新经营变化、公告和市场预期", "critical"),
        ("forecast_valuation", "建立经营驱动预测、情景和反向估值", "critical"),
        ("red_team", "寻找最强反方解释和结论失效条件", "critical"),
        ("governance", "审计治理、关联交易与资本配置", "high"),
        ("industry_technology", "研究行业周期、技术路线和商业化", "high"),
        ("peers_customers_supply", "用同业、客户和供应链交叉验证", "high"),
        ("policy_geopolitics", "检查政策、监管和地缘约束", "medium"),
        ("evidence_audit", "复核证据独立性、冲突和引用定位", "critical"),
    ],
    "fund": [
        ("legal_product", "核验合同、招募说明书、产品机制和费用", "critical"),
        ("performance_attribution", "拆分基准、因子、证券选择和特殊收益", "critical"),
        ("current_reports", "阅读定期报告、持仓和最新重大公告", "critical"),
        ("peers_alternatives", "建立完整同类池和替代产品比较", "critical"),
        ("red_team", "从拒绝准入立场寻找最强反证", "critical"),
        ("people_process_parent", "尽调人员、流程、母公司和模型治理", "high"),
        ("capacity_operations", "量化容量、流动性、申赎和运营风险", "high"),
        ("portfolio_fit", "评估组合暴露、风险预算和适配性", "high"),
        ("methods_statistics", "核验统计显著性、稳健性和方法依据", "medium"),
        ("evidence_audit", "复核证据独立性、冲突和引用定位", "critical"),
    ],
    "industry": [
        ("boundary_history", "定义行业边界、口径和历史周期", "critical"),
        ("demand_supply", "建立需求方程和有效供给方程", "critical"),
        ("current_cycle", "核验价格、库存、利用率和资本开支", "critical"),
        ("red_team", "寻找反向周期、替代技术和需求证伪证据", "critical"),
        ("technology_economics", "连接技术路线、成本、量产和利润池", "high"),
        ("competition", "研究竞争演化、份额、议价权和控制点", "high"),
        ("policy_global", "分析政策、标准、贸易和全球分工", "high"),
        ("company_mapping", "用公司原始披露映射产业链和兑现阶段", "high"),
        ("scenarios", "建立情景、敏感性和投资映射", "medium"),
        ("evidence_audit", "复核口径、证据独立性和引用定位", "critical"),
    ],
}

PROFILE_ORDER = ["quick", "standard", "deep", "institutional"]


def build_coverage(research_type: str, profile_name: str) -> list[dict]:
    profile_index = PROFILE_ORDER.index(profile_name)
    deep_share = {"quick": 0.34, "standard": 0.40, "deep": 0.45, "institutional": 0.50}[
        profile_name
    ]
    rows = []
    for category, minimums, primary_ratio, independent_ratio in COVERAGE[research_type]:
        minimum = minimums[profile_index]
        rows.append(
            {
                "category": category,
                "required": True,
                "applicable": True,
                "waiver_reason": "",
                "minimum_effective_read": minimum,
                "minimum_deep_read": max(1, math.ceil(minimum * deep_share)),
                "minimum_primary_ratio": primary_ratio,
                "minimum_independent_ratio": independent_ratio,
                "freshness_days": None,
                "effective_read_count": 0,
                "deep_read_count": 0,
                "primary_effective_count": 0,
                "independent_effective_count": 0,
                "coverage_status": "missing",
            }
        )
    return rows


def build_branches(research_type: str, profile: dict) -> list[dict]:
    selected = BRANCHES[research_type][: profile["max_parallel_branches"]]
    per_branch_budget = max(2, math.ceil(profile["source_budget"] / len(selected)))
    return [
        {
            "branch_id": branch_id,
            "question": question,
            "why_it_matters": question,
            "priority": priority,
            "preferred_source_types": [],
            "queries": [],
            "source_budget": per_branch_budget,
            "iteration_budget": profile["iteration_budget"],
            "completion_criteria": [],
            "open_questions": [],
            "status": "planned",
        }
        for branch_id, question, priority in selected
    ]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("output_dir", type=Path)
    parser.add_argument("--type", choices=sorted(COVERAGE), required=True)
    parser.add_argument("--subject", required=True)
    parser.add_argument("--profile", choices=PROFILE_ORDER, default="standard")
    parser.add_argument("--as-of-date", default=date.today().isoformat())
    args = parser.parse_args()

    root = args.output_dir.resolve()
    root.mkdir(parents=True, exist_ok=False)
    (root / "branch-results").mkdir()
    profile = PROFILES[args.profile]
    subject_key = hashlib.sha1(args.subject.encode("utf-8")).hexdigest()[:8]
    research_id = f"{args.type}_{args.as_of_date.replace('-', '')}_{subject_key}"
    thresholds = {
        "minimum_effective_read": EFFECTIVE_READ_MINIMUMS[args.type][args.profile],
        "minimum_deep_read": profile["minimum_deep_read"],
        "minimum_primary_ratio": profile["minimum_primary_ratio"],
        "minimum_independent_ratio": profile["minimum_independent_ratio"],
        "minimum_locator_ratio": profile["minimum_locator_ratio"],
    }
    manifest = {
        "research_id": research_id,
        "research_type": args.type,
        "subject": args.subject,
        "as_of_date": args.as_of_date,
        "depth_profile": args.profile,
        "max_depth": profile["max_depth"],
        "max_parallel_branches": profile["max_parallel_branches"],
        "source_budget": profile["source_budget"],
        "iteration_budget": profile["iteration_budget"],
        "reading_thresholds": thresholds,
        "status": "planning",
        "report_label": "研究草案",
        "confidence_cap": "低",
        "coverage_matrix": build_coverage(args.type, args.profile),
        "branches": build_branches(args.type, profile),
        "research_rounds": [],
        "coverage_gaps": [],
        "contradictions": [],
        "blocked_reason": "",
        "stop_conditions": {
            "required_coverage_complete": False,
            "effective_reading_complete": False,
            "source_quality_complete": False,
            "material_claims_supported": False,
            "counterevidence_searched": False,
            "conflicts_resolved_or_disclosed": False,
            "citation_traceable": False,
            "marginal_information_gain_low": False,
        },
        "statistics": {
            "sources_discovered": 0,
            "sources_opened_or_skimmed": 0,
            "effective_read_count": 0,
            "deep_read_count": 0,
            "sources_cited": 0,
            "duplicate_sources": 0,
            "primary_effective_count": 0,
            "independent_effective_count": 0,
            "primary_ratio": 0.0,
            "independent_ratio": 0.0,
            "locator_completeness": 0.0,
        },
    }
    (root / "research-manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    for name in ("source-register.jsonl", "claim-evidence.jsonl", "citation-ledger.jsonl"):
        (root / name).write_text("", encoding="utf-8")
    print(root)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
