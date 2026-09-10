#!/usr/bin/env python3
"""Validate pinned external market-data skill snapshots."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "references" / "external-data" / "manifest.json"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> int:
    data = json.loads(MANIFEST.read_text(encoding="utf-8"))
    base = MANIFEST.parent
    failures: list[str] = []

    for source in data["sources"]:
        skill = base / source["skill_path"]
        license_file = base / source["license_path"]

        for path, expected, label in (
            (skill, source["skill_sha256"], "skill"),
            (license_file, source["license_sha256"], "license"),
        ):
            if not path.is_file():
                failures.append(f"{source['name']}: missing {label} file {path}")
                continue
            actual = sha256(path)
            if actual != expected:
                failures.append(
                    f"{source['name']}: {label} SHA-256 mismatch: {actual} != {expected}"
                )

        if skill.is_file():
            text = skill.read_text(encoding="utf-8")
            if not text.startswith("---") or f"name: {source['name']}" not in text[:2000]:
                failures.append(f"{source['name']}: invalid or unexpected SKILL.md frontmatter")
            if "```python" not in text:
                failures.append(f"{source['name']}: no Python reference blocks found")

    if failures:
        for failure in failures:
            print(f"ERROR: {failure}")
        return 1

    print(f"OK: validated {len(data['sources'])} pinned external data skills")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
