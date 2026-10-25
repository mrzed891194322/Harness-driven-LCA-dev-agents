# 环境准备

运行本项目前请准备：

1. **uv**（Python 包管理）
2. **Node.js 22+**（Pi SDK 运行时与控制面板）
3. **openLCA** 桌面客户端，并启用 IPC Server
4. **Windows：** [Git for Windows](https://git-scm.com/download/win)，供 Agent 的 bash 工具使用

在仓库根目录执行（Linux、macOS 或原生 Windows）。脚本会先同步依赖，再依次启动后端、pi-runtime 和前端；没有 `config.toml` 时会从 `config.example.toml` 复制：

```bash
npm start          # 或 node src/scripts/start.mjs
```

服务在后台常驻。停止用 `npm run stop`，重启用 `npm run restart`，不要靠 Ctrl-C 或关终端。

更细的安装步骤见仓库文档 `docs/guide/lang_CN/env_setup.md`。
