# 已迁移（仅兼容旧工作区）

运行级文件已迁至 `workspace/runs/_run/`（manifest、checkpoint、progress、evidence、resume、rework、sessions 等）。  
阶段尝试仍在 `workspace/runs/<stage-id>/<role>-<n>/`；正式交付在 `workspace/artifacts/`。

代码在读取当前运行摘要时仍会**只读**回退到本目录下的旧路径（若存在）。新运行只写入 `runs/_run/`。  
`whole-lca` 预清理会清空 `runs/`（保留 `runs/_run/orchestrator.lock` 与 `**/README.md`），不会依赖本目录。

详见 `workspace/runs/README.md` 与 `docs/PROJECT_LAYOUT.md`。
