# Benchmark 运行记录模板

> 复制本文件用于一次运行。未知字段填 `unresolved` 或 `not_applicable: {理由}`，不得留空后仍将运行晋升为有效基线。

## 1. 运行标识

| 字段 | 值 |
| :--- | :--- |
| Run ID | `{YYYYMMDD-HHMM-case-commit}` |
| 案例与版本 | `{case_name@version}` |
| 开始时间/时区 | `{ISO 8601}` |
| 结束时间/时区 | `{ISO 8601}` |
| 总耗时 | `{seconds}` |
| 执行人/Agent | `{name}` |
| 复审人 | `{name/unresolved}` |
| 结论状态 | `{pass/conditional_pass/fail/needs_human_review}` |
| 状态理由 | `{一句话摘要}` |

## 2. 代码、模型与提示词

| 字段 | 值 |
| :--- | :--- |
| Repository | `{repository}` |
| Git commit | `{full SHA}` |
| Branch | `{branch}` |
| Worktree 状态 | `{clean/dirty；附变更清单}` |
| Agent/skill/spec 版本 | `{paths + hashes/commits}` |
| 模型提供方 | `{provider}` |
| 模型名称与版本 | `{model}` |
| 推理参数 | `{temperature/seed/reasoning/etc.}` |
| 系统/开发指令标识 | `{version/hash}` |
| 用户任务/提示词路径 | `{path}` |
| 完整提示词 SHA-256 | `{hash}` |
| 上下文或附件清单 | `{paths/IDs}` |
| 自动重试次数 | `{count}` |

若完整提示词含敏感信息，保存到受控位置，并在此仅记录权限可用的路径、脱敏说明和哈希。

## 3. RAG 与来源环境

| Library | 状态 | Build ID | Embedding model | 查询/命中记录路径 |
| :--- | :--- | :--- | :--- | :--- |
| `standards` | `{complete/...}` | `{id}` | `{model}` | `{path}` |
| `openlca_manual` | `{complete/...}` | `{id}` | `{model}` | `{path}` |
| `input` | `{complete/empty/...}` | `{id}` | `{model}` | `{path}` |
| `data` | `{complete/empty/...}` | `{id}` | `{model}` | `{path}` |

| 字段 | 值 |
| :--- | :--- |
| Evidence manifest 路径 | `{path}` |
| 关键事实总数/有证据数 | `{n/n}` |
| 冲突来源 | `{none/list}` |
| 来源人工裁决 | `{none/list + reviewer}` |

## 4. openLCA 环境

| 字段 | 值 |
| :--- | :--- |
| openLCA 版本 | `{version}` |
| IPC endpoint 标识 | `{受控 endpoint；不要记录密钥}` |
| IPC 健康检查 | `{timestamp + result}` |
| 活动数据库 | `{name}` |
| 数据库版本 | `{e.g. ecoinvent 3.11}` |
| System model | `{e.g. Cutoff, S}` |
| 数据库内容/hash/导出标识 | `{id/hash}` |
| LCIA 方法 | `{exact name}` |
| LCIA 方法 UUID | `{UUID}` |
| 分配设置 | `{setting}` |
| 区域化 | `{on/off + setting}` |
| 参数覆盖 | `{none/list}` |
| 成本计算 | `{on/off}` |

### 4.1 Provider manifest

| 用途/交换 | 情景 | 完整 Provider 名称 | UUID | 地域 | 参考产品/流 | System model | 查询时间 | 选择证据 |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `{PET}` | `{Case 1}` | `{name}` | `{uuid}` | `{RER}` | `{flow}` | `{model}` | `{time}` | `{path/decision}` |
| `{...}` | `{...}` | `{...}` | `{...}` | `{...}` | `{...}` | `{...}` | `{...}` | `{...}` |

记录所有候选的原始查询输出路径。同名候选的消歧证据不得只写“名称匹配”。

## 5. 输入、输出与哈希

