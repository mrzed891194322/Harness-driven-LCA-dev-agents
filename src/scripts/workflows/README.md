# Workflows 编排实现

YAML 契约在 [`harness/LCA-*.yaml`](../../../harness/)。本目录是 Python 实现。

| 路径 | 职责 |
| --- | --- |
| `runtime/` | 通用内核：`RunContext`、capabilities、hashing、identifiers、local_files |
| `domains/lca/` | LCA 能力注册（checkers / hooks / knowledge 适配） |
| `orchestrator/` | 纯 Python 串行主编排 CLI |
| `orchestrator/load/` | YAML 加载、模型、列表合并、resolve、TaskBundle |
| `orchestrator/loop/` | `runner.py` 串行状态机、session 绑定、prompt、handoff |
| `orchestrator/persist/` | SQLite 状态与事件、工作区进程锁、manifest、runtime-config fingerprint |

入口：`orchestrator/main.py`。导入前缀：`scripts.workflows.*`。

## 运行与恢复

`runner.py` 以 `prepare → run_sdk → advance` 循环消费已解析的 workflow；业务返工和 handoff 协议修复沿用既有上限。

标准库 SQLite 在 `workspace/memory/orchestrator.sqlite` 中维护 `workflow_runs`（最新状态 JSON，含会话引用和下一动作）与 `workflow_events`（动作开始、结束、失败及任务身份）。状态和事件在同一短事务内提交，worker / 检查器 / hook 执行期间不持有数据库事务。manifest 在状态提交后原子更新；恢复时可由检查点重建。

调用 worker 或执行 advance 前先提交 `in_flight`。若结果提交前进程中断，恢复时停止并记为失败，不自动重发有不确定副作用的操作；worker 结果已提交则直接从 advance 继续。`workspace/memory/orchestrator.lock` 使用操作系统进程锁，重复启动直接报忙，退出后自动释放，锁文件本身保留。

新运行使用 `runtime_version = 4`。旧 LangGraph 表保留，但 `--resume` 不迁移旧运行；应重新启动。CLI 参数与 GUI 启动入口不变。
