# 上游项目借鉴与许可证

## Open Deep Research

- 仓库：`langchain-ai/open_deep_research`
- 审计版本：下载时的 `main` 分支快照
- 许可证：MIT
- 运行要求：Python 3.10+；核心依赖包括 LangGraph、LangChain、多模型适配、MCP、搜索服务和文档解析。
- 借鉴机制：结构化 research brief、Supervisor/Researcher 状态、并发研究单元、研究迭代与工具调用预算、笔记压缩、明确完成信号。

## GPT Researcher

- 仓库：`assafelovic/gpt-researcher`
- 审计版本：下载时的默认分支快照
- 许可证：Apache-2.0
- 运行要求：Python 3.10/3.11+，完整安装包含 LangChain/LangGraph、多个检索器、抓取器、文档处理、API 服务和可选前端。
- 借鉴机制：树状深度/广度研究、子问题并发、visited URL 去重、网页与本地资料合并、来源筛选、研究进度和引用聚合。

## 接入决定

第一阶段不复制上游源码，也不把其完整运行时设为必需依赖。共享 Skill 使用标准库脚本实现研究包、分支合并、去重和门槛验证；Codex 自身的搜索、浏览、连接器或领域数据 Skill 负责实际检索。

如未来需要独立运行上游：

```powershell
# Open Deep Research（建议独立虚拟环境）
uv sync

# GPT Researcher（建议独立虚拟环境）
python -m pip install -r requirements.txt
```

两者通常还需要模型与搜索服务密钥。不要把密钥写入 Skill、研究包、日志或示例配置。

若复制任何上游代码，必须保留对应版权和许可证文本。本 Skill 当前只复用思想与通用工作流结构，没有复制实质性源码。