| 产物 | 路径/标识 | SHA-256 | 大小/记录数 | 备注 |
| :--- | :--- | :--- | ---: | :--- |
| 用户输入快照 | `{path}` | `{hash}` | `{value}` | `{note}` |
| Execution plan | `{path}` | `{hash}` | `{value}` | `{note}` |
| LCI flows | `{path/manifest}` | `{hash}` | `{count}` | `{note}` |
| LCI processes | `{path/manifest}` | `{hash}` | `{count}` | `{note}` |
| Product Systems | `{path/manifest}` | `{hash}` | `{count}` | `{note}` |
| 映射报告 | `{path}` | `{hash}` | `{value}` | `{note}` |
| Provider 查询输出 | `{path}` | `{hash}` | `{count}` | `{note}` |
| 导入报告 | `{path}` | `{hash}` | `{value}` | `{note}` |
| 模型图 | `{path/manifest}` | `{hash}` | `{nodes/edges}` | `{note}` |
| LCIA 原始结果 | `{path/manifest}` | `{hash}` | `{categories}` | `{note}` |
| 最终报告 | `{path}` | `{hash}` | `{value}` | `{note}` |
| 日志/轨迹 | `{path}` | `{hash}` | `{value}` | `{note}` |

## 6. 分阶段运行记录

每阶段状态使用 `not_started`、`running`、`pass`、`conditional_pass`、`fail` 或 `needs_human_review`。

### 6.1 计划

| 检查 | 状态 | 证据 | 耗时 | 备注 |
| :--- | :--- | :--- | ---: | :--- |
| 目标、用途、受众和公开比较状态 | `{status}` | `{path}` | `{s}` | `{note}` |
| 功能单位、参考流、边界和排除项 | `{status}` | `{path}` | `{s}` | `{note}` |
| 数据、LCIA、解释和审核计划 | `{status}` | `{path}` | `{s}` | `{note}` |
| 事实/推断/代理/unresolved 分类 | `{status}` | `{path}` | `{s}` | `{note}` |

### 6.2 LCI

| 检查 | 状态 | 证据 | 耗时 | 备注 |
| :--- | :--- | :--- | ---: | :--- |
| 结构/schema | `{status}` | `{path}` | `{s}` | `{note}` |
| 单位、数量级和换算 | `{status}` | `{path}` | `{s}` | `{note}` |
| 质量/能量平衡 | `{status}` | `{path}` | `{s}` | `{note}` |
| 交换方向、参考流和 ID | `{status}` | `{path}` | `{s}` | `{note}` |
| Provider 查询与消歧 | `{status}` | `{path}` | `{s}` | `{note}` |

### 6.3 导入

| 实体 | 计划数 | 成功 | 失败 | 重复/复用 | 导入后验证 | 证据 |
| :--- | ---: | ---: | ---: | ---: | :--- | :--- |
| Flow | `{n}` | `{n}` | `{n}` | `{n}` | `{status}` | `{path}` |
| Process | `{n}` | `{n}` | `{n}` | `{n}` | `{status}` | `{path}` |
| Product System | `{n}` | `{n}` | `{n}` | `{n}` | `{status}` | `{path}` |

写入范围：`{category/project/names}`

回滚/清理策略：`{strategy}`

是否发生人工 GUI 修改：`{no/yes；见第 9 节}`

### 6.4 模型图

| Product System | 节点数 | 边数 | 预期连接 | 孤立输入 | 错误 Provider | 状态 | 证据 |
| :--- | ---: | ---: | :--- | :--- | :--- | :--- | :--- |
| `{name}` | `{n}` | `{n}` | `{n/n}` | `{n}` | `{n}` | `{status}` | `{path}` |

### 6.5 LCIA

| Product System | 参考流/数量 | 方法 | 类别数 | 结果非空 | 计算耗时 | 状态 | 证据 |
| :--- | :--- | :--- | ---: | :--- | ---: | :--- | :--- |
| `{name}` | `{flow + amount}` | `{method}` | `{n}` | `{yes/no}` | `{s}` | `{status}` | `{path}` |

