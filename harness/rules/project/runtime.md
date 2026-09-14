# 运行时

- 项目中由 `uv` 管理的虚拟环境（通常位于 `.venv/`）是**唯一可用**的 Python 运行环境。运行 Python 用 `uv run`，不要改用系统 Python 或另建虚拟环境。
- 严禁在代码中硬编码 `.venv/` 路径。
- uv 包缓存默认在仓库根 `.uv-cache/`（可用环境变量 `UV_CACHE_DIR` 覆盖）。不要把缓存放进 `workspace/tmp/`。
- 工作流 MCP 子进程由编排器改写为当前解释器启动（复用已解析的 `.venv`），YAML 中的 `uv run python` 仅表示意图。
- 禁止在 `workspace/tmp/` 或任何其他位置编写一次性探测、查询、导入或计算脚本。现有 MCP 或正式工具能力不足时报告缺口并停止相关阶段，不要用临时脚本绕过。
