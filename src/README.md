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
npm start        # 正式入口：同步依赖、构建 pi-runtime，再执行 npm run dev
npm run dev      # 后端 → 唯一的 pi-runtime → 前端，后台常驻，默认真实模型
npm run stop     # 后端 → pi-runtime → 前端依次停止，并清理本仓库残留的 MCP / 编排进程
npm run restart  # stop + start，不会叠出第二个 pi-runtime
```

日常停止用 `npm run stop`，不要靠 Ctrl-C。整个项目只有一个 pi-runtime（Unix 套接字 `.local/run/pi-runtime.sock`）；后端和 `workflow.py` 只连接它，不会自己起。

单独起 API（开发用）：

```bash
uv run uvicorn backend.api.app:app --app-dir src --host 127.0.0.1 --port 8800
```

`PYTHONPATH`：`src`（加项目根，见根目录 `pyproject.toml`）。Python 导入一律以 `backend.` 开头。
