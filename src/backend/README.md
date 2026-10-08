# Backend

仅包含 **FastAPI** 业务 API：

- **`api/`**：诊断、模型档案、计划、manifest、SSE 等 HTTP 端点。

编排内核、Pi SDK 运行时、CLI 与共享服务已移至与 `backend/` 平级的 `src/core`、`src/pi-runtime`、`src/pi_runtime`、`src/cli`、`src/services` 等目录。Python 导入根目录见根目录 `pyproject.toml` 的 `pythonpath`（`src/backend` + `src`）。
