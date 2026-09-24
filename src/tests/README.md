# 测试

本目录（`src/tests/`）是仓库唯一的测试根目录。从仓库根目录运行：

```bash
uv run pytest
```

## 布局

| 目录 | 覆盖 |
| --- | --- |
| `t_core/` | orchestrator、agents、runtime（避免与包名 `core` 冲突） |
| `t_harness/tools/` | control_openlca MCP、lca_artifacts 等 harness 工具离线测试 |
| `t_scripts/` | workspace clean、gui_control、proj_init 等薄 CLI 脚本 |
| `gui/` | Gradio 启动、门禁、设置 |
| `support/` | 共享 fake / ScriptedSession 等设施 |

```bash
uv run pytest src/tests/gui -v
uv run pytest src/tests/t_core -v
uv run pytest src/tests/t_harness/tools -v
uv run pytest src/tests/t_scripts -v
```
