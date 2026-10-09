# 环境准备

运行本项目前请准备：

1. **uv**（Python 包管理）
2. **Node.js 22+**（Pi SDK 运行时与控制面板）
3. **openLCA** 桌面客户端，并启用 IPC Server

在仓库根目录执行（macOS、Linux 与 Windows 相同）。脚本会先同步依赖，再启动控制面板；没有 `.env` 时会从 `.env.example` 复制：

```bash
node src/scripts/start.mjs
```

更细的安装步骤见仓库文档 `docs/lang_CN/env_setup.md`。
