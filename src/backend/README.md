# backend

FastAPI 栈：

- **`api/`**：HTTP 应用与路由。
- **`services/`**：API / Web 使用的应用服务（含 `executor_console` 流式跑编排、`workflow_service` 读 manifest 等）。

共用编排与工具在 **`src/shared/`**；命令行入口在 **`src/scripts/`**。
