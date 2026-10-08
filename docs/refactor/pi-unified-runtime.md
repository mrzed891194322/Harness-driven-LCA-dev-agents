# Pi SDK 统一运行时重构

## 核验依赖

| 组件 | 版本 | 依据 |
| --- | --- | --- |
| Node | 22.x（`.node-version`） | Cloud / nvm 22.14+ |
| `@earendil-works/pi-coding-agent` | 1.1.0 | npm registry / `src/pi_agents/pi-runtime` 锁定 |
| Next.js | 15.x | `src/frontend/web/package.json` |
| FastAPI | uv `pyproject.toml` | Python 业务 API |

SDK 使用 `createAgentSession` + `DefaultResourceLoader`（禁用 skills/模板自动发现）+ `createMcpExtension()`（MCP 写入隔离 `agent_dir/mcp.json`）。

## 架构

- **Python**：workflow 语义、验收、checkpoint、handoff 校验（不变）
- **Node `src/pi_agents/pi-runtime`**：Pi SDK session、工具、MCP；stdin/stdout NDJSON 协议
- **FastAPI `src/backend/api`**：浏览器唯一业务 API
- **Next.js `src/frontend/web`**：替代 Gradio GUI

跨语言契约：`src/shared/contracts/session_launch_spec.schema.json` + `src/shared/core/contracts/session_launch_spec.py`。

## 启动

```bash
uv sync
npm install
npm run build -w @harness/pi-runtime
npm run dev   # Next.js :GUI_WEB_PORT（默认 3000）+ uvicorn :GUI_API_PORT（默认 8800）
```

CLI 工作流（无浏览器）：

```bash
PI_RUNTIME_MOCK=1 uv run python src/scripts/workflow.py --workflow harness/LCA-main.yaml
```

`PI_RUNTIME_MOCK=1` 仅用于无 API 密钥的协议/编排测试；真实模型调用需配置 `.local/credentials/pi-auth.json` 与模型档案。

## 模型与 BYOK

- 非密钥档案：`src/shared/config/model_profiles.json`（`.env` 的 `PI_MODEL` 选档案 id）
- 密钥：Web「设置」写入 `.local/credentials/pi-auth.json`（Pi `auth.json` 形态：`{ "<provider>": { "type": "api_key", "key": "..." } }`）
- 会话创建时 `session_host` 物化到 `agent_dir/auth.json`；仅当档案含 `api_type`/`base_url` 时写 `models.json`
- 使用 `@earendil-works/pi-coding-agent` 的 `ModelRuntime.create` + `getModel(provider, model_id)` 接入 `createAgentSession`

## 旧运行时

已移除对 PATH 上 `codex` / `claude` / `opencode` / `pi` CLI 的依赖。`HARNESS_AGENT` 保留兼容但固定为 Pi SDK runtime。
