#!/usr/bin/env python3
"""Merge branch JSONL files and conservatively deduplicate research evidence."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit


TRACKING_KEYS = {"fbclid", "gclid", "mc_cid", "mc_eid"}
READ_RANK = {
    "discovered": 0,
    "opened": 1,
    "skimmed": 2,
    "read": 3,
    "deep_read": 4,
    # Backward compatibility with the first research-depth schema.
    "extracted": 3,
    "cited": 3,
}


def normalize_url(value: str) -> str:
    if not value:
        return ""
    parts = urlsplit(value.strip())
    query = [
        (key, val)
        for key, val in parse_qsl(parts.query, keep_blank_values=True)
        if not key.lower().startswith("utm_") and key.lower() not in TRACKING_KEYS
    ]
    path = parts.path.rstrip("/") or "/"
    return urlunsplit(
        (parts.scheme.lower(), parts.netloc.lower(), path, urlencode(query), "")
    )


def source_key(item: dict) -> str:
    for field in ("original_source_id", "document_id", "doi", "content_hash"):
        if item.get(field):
            return f"{field}:{str(item[field]).strip().lower()}"
    url = normalize_url(str(item.get("url", "")))
    if url:
        return f"url:{url}"
    raw = "|".join(
        str(item.get(key, "")).strip().lower()
        for key in ("publisher", "title", "published_date")
    )
    return "meta:" + hashlib.sha256(raw.encode("utf-8")).hexdigest()


def read_jsonl(path: Path):
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if line.strip():
            try:
                yield json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"{path}:{number}: {exc}") from exc


def merge_lists(existing: dict, incoming: dict, field: str) -> None:
    values = list(existing.get(field, []) or [])
    for value in incoming.get(field, []) or []:
        if value not in values:
            values.append(value)
    if values:
        existing[field] = values


def merge_text(existing: dict, incoming: dict, field: str) -> None:
    old = str(existing.get(field, "") or "").strip()
    new = str(incoming.get(field, "") or "").strip()
    if not old and new:
        existing[field] = new
    elif new and new not in old:
        existing[field] = f"{old} | {new}"


def merge_source(existing: dict, incoming: dict) -> None:
    for field in ("branch_ids", "categories", "sections_read"):
        merge_lists(existing, incoming, field)
    for field in ("notes", "evidence_summary"):
        merge_text(existing, incoming, field)
    for field in ("primary", "extracted", "cited"):
        existing[field] = bool(existing.get(field)) or bool(incoming.get(field))
    old_level = str(existing.get("read_level") or existing.get("status") or "discovered")
    new_level = str(incoming.get("read_level") or incoming.get("status") or "discovered")
    if READ_RANK.get(new_level, 0) > READ_RANK.get(old_level, 0):
        existing["read_level"] = "read" if new_level in {"extracted", "cited"} else new_level
    for field, value in incoming.items():
        if field not in existing or existing[field] in ("", None, [], {}):
            existing[field] = value
    old_independence = str(existing.get("independence", "") or "")
    new_independence = str(incoming.get("independence", "") or "")
    if old_independence and new_independence and old_independence != new_independence:
        existing["independence"] = "unknown"
        merge_text(existing, {"notes": "来源独立性标记冲突，需人工复核"}, "notes")


def merge_claim(existing: dict, incoming: dict) -> None:
    for field in (
        "supporting_source_ids",
        "opposing_source_ids",
        "supporting_independence_groups",
        "calculations",
        "alternative_explanations",
        "missing_evidence",
        "invalidation_conditions",
        "counter_search_scope",
    ):
        merge_lists(existing, incoming, field)
    for field, value in incoming.items():
        if field not in existing or existing[field] in ("", None, [], {}):
            existing[field] = value


def citation_key(item: dict) -> str:
    if item.get("citation_id"):
        return f"citation:{item['citation_id']}"
    raw = "|".join(str(item.get(k, "")) for k in ("claim_id", "source_id", "locator"))
    return "citation-meta:" + hashlib.sha256(raw.encode("utf-8")).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("research_dir", type=Path)
    args = parser.parse_args()
    root = args.research_dir.resolve()
    branch_root = root / "branch-results"
    groups = {
        "sources": ("source-register.jsonl", source_key, merge_source),
        "claims": (
            "claim-evidence.jsonl",
            lambda item: f"claim:{item.get('claim_id', '')}",
            merge_claim,
        ),
        "citations": ("citation-ledger.jsonl", citation_key, None),
    }
    summary: dict[str, int] = {}
    for stem, (output_name, key_fn, merge_fn) in groups.items():
        seen: dict[str, dict] = {}
        input_count = 0
        for path in sorted(branch_root.glob(f"*.{stem}.jsonl")):
            for item in read_jsonl(path):
                input_count += 1
                key = key_fn(item)
                if key not in seen:
                    seen[key] = item
                elif merge_fn is not None:
                    merge_fn(seen[key], item)
        output = root / output_name
        output.write_text(
            "".join(json.dumps(item, ensure_ascii=False) + "\n" for item in seen.values()),
            encoding="utf-8",
        )
        summary[stem] = len(seen)
        summary[f"{stem}_duplicates_removed"] = input_count - len(seen)
    (root / "merge-summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(summary, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
