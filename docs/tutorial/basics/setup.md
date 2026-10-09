# 环境准备

运行本项目前请准备：

1. **uv**（Python 包管理）
2. **Node.js 22+**（Pi SDK 运行时与控制面板）
3. **openLCA** 桌面客户端，并启用 IPC Server

首次克隆仓库后，可在 AI 工具中执行：

```text
读取并执行 `src/scripts/proj_init/PROMPT.md`
```

或在仓库根目录：

```bash
uv sync
npm install
npm run build -w @harness/pi-runtime
uv run python src/scripts/proj_init/main.py
```

更细的安装步骤见仓库文档 `docs/lang_CN/env_setup.md`。
