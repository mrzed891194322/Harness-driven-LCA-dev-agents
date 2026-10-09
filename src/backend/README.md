# backend

唯一的 Python 包（`backend`，以 `src` 为导入根，`PYTHONPATH=src`）：

- **`api/`**：FastAPI HTTP 应用与路由（控制面板唯一业务 API）。
- **`services/`**：API / Web 使用的应用服务（含 `executor_console` 流式跑编排、`workflow_service` 读 manifest 等），以及 `diagnostics.py`、`workspace_clean.py`。
- **`core/`**：Python 主编排器（`workflow/`、`runtime/`、`agents/`、`contracts/`），负责组装工作流要素并注入 Pi agent。core 不得 import `api`、`services`。
- **`pi_client/`**：Pi Agent worker 的 Python NDJSON 客户端（`client.py`、`process.py`），连接项目唯一的 `src/pi-runtime/` 服务（Node Pi SDK，`@harness/pi-runtime`，由 `npm run dev` 启动）。
- **`settings.py`**：应用级 `.env` 设置键，以及通用的 `.env`、文件系统清理、workspace 目录名辅助函数（原 `app_settings.py` 与 `utils/`）。

编排器内部脚本入口在 **`src/scripts/`**（由服务子进程调用，不对用户暴露为控制方式）。用户侧控制只经 Web 控制面板。
