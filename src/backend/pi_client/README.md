# pi_client

**Pi Agent worker 的 Python 客户端**（包名 `backend.pi_client`）：

| 路径 | 说明 |
| --- | --- |
| `client.py` | `PiRuntimeSessionClient`：按分工创建、运行、释放 Pi 会话 |
| `process.py` | `PiRuntimeClient`：连接项目唯一的 pi-runtime（Linux / macOS 为 `.local/run/pi-runtime.sock`，Windows 为 `tcp://127.0.0.1:<端口>`，记在 `.local/run/pi-runtime.endpoint`，`PI_RUNTIME_SOCKET` 可改），断线重连一次；从不自己起 runtime（`PI_RUNTIME_PRIVATE=1` 仅测试用）。`close()` 释放本连接的会话后断开 |
| `env.py` | runtime 与 MCP 的环境变量白名单；`python -m backend.pi_client.env` 供 `dev.mjs` 使用 |
| `src/pi-runtime/` | Node Pi SDK 服务（`@harness/pi-runtime`，由 `npm run dev` 启动、`npm run stop` 停止） |

编排器经 `backend/core/agents` 的 provider 调用 `backend.pi_client.client`。
