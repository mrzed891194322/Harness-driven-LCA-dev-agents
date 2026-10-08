# agents_runtime

与 `backend`、`frontend` 平级的 **Agent worker 运行时**：

| 路径 | 说明 |
| --- | --- |
| `client.py`、`process.py` | Python NDJSON 客户端（包名 `agents_runtime`） |
| `pi-runtime/` | Node Pi SDK 子进程（`@harness/pi-runtime`，`pnpm --filter @harness/pi-runtime build`） |

编排器经 `shared/core/agents` 的 provider 调用 `agents_runtime.client`。
