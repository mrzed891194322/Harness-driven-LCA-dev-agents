# pi_agents

与 `backend`、`frontend` 平级的 **Pi Agent worker 运行时**：

| 路径 | 说明 |
| --- | --- |
| `client.py`、`process.py` | Python NDJSON 客户端（包名 `pi_agents`） |
| `pi-runtime/` | Node Pi SDK 子进程（`@harness/pi-runtime`） |

编排器经 `shared/core/agents` 的 provider 调用 `pi_agents.client`。
