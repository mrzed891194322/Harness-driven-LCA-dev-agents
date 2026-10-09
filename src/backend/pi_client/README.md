# pi_client

**Pi Agent worker 的 Python 客户端**（包名 `backend.pi_client`）：

| 路径 | 说明 |
| --- | --- |
| `client.py`、`process.py` | Python NDJSON 客户端 |
| `src/pi-runtime/` | Node Pi SDK 子进程（`@harness/pi-runtime`，与 `backend`、`frontend` 平级） |

编排器经 `backend/core/agents` 的 provider 调用 `backend.pi_client.client`。
