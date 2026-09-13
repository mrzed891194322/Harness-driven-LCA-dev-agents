# 项目总则

主工作流默认把本目录的写边界、运行时与路径规则交给每个任务。审查任务另绑 [`reviewer-readonly.md`](reviewer-readonly.md)。

| 文件 | 用途 |
| --- | --- |
| [`write-boundary.md`](write-boundary.md) | 只写 `workspace/`；`harness/` 只读 |
| [`runtime.md`](runtime.md) | 只用 `uv` / `.venv`；禁止一次性脚本 |
| [`paths.md`](paths.md) | `knowledge/` 与 `workspace/` 固定路径 |
| [`reviewer-readonly.md`](reviewer-readonly.md) | 审查只读被审对象，只提交意见与 handoff |
