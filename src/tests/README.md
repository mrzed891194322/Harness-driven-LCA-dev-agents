# 测试

本目录（`src/tests/`）是仓库唯一的测试根目录。从仓库根目录运行：

```bash
uv run pytest
```

## 目录结构

| 路径 | 覆盖范围 |
| --- | --- |
| `gui/` | Gradio GUI 路径、设置、计划编辑器、文件同步、LCA 结果 |
| `scripts/` | `agent_sdk`、`clean_dir`、项目初始化、GUI 进程管理 |
| `harness/workflows/` | 工作流 YAML 契约与 LangGraph 编排 |
| `harness/tools/control_openlca/` | openLCA MCP 离线回归（mock IPC） |
| `support/` | 共享测试 fakes（如 openLCA FakeClient） |
| `conftest.py` | `PROJECT_ROOT` 等路径常量与 `local_script_packages` |

## 分模块运行

```bash
uv run pytest src/tests/gui -v
uv run pytest src/tests/scripts -v
uv run pytest src/tests/harness/workflows -v
uv run pytest src/tests/harness/tools/control_openlca -v
```

## 开发检查

```bash
uv run ruff format .
uv run ruff check .
uv run pyright
uv run pytest
```

测试使用临时目录与 mock，不读写真实 `workspace` 运行产物。
