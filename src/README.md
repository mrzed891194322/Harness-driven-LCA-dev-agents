# `src/` 布局

`src/` 下仅保留这些顶层目录（外加本说明文件）：

```
src/
  backend/          # FastAPI（api/ + services/）
  frontend/         # Next.js（web/）
  pi_agents/          # Pi Agent worker：Python 客户端 + Node pi-runtime
  shared/           # CLI、编排器、API 共用的 Python（core、utils、config…）
  scripts/          # 开发脚本（dev.mjs）与 Python 薄 CLI（workflow、clean…）
  tests/            # 回归测试
```

## 常用命令

```bash
uv run uvicorn api.app:app --app-dir src/backend --host 127.0.0.1 --port 8000
uv run python src/scripts/workflow.py --workflow harness/LCA-main.yaml
npm run dev
```

`PYTHONPATH`：`src/backend` + `src/shared` + `src`（见根目录 `pyproject.toml`）。
