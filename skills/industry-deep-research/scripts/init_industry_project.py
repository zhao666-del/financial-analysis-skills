#!/usr/bin/env python3
"""Create a structured workspace for an industry research project."""

from __future__ import annotations

import argparse
import re
from pathlib import Path


def safe_name(value: str) -> str:
    name = re.sub(r"[\\/:*?\"<>|]+", "-", value).strip(" .-")
    return name or "industry-research"


def write_if_missing(path: Path, content: str) -> None:
    if not path.exists():
        path.write_text(content, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="初始化产业深度研究工作区")
    parser.add_argument("industry", help="行业、产业链或技术赛道名称")
    parser.add_argument("--root", default=".", help="工作区上级目录")
    parser.add_argument("--as-of", default="待填写", help="数据截止日")
    args = parser.parse_args()

    project = Path(args.root).expanduser().resolve() / safe_name(args.industry)
    for relative in (
        "sources/primary",
        "sources/secondary",
        "data/raw",
        "data/processed",
        "charts",
        "models",
        "drafts",
        "deliverables",
    ):
        (project / relative).mkdir(parents=True, exist_ok=True)

    write_if_missing(
        project / "research_brief.md",
        f"""# {args.industry}产业深度研究简报

## 基本信息

- 研究对象：{args.industry}
- 地域范围：待填写
- 数据截止日：{args.as_of}
- 历史区间：待填写
- 预测区间：待填写
- 最终交付物：待填写

## 核心决策问题

1. 待填写

## 待验证产业命题

1. 命题：
   - 支持证据：
   - 反对证据：
   - 反证阈值：
   - 跟踪指标：

## 产业边界

- 纳入：
- 排除：
- 替代品：
- 互补品：
- 统计口径：

## 全产业链起始骨架

- 采用的链条表示法：传统上中下游 / 价值交付链 / 研发审批商业化链 / 项目生命周期链 / 多边平台生态
- 上游或基础投入/使能层：
- 中游或价值创造/转化层：
- 下游或交付/渠道/运营层：
- 终端使用者、采购者和付费方：
- 售后、回收、退出或上市后管理：
- 关键横向能力：设备工具 / 软件数据 / 外包服务 / 许可标准 / 物流金融 / 其他
- 需要追踪的流：产品或服务 / 资金 / 数据 / 知识产权 / 责任风险
- 初步控制点和单点瓶颈：

## 数据缺口与调研计划

| 问题 | 所需数据 | 首选来源 | 备选来源 | 状态 |
|---|---|---|---|---|
|  |  |  |  | 待获取 |
""",
    )

    write_if_missing(
        project / "source_register.csv",
        "编号,标题,发布者,发布日期,数据截止日,链接或文件,来源级别,支撑命题,口径备注\n",
    )
    write_if_missing(
        project / "data_dictionary.csv",
        "变量,中文含义,单位,历史值,预测值,来源日期,来源,事实估算预测,区间,备注\n",
    )
    write_if_missing(
        project / "thesis_register.csv",
        "编号,命题,支持证据,反对证据,关键假设,反证阈值,跟踪指标,更新频率,置信度\n",
    )
    write_if_missing(
        project / "industry_chain.csv",
        "节点编号,层级或功能层,节点名称,核心功能,主要输入,主要输出,客户或付费方,定价与合同,收入确认与回款,关键成本与资产,有效供给约束,认证或交付时滞,控制点,周期变量,代表性公司,证据来源,未知与反证\n",
    )
    write_if_missing(
        project / "flow_register.csv",
        "流编号,流类型,起始节点,终止节点,流转对象,所有权或责任转移,定价或付款节点,关键风险,证据来源,备注\n",
    )
    write_if_missing(
        project / "company_role_matrix.csv",
        "公司,主角色,覆盖节点,纵向或横向能力,自营或外包,主要变现方式,核心控制点,主要瓶颈,可外推结论,不可外推事项,证据来源\n",
    )
    write_if_missing(
        project / "chain_risk_register.csv",
        "风险编号,触发事件,首个受影响节点,数量价格或交付变化,上游或下游传导,利润与现金流影响,可观察指标,失效阈值,证据来源\n",
    )
    write_if_missing(
        project / "models" / "scenario_table.csv",
        "变量,悲观,基准,乐观,证据与触发条件\n终端数量,,,,\n渗透率,,,,\n单机用量或价值,,,,\n有效供给,,,,\n平均价格,,,,\n行业利润,,,,\n",
    )

    print(f"已创建产业研究工作区：{project}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
