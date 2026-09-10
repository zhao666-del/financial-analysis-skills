---
name: research-depth
description: 为基金、上市公司/股票和行业研究建立可审计的有效阅读与证据追踪流程。凡任务需要形成专业判断、比较、估值、准入结论或研究报告，无论是快速、标准、深度还是机构级模式，均在领域 Skill 动笔前使用；提供 Research Manifest、分级阅读预算、递归/并行研究、来源去重与独立性识别、Source Coverage Matrix、Claim-Evidence 映射、精准引用台账、停止条件和研究不足降级。
---

# 有效阅读与研究深度控制

先建立研究包，再检索、阅读和写作。资料篇数只用于预算控制；只有真正读过、去重后仍独立、能够支撑研究问题且留有定位记录的资料，才计入有效阅读量。

## 必须执行的流程

1. 读取 [研究执行协议](references/research-protocol.md) 和 [有效阅读门槛](references/effective-reading-gates.md)。
2. 选择研究类型 `company`、`industry` 或 `fund`，再选择 `quick`、`standard`、`deep` 或 `institutional`。
3. 运行：

   ```powershell
   python scripts/init_research.py <研究目录> --type company --subject "研究对象" --profile standard
   ```

4. 按自动生成的分支计划检索。可以并行执行互不依赖的分支；并行只改变速度，不降低阅读和证据要求。
5. 把来源登记为 `discovered → opened → skimmed → read → deep_read`。摘要、搜索结果页和模型转述最多只能标为 `skimmed`。
6. 记录实际阅读的章节、页码/表格、提取事实、适用口径、来源独立性和原始发布者。转载、镜像和同源改写不得重复计数。
7. 仅由覆盖缺口、证据冲突、未解决声明、替代解释或反方证据触发下一轮递归研究；不得为了达到篇数泛搜。
8. 为决定性结论建立 Claim-Evidence 映射。同步记录支持证据、反对证据、替代解释、置信度、缺失证据和失效条件。
9. 分支结束后运行：

   ```powershell
   python scripts/merge_branches.py <研究目录>
   python scripts/validate_research.py <研究目录> --strict
   ```

10. 读取 `validation-report.json` 后再交给领域 Skill。未达到门槛时继承降级标签和置信度上限，不得在写作阶段自行升级。
11. 进入任何聊天结论、简报或正式报告写作前，读取 [中性客观研究写作规范](references/neutral-research-writing.md)。正式草稿使用 `scripts/validate_neutral_language.py` 检查；硬性问题未修复时不得交付。

## 四档研究模式

| 模式 | 适用场景 | 原则 |
|---|---|---|
| `quick` | 快速判断、异动解释、初筛 | 最少覆盖身份/产品、最新事实、关键历史、独立交叉验证和反方证据 |
| `standard` | 常规分析、比较、简报 | 覆盖主要事实链、同业/替代品、重要历史和核心争议 |
| `deep` | 深度报告、完整估值、行业全景 | 完成主要研究分支、历史回溯、机制穿透和高精度引用 |
| `institutional` | 准入、投资委员会、额度审批 | 在 `deep` 基础上提高独立证据、审计、运营/治理和反方取证要求 |

即使用户只要求简短答案，也应使用 `quick`。只有纯粹读取单个确定性事实且不形成研究判断时，才可只调用数据 Skill。

## 有效阅读硬规则

- 同一原始信息只计一个有效来源；同一文件可覆盖多个主题，但只计一次总阅读量。
- `read` 必须记录阅读范围和证据摘要；`deep_read` 还必须覆盖所有与当前决定性问题相关的正文、表格和附注。
- 核心结论优先回到法定披露、监管/政府、原始数据、标准、论文、客户/供应商或产品原始文件。
- 公司或管理人自述属于一手来源，但不天然具有独立性；重要推断需要外部交叉验证。
- 决定性结论原则上需要两个独立证据组。法律事实可由单一权威原件支持，但必须注明 `single_source_authoritative`。
- 每个决定性判断必须主动寻找反方材料；找不到时记录检索范围和查询词，不得写成“没有反证”。
- 引用必须能定位到页码、章节、表格、公告编号或网页小标题。只有来源编号、没有定位信息，不算完整可追溯。
- 达到预算而关键覆盖仍不足时停止扩写，输出研究缺口、置信度上限和人工取证清单。

## 停止条件

只有同时满足以下条件才可结束研究：

- 必填覆盖项达到门槛或存在有依据的非适用豁免；
- 有效阅读量、深读量、一级/原始来源比例和独立来源比例达标；
- 决定性声明有支持证据、反方搜索和精准引用；
- 冲突已解决或并列披露；
- 连续一轮检索的决定性新增事实低于阈值；
- 数据时点、许可证和使用边界合规。

不得仅因达到篇数、时间或来源预算而标记完成。

## 研究包交付

至少保留：

- `research-manifest.json`
- `source-register.jsonl`
- `claim-evidence.jsonl`
- `citation-ledger.jsonl`
- `branch-results/`
- `validation-report.json`
- 正式报告任务另保留 `language-audit.json`

字段定义见 [研究包字段规范](references/schema-guide.md)。上游 Open Deep Research 与 GPT Researcher 的借鉴范围和许可证见 [上游项目说明](references/upstream-projects.md)。
