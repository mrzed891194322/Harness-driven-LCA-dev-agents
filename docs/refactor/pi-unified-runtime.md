# Pi SDK 统一运行时重构

## 核验依赖

| 组件 | 版本 | 依据 |
| --- | --- | --- |
| Node | 22.x（`.node-version`） | Cloud / nvm 22.14+ |
| `@earendil-works/pi-coding-agent` | 1.1.0 | npm registry / `apps/pi-runtime` 锁定 |
| Next.js | 15.x | `apps/web/package.json` |
| FastAPI | uv `pyproject.toml` | Python 业务 API |

SDK 使用 `createAgentSession` + `DefaultResourceLoader`（禁用 skills/模板自动发现）+ `createMcpExtension()`（MCP 写入隔离 `agent_dir/mcp.json`）。

## 架构

- **Python**：workflow 语义、验收、checkpoint、handoff 校验（不变）
- **Node `apps/pi-runtime`**：Pi SDK session、工具、MCP；stdin/stdout NDJSON 协议
- **FastAPI `src/api`**：浏览器唯一业务 API
- **Next.js `apps/web`**：替代 Gradio GUI

跨语言契约：`contracts/session_launch_spec.schema.json` + `src/core/contracts/session_launch_spec.py`。

## 启动

```bash
uv sync
pnpm install
pnpm --filter @harness/pi-runtime build
pnpm dev   # Next.js :3000 + uvicorn :8000
```

CLI 工作流（无浏览器）：

```bash
PI_RUNTIME_MOCK=1 uv run python src/scripts/workflow.py --workflow harness/LCA-main.yaml
```

`PI_RUNTIME_MOCK=1` 仅用于无 API 密钥的协议/编排测试；真实模型调用需配置 `.local/credentials/pi-auth.json` 与模型档案。

## 旧运行时

已移除对 PATH 上 `codex` / `claude` / `opencode` / `pi` CLI 的依赖。`HARNESS_AGENT` 保留兼容但固定为 Pi SDK runtime。
