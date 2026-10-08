# `src/` 布局

```
src/
  frontend/                 # Next.js + legacy GUI 参考
    web/
    legacy/gui/
  backend/                  # FastAPI 栈
    api/                      # HTTP 路由与应用
    services/                 # API / Web 控制台调用的应用服务
  shared/                   # CLI、编排器、API 共用的 Python
    core/                     # workflow / agents / runtime
    agents_runtime/           # Agent worker 子进程客户端（Pi SDK）
    utils/、config/、contracts/
    diagnostics.py、workspace_clean.py、app_settings.py
  pi-runtime/               # Node Pi SDK（NDJSON，与 agents_runtime 配对）
  cli/                      # 薄 CLI（workflow、clean、proj_init）
  scripts/                  # dev.mjs 等跨栈脚本
  tests/
```

## 常用命令

```bash
uv run uvicorn api.app:app --app-dir src/backend --host 127.0.0.1 --port 8000
uv run python src/cli/workflow.py --workflow harness/LCA-main.yaml
pnpm dev
```

Python `PYTHONPATH`：`src/backend`（`api`、`services`）+ `src/shared`（`core`、`agents_runtime` 等），见根目录 `pyproject.toml`。

跨语言契约：`src/shared/contracts/session_launch_spec.schema.json`；Python 类型在 `src/shared/core/contracts/`。