资源释放/计算句柄处置：`{status + evidence}`

### 6.6 解释

| 检查 | 状态 | 证据 | 主要发现 |
| :--- | :--- | :--- | :--- |
| 重大问题/热点 | `{status}` | `{path}` | `{finding}` |
| 完整性 | `{status}` | `{path}` | `{finding}` |
| 敏感性 | `{status}` | `{path}` | `{finding}` |
| 一致性 | `{status}` | `{path}` | `{finding}` |
| 不确定性/数据质量 | `{status}` | `{path}` | `{finding}` |
| 结论与限制 | `{status}` | `{path}` | `{finding}` |

### 6.7 ISO 门禁与人工审核

| 门禁/维度 | 适用性 | 证据等级 0–3 | 硬门禁状态 | 证据 | 审核人/日期 |
| :--- | :--- | ---: | :--- | :--- | :--- |
| `{goal_and_scope}` | `{yes/no + reason}` | `{0}` | `{status}` | `{path}` | `{review}` |
| `{...}` | `{...}` | `{...}` | `{...}` | `{...}` | `{...}` |

完整矩阵路径：`{path}`

## 7. 数值基线差异

基线标识：`{baseline run ID/none}`

比较前提是否相同：`{database/system model/providers/method/reference flow/settings}`

| 情景 | 影响类别 | 单位 | 基线值 | 本次值 | 绝对差 | 相对差 | 容差 | 判定 | 解释 |
| :--- | :--- | :--- | ---: | ---: | ---: | ---: | :--- | :--- | :--- |
| `{Case}` | `{category}` | `{unit}` | `{value}` | `{value}` | `{value}` | `{%}` | `{rule}` | `{pass/fail/review}` | `{reason}` |

不得在数据库、Provider、方法或参考流不一致时仅用相对误差判定回归。先标记环境不等价，再决定是否可比较。

## 8. 失败与根因

| Failure ID | 最早阶段 | 表面症状 | 分类 | 根因 | 影响范围 | 修复/处置 | 回归案例 |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `{F-001}` | `{stage}` | `{symptom}` | `{taxonomy}` | `{root cause}` | `{scope}` | `{action}` | `{id/path}` |

失败分类建议使用 `input_or_scope`、`evidence`、`case_fact`、`entity_mapping`、`schema_or_reference`、`import`、`graph_connection`、`calculation`、`interpretation` 或 `review_required`。

## 9. 人工修改与决策

| ID | 时间 | 操作者 | 修改/决定 | 原因 | 影响的输入/输出 | 修改前后哈希 | 是否可自动复现 |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `{H-001}` | `{time}` | `{name}` | `{change}` | `{reason}` | `{scope}` | `{before/after}` | `{yes/no}` |

未经记录的人工 GUI 修改使本次运行不能晋升为可复现基线。

## 10. 基线晋升决定

| 问题 | 结论 |
| :--- | :--- |
| 适用硬性门禁是否全部通过 | `{yes/no}` |
| 是否有未解决的重要限制 | `{yes/no + list}` |
| 是否需要独立 LCA 专家/评审小组 | `{yes/no + status}` |
| 所有输入、环境和输出是否已哈希 | `{yes/no}` |
| 与旧基线的差异是否全部解释 | `{yes/no/not_applicable}` |
| 是否建议晋升为新基线 | `{yes/no/conditional}` |
| 建议适用范围 | `{exact environment and purpose}` |
| 复审人 | `{name}` |
| 复审日期 | `{date}` |
| 复审意见/签名记录 | `{path/text}` |

## 11. 最终结论

**状态**：`{pass | conditional_pass | fail | needs_human_review}`

**依据**：`{概述硬门禁、工程证据、数值差异和人工审核}`

**限制与后续行动**：`{负责人、截止/复审条件、阻止的用途}`
