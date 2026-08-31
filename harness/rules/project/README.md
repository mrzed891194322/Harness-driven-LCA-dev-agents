# 项目总则

所有角色、所有阶段都加载本目录三份文件（亦见 [`../injection.md`](../injection.md)）。OpenCode 可将它们挂到全局 `instructions`。

| 文件 | 用途 |
| --- | --- |
| [`write-boundary.md`](write-boundary.md) | 只写 `workspace/`；`harness/` 只读 |
| [`runtime.md`](runtime.md) | 只用 `uv` / `.venv`；禁止一次性脚本 |
| [`paths.md`](paths.md) | `knowledge/` 与 `workspace/` 固定路径 |
