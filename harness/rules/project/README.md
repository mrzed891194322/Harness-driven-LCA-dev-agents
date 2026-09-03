# 项目总则

OpenCode 可将本目录三份文件挂到全局 `instructions`。Python 主编排的通用信封也要求只写 `workspace/`。

| 文件 | 用途 |
| --- | --- |
| [`write-boundary.md`](write-boundary.md) | 只写 `workspace/`；`harness/` 只读 |
| [`runtime.md`](runtime.md) | 只用 `uv` / `.venv`；禁止一次性脚本 |
| [`paths.md`](paths.md) | `knowledge/` 与 `workspace/` 固定路径 |
