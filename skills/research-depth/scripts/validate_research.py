#!/usr/bin/env python3
"""Validate effective reading, evidence, citations, and downgrade rules."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit


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
PROFILE_LABELS = {
    "quick": "快速公开资料研究",
    "standard": "标准公开资料研究",
    "deep": "公开资料深度研究",
    "institutional": "机构级公开资料研究（非完整尽调）",
}
PROFILE_CONFIDENCE = {
    "quick": "中",
    "standard": "中",
    "deep": "中高",
    "institutional": "中高",
}


def read_jsonl(path: Path) -> list[dict]:
    records = []
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            records.append(json.loads(line))
        except json.JSONDecodeError as exc:
            raise ValueError(f"{path}:{number}: {exc}") from exc
    return records


def list_value(value) -> list:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, str):
        return [value] if value.strip() else []
    return [value]


def read_level(source: dict) -> str:
    value = str(source.get("read_level") or source.get("status") or "discovered")
    return "read" if value in {"extracted", "cited"} else value


def normalized_url(value: str) -> str:
    if not value:
        return ""
    parts = urlsplit(value.strip())
    return urlunsplit(
        (parts.scheme.lower(), parts.netloc.lower(), parts.path.rstrip("/") or "/", "", "")
    )


def dedup_key(source: dict) -> str:
    for field in ("original_source_id", "document_id", "doi", "content_hash"):
        if source.get(field):
            return f"{field}:{str(source[field]).strip().lower()}"
    url = normalized_url(str(source.get("url", "")))
    if url:
        return f"url:{url}"
    raw = "|".join(
        str(source.get(field, "")).strip().lower()
        for field in ("publisher", "title", "published_date")
    )
    return "meta:" + hashlib.sha256(raw.encode("utf-8")).hexdigest()


def source_categories(source: dict) -> set[str]:
    categories = {str(item) for item in list_value(source.get("categories")) if item}
    if source.get("category"):
        categories.add(str(source["category"]))
    return categories


def is_effective_read(source: dict, citation_sources_with_locator: set[str]) -> bool:
    level_ok = READ_RANK.get(read_level(source), 0) >= READ_RANK["read"]
    location_ok = bool(
        list_value(source.get("sections_read"))
        or source.get("locator")
        or source.get("source_id") in citation_sources_with_locator
    )
    evidence_ok = bool(str(source.get("evidence_summary") or source.get("notes") or "").strip())
    identity_ok = bool(
        source.get("url")
        or source.get("local_path")
        or source.get("document_id")
        or source.get("content_hash")
    )
    return level_ok and location_ok and evidence_ok and identity_ok


def ratio(numerator: int, denominator: int) -> float:
    return numerator / denominator if denominator else 0.0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("research_dir", type=Path)
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args()
    root = args.research_dir.resolve()
    manifest_path = root / "research-manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    sources = read_jsonl(root / "source-register.jsonl")
    claims = read_jsonl(root / "claim-evidence.jsonl")
    citations = read_jsonl(root / "citation-ledger.jsonl")

    errors: list[str] = []
    warnings: list[str] = []
    gaps: list[str] = []

    source_ids = {source.get("source_id") for source in sources if source.get("source_id")}
    source_by_id = {
        source.get("source_id"): source for source in sources if source.get("source_id")
    }
    claim_ids = {claim.get("claim_id") for claim in claims if claim.get("claim_id")}
    cited_source_ids = {citation.get("source_id") for citation in citations}
    citation_claim_ids = {citation.get("claim_id") for citation in citations}
    citation_sources_with_locator = {
        citation.get("source_id")
        for citation in citations
        if str(citation.get("locator") or "").strip()
    }

    unique_sources: dict[str, dict] = {}
    for source in sources:
        unique_sources.setdefault(dedup_key(source), source)
    duplicate_count = len(sources) - len(unique_sources)
    effective_sources = [
        source
        for source in unique_sources.values()
        if is_effective_read(source, citation_sources_with_locator)
    ]
    deep_sources = [
        source for source in effective_sources if read_level(source) == "deep_read"
    ]
    opened_or_skimmed = [
        source
        for source in unique_sources.values()
        if READ_RANK.get(read_level(source), 0) in {1, 2}
    ]
    primary_count = sum(bool(source.get("primary")) for source in effective_sources)
    independent_count = sum(
        str(source.get("independence") or "") == "independent"
        for source in effective_sources
    )
    primary_ratio = ratio(primary_count, len(effective_sources))
    independent_ratio = ratio(independent_count, len(effective_sources))
    locator_count = sum(bool(str(citation.get("locator") or "").strip()) for citation in citations)
    locator_ratio = ratio(locator_count, len(citations))

    for row in manifest.get("coverage_matrix", []):
        if row.get("applicable") is False:
            if str(row.get("waiver_reason") or "").strip():
                row["coverage_status"] = "waived"
                warnings.append(f"coverage waived: {row['category']}")
                continue
            row["coverage_status"] = "missing"
            gaps.append(row["category"])
            errors.append(f"coverage marked not applicable without waiver: {row['category']}")
            continue
        category_sources = [
            source for source in effective_sources if row["category"] in source_categories(source)
        ]
        category_deep = [
            source for source in category_sources if read_level(source) == "deep_read"
        ]
        category_primary = sum(bool(source.get("primary")) for source in category_sources)
        category_independent = sum(
            str(source.get("independence") or "") == "independent"
            for source in category_sources
        )
        category_primary_ratio = ratio(category_primary, len(category_sources))
        category_independent_ratio = ratio(category_independent, len(category_sources))
        row["effective_read_count"] = len(category_sources)
        row["deep_read_count"] = len(category_deep)
        row["primary_effective_count"] = category_primary
        row["independent_effective_count"] = category_independent
        row["primary_ratio"] = round(category_primary_ratio, 4)
        row["independent_ratio"] = round(category_independent_ratio, 4)
        complete = (
            len(category_sources) >= int(row.get("minimum_effective_read", 0))
            and len(category_deep) >= int(row.get("minimum_deep_read", 0))
            and category_primary_ratio >= float(row.get("minimum_primary_ratio", 0))
            and category_independent_ratio
            >= float(row.get("minimum_independent_ratio", 0))
        )
        row["coverage_status"] = "complete" if complete else "missing"
        if row.get("required") and not complete:
            gaps.append(row["category"])

    bad_source_refs = sorted(source_id for source_id in cited_source_ids if source_id not in source_ids)
    bad_claim_refs = sorted(claim_id for claim_id in citation_claim_ids if claim_id not in claim_ids)
    if bad_source_refs:
        errors.append(f"citations reference unknown sources: {bad_source_refs}")
    if bad_claim_refs:
        errors.append(f"citations reference unknown claims: {bad_claim_refs}")

    material_claims = [
        claim for claim in claims if str(claim.get("materiality") or "") == "decisive"
    ]
    unsupported: list[str] = []
    weak_independence: list[str] = []
    no_counter_search: list[str] = []
    untraceable_claims: list[str] = []
    for claim in material_claims:
        claim_id = str(claim.get("claim_id") or "")
        supports = list_value(claim.get("supporting_source_ids"))
        if not supports:
            unsupported.append(claim_id)
        support_groups = set(list_value(claim.get("supporting_independence_groups")))
        for source_id in supports:
            source = source_by_id.get(source_id, {})
            group = (
                source.get("independence_group")
                or source.get("original_source_id")
                or source_id
            )
            if group:
                support_groups.add(str(group))
        if (
            supports
            and len(support_groups) < 2
            and not bool(claim.get("single_source_authoritative"))
        ):
            weak_independence.append(claim_id)
        if not list_value(claim.get("opposing_source_ids")) and not list_value(
            claim.get("counter_search_scope")
        ):
            no_counter_search.append(claim_id)
        claim_citations = [
            citation
            for citation in citations
            if str(citation.get("claim_id") or "") == claim_id
            and str(citation.get("locator") or "").strip()
        ]
        if not claim_citations:
            untraceable_claims.append(claim_id)

    if unsupported:
        errors.append(f"decisive claims without support: {unsupported}")
    if weak_independence:
        errors.append(
            "decisive claims without two independent evidence groups or authoritative "
            f"single-source justification: {weak_independence}"
        )
    if no_counter_search:
        errors.append(f"decisive claims without counterevidence search: {no_counter_search}")
    if untraceable_claims:
        errors.append(f"decisive claims without pinpoint citations: {untraceable_claims}")

    thresholds = manifest.get("reading_thresholds", {})
    effective_reading_complete = (
        len(effective_sources) >= int(thresholds.get("minimum_effective_read", 0))
        and len(deep_sources) >= int(thresholds.get("minimum_deep_read", 0))
    )
    source_quality_complete = (
        primary_ratio >= float(thresholds.get("minimum_primary_ratio", 0))
        and independent_ratio >= float(thresholds.get("minimum_independent_ratio", 0))
        and locator_ratio >= float(thresholds.get("minimum_locator_ratio", 0))
    )
    if not effective_reading_complete:
        gaps.append("effective_reading_threshold")
    if primary_ratio < float(thresholds.get("minimum_primary_ratio", 0)):
        gaps.append("primary_source_ratio")
    if independent_ratio < float(thresholds.get("minimum_independent_ratio", 0)):
        gaps.append("independent_source_ratio")
    if locator_ratio < float(thresholds.get("minimum_locator_ratio", 0)):
        gaps.append("citation_locator_ratio")

    unresolved_conflicts = [
        conflict
        for conflict in manifest.get("contradictions", [])
        if str(conflict.get("status") if isinstance(conflict, dict) else "") not in {
            "resolved",
            "disclosed",
        }
    ]
    rounds = manifest.get("research_rounds", [])
    last_round = rounds[-1] if rounds else {}
    marginal_information_gain_low = bool(rounds) and int(
        last_round.get("new_decisive_facts", 999)
    ) <= 1 and int(last_round.get("new_contradictions", 999)) <= 0

    stops = manifest.setdefault("stop_conditions", {})
    stops["required_coverage_complete"] = not gaps or all(
        row.get("coverage_status") in {"complete", "waived"}
        for row in manifest.get("coverage_matrix", [])
    )
    stops["effective_reading_complete"] = effective_reading_complete
    stops["source_quality_complete"] = source_quality_complete
    stops["material_claims_supported"] = (
        bool(material_claims) and not unsupported and not weak_independence
    )
    stops["counterevidence_searched"] = bool(material_claims) and not no_counter_search
    stops["conflicts_resolved_or_disclosed"] = not unresolved_conflicts
    stops["citation_traceable"] = (
        bool(citations)
        and not bad_source_refs
        and not bad_claim_refs
        and not untraceable_claims
        and locator_ratio >= float(thresholds.get("minimum_locator_ratio", 0))
    )
    stops["marginal_information_gain_low"] = marginal_information_gain_low

    if len(effective_sources) > int(manifest.get("source_budget", 0)):
        warnings.append("effective reads exceed configured source budget")
    if duplicate_count:
        warnings.append(f"duplicate source records found: {duplicate_count}")
    if not rounds:
        warnings.append("research rounds not recorded; saturation cannot be verified")

    all_stops_complete = all(bool(value) for value in stops.values())
    blocked = bool(str(manifest.get("blocked_reason") or "").strip())
    complete = all_stops_complete and not errors and not blocked
    profile = str(manifest.get("depth_profile") or "standard")
    if blocked:
        status = "blocked"
        report_label = "研究受阻"
        confidence_cap = "低"
    elif complete:
        status = "evidence_complete"
        report_label = PROFILE_LABELS.get(profile, "公开资料研究")
        confidence_cap = PROFILE_CONFIDENCE.get(profile, "中")
    else:
        status = "degraded"
        report_label = "资料覆盖不足的研究草案"
        confidence_cap = "中低" if effective_sources else "低"

    statistics = {
        "sources_discovered": len(sources),
        "unique_sources": len(unique_sources),
        "sources_opened_or_skimmed": len(opened_or_skimmed),
        "effective_read_count": len(effective_sources),
        "deep_read_count": len(deep_sources),
        "sources_cited": len({item for item in cited_source_ids if item}),
        "duplicate_sources": duplicate_count,
        "primary_effective_count": primary_count,
        "independent_effective_count": independent_count,
        "primary_ratio": round(primary_ratio, 4),
        "independent_ratio": round(independent_ratio, 4),
        "locator_completeness": round(locator_ratio, 4),
        "decisive_claims": len(material_claims),
        "decisive_claims_supported": len(material_claims) - len(unsupported),
        "decisive_claims_with_counter_search": len(material_claims)
        - len(no_counter_search),
    }
    unique_gaps = sorted(set(gaps))
    manifest["coverage_gaps"] = unique_gaps
    manifest["statistics"] = statistics
    manifest["status"] = status
    manifest["report_label"] = report_label
    manifest["confidence_cap"] = confidence_cap
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    report = {
        "valid": complete,
        "status": status,
        "report_label": report_label,
        "confidence_cap": confidence_cap,
        "errors": errors,
        "warnings": warnings,
        "coverage_gaps": unique_gaps,
        "stop_conditions": stops,
        "statistics": statistics,
        "coverage_matrix": manifest.get("coverage_matrix", []),
        "manual_evidence_needed": manifest.get("coverage_gaps", []),
    }
    (root / "validation-report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 1 if args.strict and not complete else 0


if __name__ == "__main__":
    raise SystemExit(main())
