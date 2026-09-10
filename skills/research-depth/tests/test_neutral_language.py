from __future__ import annotations

import importlib.util
import tempfile
import unittest
import zipfile
from pathlib import Path


SKILL_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = SKILL_ROOT / "scripts" / "validate_neutral_language.py"
SPEC = importlib.util.spec_from_file_location("neutral_language", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class NeutralLanguageTests(unittest.TestCase):
    def test_neutral_conditional_paragraph_passes(self) -> None:
        result = MODULE.audit_text(
            "截至2026年6月，收入同比增长31%。在毛利率维持22%的基准情景下，"
            "估值位于可比公司区间下沿；若毛利率低于18%，需重新评估。"
        )
        self.assertEqual(result["status"], "pass")
        self.assertEqual(result["error_count"], 0)

    def test_first_person_and_promotional_language_fail(self) -> None:
        result = MODULE.audit_text("我们认为这是黄金赛道，股价一定会上涨。")
        self.assertEqual(result["status"], "fail")
        self.assertGreaterEqual(result["error_count"], 3)

    def test_attributed_quotation_is_not_treated_as_report_voice(self) -> None:
        result = MODULE.audit_text(
            "公司在发布材料中称“这是黄金赛道”。当前未取得独立订单证据。"
        )
        self.assertEqual(result["status"], "pass")

    def test_soft_modifier_requires_review(self) -> None:
        result = MODULE.audit_text("公司收入大幅增长，行业空间巨大。")
        self.assertEqual(result["status"], "review")
        self.assertEqual(result["warning_count"], 2)

    def test_docx_text_extraction(self) -> None:
        document_xml = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:body><w:p><w:r><w:t>我认为该标的必买</w:t></w:r></w:p></w:body>
</w:document>"""
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "draft.docx"
            with zipfile.ZipFile(path, "w") as archive:
                archive.writestr("word/document.xml", document_xml)
            result = MODULE.audit_text(MODULE.read_report(path))
        self.assertEqual(result["status"], "fail")
        self.assertEqual(result["error_count"], 2)


if __name__ == "__main__":
    unittest.main()
