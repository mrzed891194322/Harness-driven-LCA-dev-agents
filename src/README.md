# `src/` 布局

`src/` 下仅保留这些顶层目录（外加本说明文件）：

```
src/
  backend/          # 唯一的 Python 包：FastAPI（api/ + services/）、编排器 core/、Pi 客户端 pi_client/、settings.py
  frontend/         # Next.js（web/）
  pi-runtime/       # Node Pi SDK 宿主（@harness/pi-runtime）
  scripts/          # 开发启动（dev.mjs）、环境引导与编排器内部入口
  tests/            # 回归测试
```

## 常用命令

```bash
npm run dev   # 控制面板：Next.js + FastAPI（唯一用户控制入口）
```

单独起 API（开发用）：

```bash
uv run uvicorn backend.api.app:app --app-dir src --host 127.0.0.1 --port 8800
```

`PYTHONPATH`：`src`（加项目根，见根目录 `pyproject.toml`）。Python 导入一律以 `backend.` 开头。
