# `src/` 布局

`src/` 下仅保留这些顶层目录（外加本说明文件）：

```
src/
  backend/          # FastAPI（api/ + services/）
  frontend/         # Next.js（web/）
  pi_agents/        # Pi Agent worker：Python 客户端 + Node pi-runtime
  shared/           # 编排器与 API 共用的 Python（core、utils、config…）
  scripts/          # 开发启动（dev.mjs）、环境引导与编排器内部入口
  tests/            # 回归测试
```

## 常用命令

```bash
npm run dev   # 控制面板：Next.js + FastAPI（唯一用户控制入口）
```

单独起 API（开发用）：

```bash
uv run uvicorn api.app:app --app-dir src/backend --host 127.0.0.1 --port 8800
```

`PYTHONPATH`：`src/backend` + `src/shared` + `src`（见根目录 `pyproject.toml`）。
