"""Smoke tests for institutional fund diagnostics and research gates."""

from __future__ import annotations

import json
import math
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np
import pandas as pd


SKILL_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL_ROOT / "scripts"))

from capacity_stress import analyze as analyze_capacity  # noqa: E402
from institutional_diagnostics import analyze as analyze_diagnostics  # noqa: E402
from validate_research_package import validate  # noqa: E402


class InstitutionalToolsTest(unittest.TestCase):
    def test_diagnostics_detects_positive_active_nav(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "nav.csv"
            dates = pd.bdate_range("2018-01-01", periods=1600)
            benchmark_returns = 0.0002 + 0.008 * np.sin(np.arange(len(dates)) / 19)
            fund_returns = benchmark_returns + 0.00008
            frame = pd.DataFrame(
                {
                    "date": dates,
                    "nav": np.cumprod(1 + fund_returns),
                    "benchmark": np.cumprod(1 + benchmark_returns),
                }
            )
            frame.to_csv(path, index=False, encoding="utf-8-sig")
            result = analyze_diagnostics(path, 0.02, 100, 10, 7, 5)
            self.assertGreater(result["active_performance"]["active_nav_end"], 1.0)
            self.assertTrue(result["alpha_significance"]["available"])
            self.assertIn("rolling_36m_arithmetic_excess", result["rolling"])

    def test_capacity_stress_reports_untradeable_weight(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "holdings.csv"
            pd.DataFrame(
                [
                    {
                        "asset_code": "A",
                        "market_value": 60,
                        "adv20": 30,
                        "volatility_daily": 0.02,
                        "restricted": False,
                    },
                    {
                        "asset_code": "B",
                        "market_value": 40,
                        "adv20": 10,
                        "volatility_daily": 0.03,
                        "restricted": True,
                    },
                ]
            ).to_csv(path, index=False, encoding="utf-8-sig")
            result = analyze_capacity(path, [0.1, 0.2], [0.05, 0.1, 0.2], 0.5)
            self.assertTrue(math.isclose(result["untradeable_weight"], 0.4))
            self.assertIn("10%", result["liquidity"])

    def test_hard_veto_caps_rating(self) -> None:
        package = {
            "source_coverage": {},
            "alpha_attribution": {"major_alpha_sources_distinguished": False},
            "due_diligence": {},
            "capacity": {"quantified": False},
            "peer_universe": {},
            "red_team": {},
            "claims": [],
        }
        result = validate(package)
        self.assertEqual(result["rating_ceiling"], "观察")
        self.assertEqual(len(result["hard_vetoes"]), 3)

    def test_complete_package_passes(self) -> None:
        package = {
            "source_coverage": {
                "annual_reports": 3,
                "quarterly_reports": 8,
                "legal_documents": 3,
                "independent_method_sources": 8,
                "fund_contract_current": True,
                "benchmark_method_current": True,
            },
            "alpha_attribution": {"major_alpha_sources_distinguished": True},
            "due_diligence": {
                "team_governance_assessed": True,
                "model_or_process_governance_assessed": True,
            },
            "capacity": {"quantified": True},
            "peer_universe": {
                "share_classes_deduplicated": True,
                "same_end_date_and_return_basis": True,
                "passive_alternatives_included": True,
                "dead_or_transformed_funds_considered": True,
            },
            "red_team": {
                "completed": True,
                "strongest_rejection_arguments": ["a", "b", "c"],
                "responses": ["r"],
            },
            "claims": [
                {
                    "claim_id": "c1",
                    "question": "q",
                    "claim": "c",
                    "evidence_for": ["e1"],
                    "evidence_against": ["e2"],
                    "confidence": "中",
                }
            ],
        }
        result = validate(json.loads(json.dumps(package)))
        self.assertTrue(result["can_label_complete_due_diligence"])


if __name__ == "__main__":
    unittest.main()
