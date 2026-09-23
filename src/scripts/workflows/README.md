# Workflows 编排实现

YAML 契约在 [`harness/LCA-*.yaml`](../../../harness/)。本目录是 Python 实现。

| 路径 | 职责 |
| --- | --- |
| `runtime/` | 通用内核：`RunContext`、capabilities、hashing、identifiers、local_files |
| `domains/lca/` | LCA 能力与 MCP 适配（checkers / hooks / handoff 扩展 / 上下文与证据策略） |
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

## 工具边界与检查

`harness/tools/` 的独立工具不导入 workflow；LCA 适配层调用底层能力并在数据库操作前执行工作流门禁。通用 SDK 只处理 stdio 启动配置和每服务超时。

YAML 只读取/合并一次；引用与阶段拓扑在 resolver 检查，声明文件按解析后的路径去重检查。运行时保留写者后的完整校验、审核通过后的变化检测及导入前检查。文件读取缓存只覆盖一次确定性检查，并随文件状态变化失效，不跨回合或操作共享。

能力依赖的导入测试在独立进程执行，不修改当前 pytest 进程的 `sys.modules`。接口迁移改变实现指纹，重构前未完成的运行按现有规则拒绝续跑；请新建运行。
