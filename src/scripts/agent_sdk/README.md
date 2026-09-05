# Agent SDK 门面

Worker 的配置、廉价探测与真正调用都在 `providers/<name>/`（`config.py` / `inspect.py` / `run.py`）。主编排 `run()` 与 GUI 任务门禁共用这一套。

| 入口 | 行为 |
| --- | --- |
| `inspect(name)` | 廉价：SDK 可导入 + 该 worker 的运行时依赖。不发 LLM。`agents_check --inspect` 走这里。 |
| `check(name)` | `inspect` 之后用同一条 `run()` 发短 ping。GUI / `check_status --only agents` 在已选 worker 时走这里。 |
| `run(name, prompt, cwd=...)` | 真正调用。`lca_orchestrator.workers` 只做转发。 |

```bash
uv run python src/scripts/agent_sdk/main.py --agent claude
uv run python src/scripts/agent_sdk/main.py --agent opencode --inspect
```

`--agent` 取值：`claude` / `codex` / `opencode` / `dsh` / `antigravity`。
默认 live check 会向模型发一条短请求；pytest 必须 mock `run`，不要打真 LLM。
