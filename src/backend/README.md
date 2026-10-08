# Backend

FastAPI 相关 Python 代码：

- **`api/`**：HTTP 路由与 `FastAPI` 应用实例。
- **`services/`**：主要由 `api` 与 Web 控制台调用的服务层（诊断聚合、manifest、执行器控制台等）。

编排内核、Agent runtime 客户端、环境清理与 CLI 共用模块在 **`src/shared/`**；命令行入口在 **`src/cli/`**。
