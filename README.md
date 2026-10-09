# Harness-driven LCA agents

多智能体在 harness 框架下进行合规化 **LCA（Life Cycle Assessment，生命周期评价）** 的项目。业务操作都在 Web 控制面板中完成。

## 前置要求

以下软件都提供 **macOS、Linux、Windows** 安装包：

1. **[uv](https://docs.astral.sh/uv/getting-started/installation/)**：Python 包与项目管理。Python 3.12 由 uv 按项目配置安装，无需单独准备。
2. **[Node.js 22+](https://nodejs.org/)**（自带 npm）。
3. **[openLCA](https://www.openlca.org/download/)** 桌面客户端。使用前打开目标数据库，并启用 IPC Server（默认 `127.0.0.1:8080`）。

## 启动

macOS、Linux 与 Windows 使用同一条命令。在仓库根目录执行（Windows 可用 PowerShell、命令提示符或 Git Bash）：

```bash
node src/scripts/start.mjs
```

每次启动前，脚本会同步 uv 与 Node.js 依赖；若没有 `.env`，会从 `.env.example` 复制一份。浏览器打开终端打印的地址（默认 [http://127.0.0.1:3000](http://127.0.0.1:3000)）。

设置、计划、执行与结果查看，请在应用内打开 **教程**。
