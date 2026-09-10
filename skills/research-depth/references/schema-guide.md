# 研究包字段规范

## Research Manifest

关键字段：

- `research_id`、`research_type`、`subject`、`as_of_date`
- `depth_profile`、`max_depth`、`max_parallel_branches`
- `source_budget`、`iteration_budget`
- `reading_thresholds`
- `status`、`report_label`、`confidence_cap`
- `coverage_matrix`
- `branches`
- `research_rounds`
- `coverage_gaps`、`contradictions`
- `stop_conditions`
- `statistics`

## 来源台账

每行 JSON 至少包含：

`source_id, title, publisher, published_date, effective_date, url, local_path, document_id, source_type, source_tier, primary, independence, independence_group, original_source_id, content_hash, read_level, sections_read, evidence_summary, extracted, cited, categories, branch_ids, notes`

规则：

- `read_level` 使用 `discovered/opened/skimmed/read/deep_read`；
- `sections_read` 写页码、章节或表格范围；
- `evidence_summary` 写与研究问题相关的事实，不粘贴整篇摘要；
- `categories` 可以包含多个覆盖类别；
- `independence_group` 用于识别同源转载和同一数据链；
- `extracted`、`cited` 为布尔值，不替代阅读层级。

## Claim-Evidence

每行 JSON 至少包含：

`claim_id, claim, claim_type, materiality, status, supporting_source_ids, opposing_source_ids, supporting_independence_groups, calculations, alternative_explanations, confidence, evidence_quality, missing_evidence, invalidation_conditions, counter_search_scope, single_source_authoritative`

`claim_type` 使用 `fact/calculation/inference/forecast/judgment`。

## 引用台账

每行 JSON 至少包含：

`citation_id, claim_id, source_id, locator, excerpt_summary, accessed_at`

`locator` 必须尽量记录页码、章节、表格、公告编号或网页标题，不使用模糊的“见年报”。正文中的来源编号必须能回到本台账。

## 研究轮次

`research_rounds` 每项至少包含：

`round, new_sources_read, new_decisive_facts, new_contradictions, claims_upgraded, claims_downgraded, new_queries_triggered`

最后一轮只有在必填覆盖已经完成、`new_decisive_facts <= 1` 且没有新增未解决冲突时，才能视为边际信息增益低。
