# 项目规则

默认注入 [write-boundary.md](write-boundary.md)、[runtime.md](runtime.md) 和 [paths.md](paths.md)，分别约束读写边界、uv 与受限离线处理、产物位置。阶段循环与 LCA 证据约定见 [runtime-loop.md](runtime-loop.md)。审查任务另加 [reviewer-readonly.md](reviewer-readonly.md)。

Agent 只写当前角色获准产物；工具维护的缓存、锁和权威证据不属于可手工编辑的业务文件。离线脚本获准用于提取、换算和复核，不允许绕过 MCP 或修改被审对象。
