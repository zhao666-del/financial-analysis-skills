# Financial Analysis Skills

一套面向 Codex 的中文金融研究 Skills，覆盖研究证据管理、A 股/港股/美股数据采集、单一公司证券研究、基金尽调和产业深度研究。

本仓库强调三件事：

- 先取证、后判断，保留来源、日期、口径与定位信息；
- 明确区分披露事实、计算结果、研究假设和条件化判断；
- 对新业务按“送样 → 测试 → 认证 → 小批量 → 批量供货 → 多客户复购”描述商业化阶段。

## Skills 一览

| Skill | 作用 | 典型任务 |
|---|---|---|
| `research-depth` | 研究资料搜集、阅读预算、来源分级和证据台账 | 为公司、基金或行业报告建立可审计研究包 |
| `a-stock-data` | A 股行情、财务、公告、研报和交易结构数据采集 | 获取带来源与日期留痕的 A 股数据 |
| `global-stock-data` | 港股和美股行情、财务、监管文件、期权与机构持仓数据采集 | 获取海外市场与 SEC 等一手数据 |
| `stock-analysis-pro` | 单一公司的商业模式、财务、盈利预测和估值研究 | 上市公司深度报告、盈利拆分与估值 |
| `fund-research-analyst` | 中国公募基金和 ETF 的机构级研究与准入尽调 | 阿尔法归因、显著性、容量、同类比较与组合适配 |
| `industry-deep-research` | 从完整产业链出发研究行业系统 | 产业链、供需、技术路线、利润池、竞争和投资机会 |

## 组合关系

```text
research-depth                 研究流程与证据底座
├── stock-analysis-pro        单一公司研究
│   ├── a-stock-data          A 股数据
│   └── global-stock-data     港股/美股数据
├── fund-research-analyst     基金与 ETF 研究
└── industry-deep-research    行业与产业链研究
```

## 仓库结构

```text
skills/
├── a-stock-data/
├── global-stock-data/
├── stock-analysis-pro/
├── fund-research-analyst/
├── industry-deep-research/
└── research-depth/
```

每个 Skill 以 `SKILL.md` 为入口，并可包含：

- `agents/`：Codex 展示名称、简介和默认提示词；
- `references/`：研究方法、数据口径和报告蓝图；
- `scripts/`：初始化、计算和校验工具；
- `templates/`：可复用的研究包模板；
- `tests/`：确定性校验用例。

## 安装

先克隆仓库：

```bash
git clone https://github.com/zhao666-del/financial-analysis-skills.git
cd financial-analysis-skills
```

将需要的 Skill 目录复制到 Codex 的个人 Skills 目录。Windows 常见位置为：

```text
%USERPROFILE%\.codex\skills\
```

例如安装全部 Skills：

```powershell
$source = ".\skills"
$destination = Join-Path $env:USERPROFILE ".codex\skills"
Get-ChildItem -LiteralPath $source -Directory | ForEach-Object {
    Copy-Item -LiteralPath $_.FullName -Destination $destination -Recurse -Force
}
```

安装后重新加载 Codex。具体依赖和调用边界以各目录中的 `SKILL.md` 为准。

## 调用示例

```text
使用 $stock-analysis-pro 和 $a-stock-data，研究一家 A 股公司的商业模式、财务质量、盈利预测与估值。

使用 $fund-research-analyst，对目标基金完成同类池、风险收益、风格、容量与准入尽调。

使用 $industry-deep-research，先建立完整产业链，再分析供需、技术路线、利润池和竞争演化。
```

## 安全与数据说明

- 仓库不包含本机 `config.yaml`、Cookie、访问令牌或编译缓存；需要鉴权的数据源请使用环境变量或本地配置。
- 市场数据接口可能受频率限制、字段变化、地域网络和数据源授权约束，使用前应核对各 Skill 中的数据政策。
- 研究输出用于分析和学习，不构成收益承诺或个性化投资建议；重要结论应回到公告、监管文件、基金合同和财务报表原件复核。

## 许可证与归属

不同目录可能适用不同许可证。`stock-analysis-pro` 保留其目录内的 MIT License；`a-stock-data` 与 `global-stock-data` 保留各自的 Apache-2.0 许可证和上游归属说明。详见 [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md) 及各目录内文件。

除已明确标注许可证的内容外，本仓库未额外授予许可。
