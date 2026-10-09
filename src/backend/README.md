# backend

FastAPI 栈：

- **`api/`**：HTTP 应用与路由（控制面板唯一业务 API）。
- **`services/`**：API / Web 使用的应用服务（含 `executor_console` 流式跑编排、`workflow_service` 读 manifest 等）。

共用编排与工具在 **`src/shared/`**；编排器内部脚本入口在 **`src/scripts/`**（由服务子进程调用，不对用户暴露为控制方式）。
