# 知识

`registry.knowledge.<id>` 只写 `kind: local_dir`、`path`、`provider: local_files`。现有两条：

| ID | 路径 | 内容 |
| --- | --- | --- |
| `workspace_knowledge` | `harness/knowledge/inputs/` | 用户参考资料 |
| `workflow_plan` | `harness/knowledge/plan/` | `main_plan.md`；修订任务还有 `revise_plan.md` |

默认两条都在 `defaults.knowledge` 里，所以每个阶段都能读到。某个阶段要多带或拿掉时，用该阶段的 `knowledge: {add, remove}`。

这些目录是执行前的输入。`whole-lca` 清理会动 knowledge 暂存；启动流程会先复制再写回。改存放位置时要同时改 YAML、阶段 spec 的 `inputs`，以及 `workflow_launch.py` 的快照路径。不要把运行产物写进 `harness/knowledge/`。
