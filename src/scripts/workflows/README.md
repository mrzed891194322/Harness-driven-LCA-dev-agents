# Workflows 编排实现

YAML 契约在 [`harness/LCA-*.yaml`](../../../harness/)。本目录是 Python 实现。

| 路径 | 职责 |
| --- | --- |
| `runtime/` | 通用内核：`RunContext`、capabilities、hashing、identifiers、local_files |
| `domains/lca/` | LCA 能力注册（checkers / hooks / knowledge 适配） |
| `orchestrator/` | LangGraph 主编排 CLI |
| `orchestrator/load/` | YAML 加载、模型、列表合并、resolve、TaskBundle |
| `orchestrator/loop/` | 状态机、session 绑定、prompt、handoff |
| `orchestrator/persist/` | checkpoint、manifest、runtime-config fingerprint |

入口：`orchestrator/main.py`。导入前缀：`scripts.workflows.*`。
