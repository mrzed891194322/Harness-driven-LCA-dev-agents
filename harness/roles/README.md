# Agent 角色职责

主编排是 Python LangGraph 程序，不再由 IDE 会话扮演。Worker 会话只承担 YAML 中的写者或审查任务。

| 角色 | 文件 | 说明 |
| --- | --- | --- |
| 执行 | `sub-executor.md` | 对应 YAML `role: executor`（whole-lca 02–04） |
| 修订 | `sub-executor.md` | 对应 YAML `role: reviser`（revise-lca 02–04）；任务正文是各包 `reviser.md` |
| 只读审查 | `eval-reviewer.md` | 对应 YAML `role: reviewer` |
| 历史主编排说明 | `major-orchestrator.md` | 人读对照；运行时由 `lca_orchestrator` 取代 |

通用职责与 handoff 以 `harness/specs/public/references/workflow-runtime-spec.md` 为准。阶段任务说明在各 spec 包的 `executor.md` / `reviser.md` / `reviewer.md`。
