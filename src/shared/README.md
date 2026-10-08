# Shared

CLI、Python 主编排器与 FastAPI 共用的 Python 包与模块：

| 路径 | 说明 |
| --- | --- |
| `core/` | YAML 工作流编排、agent 会话、checkpoint / manifest |
| `agents_runtime/` | Node `pi-runtime` 的 Python 客户端（NDJSON） |
| `utils/`、`config/`、`contracts/` | 工具、模型档案、跨语言 schema |
| `diagnostics.py`、`workspace_clean.py`、`app_settings.py` | 环境探测与 workspace 清理 |

导入根目录：`pyproject.toml` 将 `src/shared` 加入 `pythonpath`（与 `src/backend` 并列）。
