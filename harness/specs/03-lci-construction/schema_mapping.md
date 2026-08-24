# 03 LCI 制定 Schema 握手映射

本文是维护索引，不替代本阶段 spec 或公共运行契约。公共 handoff / stage / manifest 握手机制见 [`../public/references/handshake-common.md`](../public/references/handshake-common.md)。

> 当前仓库没有可定位的 LCI Flow、Process、Product System JSON schema，也没有规范所称的映射报告模板。本阶段只能按 spec 约束产物和追踪关系；维护者不得在映射中虚构模板路径。

## 握手流程

```mermaid
flowchart TD
    inputs["已通过计划 + 01 review<br/>02 检索 handoff"]
    request["LCI 制定请求 handoff"]
    executor["sub-executor"]
    lci["workspace/outputs/LCI<br/>Flow / Process / Product System"]
    mapping["human_readable_mapping.md"]
    returned["LCI 返回 handoff<br/>artifact 路径"]
    gate{"文件齐全且无阻断证据缺口"}
    next["04 LCI 质量评估"]
    stop["failed"]

    inputs --> request --> executor
    executor --> lci --> returned
    executor --> mapping --> returned
    returned --> gate
    gate -->|是| next
    gate -->|否| stop
```

## 契约与调用表（阶段特有）

| 类型 | 契约或产物 | 触发时机 | 生产者 → 消费者 | 校验与握手内容 | 失败/缺口处理 |
| --- | --- | --- | --- | --- | --- |
| 输入审查 | `review.schema.json`（public） | 进入阶段前 | 01 → 03 | 计划已通过；检索任务以 01 review 与 02 handoff 为准，不要求用户计划含 `GAP-*` 字面量 | review 非通过时不得进入 |
| 输入交接 | 02 handoff | 建立 LCI 前 | 02 → 03 | 查询、原文位置、UUID、选择理由、未解决项和输入 hashes | 阻断证据缺口停止 |
| LCI 产物 | `workspace/outputs/LCI/` | 执行 Agent 制定时 | `sub-executor` → 04/05 | `flows/`、`processes/`、`product_systems/` 一文件一实体；exchange 使用布尔 `isInput`，每个 Process 有且仅有一个 `isQuantitativeReference: true` 的输出 exchange，前景输入使用 `defaultProvider`；Product System 使用 auto-link、默认 Provider 和 `expectedProcessIds`；映射报告为 `human_readable_mapping.md` | 聚合容器、错误方向/定量参考字段、缺失或重复定量参考、缺失前景 Provider、explicit 拓扑、缺少实体类型或重复 UUID 均失败 |
| 确定性校验 | `references/scripts/validation.py` | 03 完成及每轮 04 审查前 | 执行 Agent / reviewer | 调用共享 `validate_lci_directory`，返回实体计数、hash、exchange 方向、唯一定量参考、Provider-Flow 一致性、auto-link 契约和错误 | `ok!=true` 不得进入预检 |

## 维护联动

- 后续若新增 LCI JSON schema 或映射模板，应放在本阶段 `references/` 下，并同步 04 审查、05 预检、MCP 导入校验、质量 rubric 和本映射。
- 规范 LCI 仍写入 `workspace/outputs/LCI/`；连续改进运行如需转换，只能把完整兼容副本放在 `workspace/tmp/` 的具体子目录。路径门禁变化必须同步 05/06、openLCA 规则和工具测试。
- 本阶段通过仅表示材料可审查，不表示质量审查通过或允许写入 openLCA。
