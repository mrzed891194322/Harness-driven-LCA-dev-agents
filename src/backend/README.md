# Backend

- **`api/`**：FastAPI 业务 API（诊断、模型档案、计划、manifest、SSE）。
- **`pi-runtime/`**：Node Pi SDK 子进程（`@earendil-works/pi-coding-agent`）。
- **`core/`**：YAML 工作流编排、agent 会话客户端、验收与 checkpoint。
- **`scripts/`**：`workflow.py`、`clean.py`、`proj_init/` 等薄 CLI。
- **`services/`**：API 与 CLI 共用的应用服务。

Python 包导入根目录为 `src/backend`（见根目录 `pyproject.toml` 的 `pythonpath`）。
