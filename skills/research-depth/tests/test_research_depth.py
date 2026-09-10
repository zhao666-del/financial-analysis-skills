from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


SKILL_ROOT = Path(__file__).resolve().parents[1]
INIT = SKILL_ROOT / "scripts" / "init_research.py"
MERGE = SKILL_ROOT / "scripts" / "merge_branches.py"
VALIDATE = SKILL_ROOT / "scripts" / "validate_research.py"


def write_jsonl(path: Path, records: list[dict]) -> None:
    path.write_text(
        "".join(json.dumps(record, ensure_ascii=False) + "\n" for record in records),
        encoding="utf-8",
    )


class ResearchDepthTests(unittest.TestCase):
    def init_package(self, parent: Path, profile: str = "quick") -> Path:
        root = parent / "package"
        subprocess.run(
            [
                sys.executable,
                str(INIT),
                str(root),
                "--type",
                "company",
                "--subject",
                "示例公司",
                "--profile",
                profile,
                "--as-of-date",
                "2026-07-24",
            ],
            check=True,
            capture_output=True,
            text=True,
        )
        return root

    def test_init_creates_profile_specific_reading_gates(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = self.init_package(Path(temp))
            manifest = json.loads(
                (root / "research-manifest.json").read_text(encoding="utf-8")
            )
            self.assertEqual(manifest["reading_thresholds"]["minimum_effective_read"], 8)
            self.assertEqual(manifest["reading_thresholds"]["minimum_deep_read"], 3)
            self.assertEqual(len(manifest["branches"]), 4)
            self.assertTrue(
                all("minimum_deep_read" in row for row in manifest["coverage_matrix"])
            )

    def test_all_research_types_and_profiles_initialize(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            parent = Path(temp)
            for research_type in ("company", "fund", "industry"):
                for profile in ("quick", "standard", "deep", "institutional"):
                    root = parent / f"{research_type}-{profile}"
                    completed = subprocess.run(
                        [
                            sys.executable,
                            str(INIT),
                            str(root),
                            "--type",
                            research_type,
                            "--subject",
                            "示例对象",
                            "--profile",
                            profile,
                            "--as-of-date",
                            "2026-07-24",
                        ],
                        capture_output=True,
                        text=True,
                    )
                    self.assertEqual(
                        completed.returncode, 0, completed.stdout + completed.stderr
                    )
                    manifest = json.loads(
                        (root / "research-manifest.json").read_text(encoding="utf-8")
                    )
                    self.assertEqual(manifest["research_type"], research_type)
                    self.assertEqual(manifest["depth_profile"], profile)
                    self.assertGreater(
                        manifest["reading_thresholds"]["minimum_effective_read"], 0
                    )

    def test_skimmed_sources_do_not_count_as_effective_reads(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = self.init_package(Path(temp))
            write_jsonl(
                root / "source-register.jsonl",
                [
                    {
                        "source_id": "S001",
                        "title": "搜索摘要",
                        "publisher": "聚合网站",
                        "url": "https://example.com/summary",
                        "read_level": "skimmed",
                        "sections_read": ["摘要"],
                        "evidence_summary": "只阅读了摘要",
                        "primary": False,
                        "independence": "unknown",
                        "categories": ["annual_reports"],
                    }
                ],
            )
            subprocess.run(
                [sys.executable, str(VALIDATE), str(root)],
                check=True,
                capture_output=True,
                text=True,
            )
            report = json.loads(
                (root / "validation-report.json").read_text(encoding="utf-8")
            )
            self.assertEqual(report["status"], "degraded")
            self.assertEqual(report["statistics"]["effective_read_count"], 0)

    def test_quick_company_package_can_pass_all_effective_reading_gates(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = self.init_package(Path(temp))
            sources = [
                ("S001", ["annual_reports", "business_segments_and_commercialization"], True, "issuer", "issuer-a", "deep_read"),
                ("S002", ["interim_or_current_reports", "business_segments_and_commercialization"], True, "issuer", "issuer-a", "deep_read"),
                ("S003", ["material_announcements", "governance_and_capital_allocation"], True, "issuer", "issuer-a", "deep_read"),
                ("S004", ["peer_primary_filings"], True, "independent", "peer-a", "deep_read"),
                ("S005", ["industry_technology_and_policy"], True, "independent", "government-a", "deep_read"),
                ("S006", ["independent_cross_checks", "governance_and_capital_allocation"], True, "independent", "research-a", "deep_read"),
                ("S007", ["valuation_and_counterevidence"], True, "independent", "market-a", "deep_read"),
                ("S008", ["valuation_and_counterevidence"], False, "independent", "bear-a", "read"),
            ]
            source_records = []
            for source_id, categories, primary, independence, group, level in sources:
                source_records.append(
                    {
                        "source_id": source_id,
                        "title": f"资料 {source_id}",
                        "publisher": f"发布者 {source_id}",
                        "published_date": "2026-07-01",
                        "url": f"https://example.com/{source_id}",
                        "source_tier": "A" if primary else "B",
                        "primary": primary,
                        "independence": independence,
                        "independence_group": group,
                        "read_level": level,
                        "sections_read": ["第1节", "表1"],
                        "evidence_summary": "已提取与决定性研究问题相关的事实。",
                        "extracted": True,
                        "cited": source_id in {"S001", "S004", "S008"},
                        "categories": categories,
                        "branch_ids": ["filings"],
                    }
                )
            write_jsonl(root / "source-register.jsonl", source_records)
            write_jsonl(
                root / "claim-evidence.jsonl",
                [
                    {
                        "claim_id": "C001",
                        "claim": "示例决定性结论",
                        "claim_type": "inference",
                        "materiality": "decisive",
                        "status": "supported",
                        "supporting_source_ids": ["S001", "S004"],
                        "opposing_source_ids": ["S008"],
                        "supporting_independence_groups": ["issuer-a", "peer-a"],
                        "calculations": [],
                        "alternative_explanations": ["另一种解释"],
                        "confidence": "中",
                        "evidence_quality": "中高",
                        "missing_evidence": [],
                        "invalidation_conditions": ["关键指标恶化"],
                        "counter_search_scope": ["监管文件", "同业披露"],
                        "single_source_authoritative": False,
                    }
                ],
            )
            write_jsonl(
                root / "citation-ledger.jsonl",
                [
                    {
                        "citation_id": "CT001",
                        "claim_id": "C001",
                        "source_id": "S001",
                        "locator": "第1页，表1",
                        "excerpt_summary": "支持事实",
                        "accessed_at": "2026-07-24",
                    },
                    {
                        "citation_id": "CT002",
                        "claim_id": "C001",
                        "source_id": "S004",
                        "locator": "第2页，经营回顾",
                        "excerpt_summary": "独立交叉验证",
                        "accessed_at": "2026-07-24",
                    },
                ],
            )
            manifest_path = root / "research-manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["research_rounds"] = [
                {
                    "round": 1,
                    "new_sources_read": 8,
                    "new_decisive_facts": 1,
                    "new_contradictions": 0,
                    "claims_upgraded": 1,
                    "claims_downgraded": 0,
                    "new_queries_triggered": 0,
                }
            ]
            manifest_path.write_text(
                json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            completed = subprocess.run(
                [sys.executable, str(VALIDATE), str(root), "--strict"],
                capture_output=True,
                text=True,
            )
            self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
            report = json.loads(
                (root / "validation-report.json").read_text(encoding="utf-8")
            )
            self.assertEqual(report["status"], "evidence_complete")
            self.assertEqual(report["statistics"]["effective_read_count"], 8)

    def test_merge_deduplicates_tracking_urls_and_keeps_highest_read_level(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = self.init_package(Path(temp))
            write_jsonl(
                root / "branch-results" / "a.sources.jsonl",
                [
                    {
                        "source_id": "S001",
                        "title": "原始文件",
                        "publisher": "发布者",
                        "url": "https://example.com/report?utm_source=a",
                        "read_level": "opened",
                        "categories": ["annual_reports"],
                        "branch_ids": ["a"],
                    }
                ],
            )
            write_jsonl(
                root / "branch-results" / "b.sources.jsonl",
                [
                    {
                        "source_id": "S002",
                        "title": "原始文件",
                        "publisher": "发布者",
                        "url": "https://example.com/report",
                        "read_level": "deep_read",
                        "categories": ["business_segments_and_commercialization"],
                        "branch_ids": ["b"],
                    }
                ],
            )
            subprocess.run(
                [sys.executable, str(MERGE), str(root)],
                check=True,
                capture_output=True,
                text=True,
            )
            merged = [
                json.loads(line)
                for line in (root / "source-register.jsonl")
                .read_text(encoding="utf-8")
                .splitlines()
                if line.strip()
            ]
            self.assertEqual(len(merged), 1)
            self.assertEqual(merged[0]["read_level"], "deep_read")
            self.assertEqual(
                set(merged[0]["categories"]),
                {"annual_reports", "business_segments_and_commercialization"},
            )


if __name__ == "__main__":
    unittest.main()
