# Harness-driven LCA agents project

这是一个使用多智能体（Multi-agent）在 harness 框架下进行合规化 **LCA（Life Cycle Assessment，生命周期评价）** 输出的项目。

**控制方式**：业务运行与清理一律通过 **Web 控制面板**完成，不提供面向用户的命令行控制入口。

## 前置要求

运行本仓库前请先安装：

1. **uv** - Python 包和项目管理工具（[下载&安装链接](https://docs.astral.sh/uv/getting-started/installation/)）
2. **Node.js 22+**（自带 npm；Pi SDK 运行时与 Next.js GUI）。模型凭证与档案在 Web 设置页或 `.local/credentials/` 配置，不再依赖全局 `codex` / `claude` / `opencode` / `pi` 可执行文件。
3. **[openLCA](https://www.openlca.org/download/)** 桌面客户端。**每次开始项目前**必须打开 openLCA、打开目标数据库，并启用 IPC Server（默认 `127.0.0.1:8080`），否则后续导入与计算无法进行。

## 环境配置

首次运行前，在所用 AI 工具中打开本仓库，输入：

```text
读取并执行 `src/scripts/proj_init/PROMPT.md`
```

或直接：

```bash
uv sync
uv run python src/scripts/proj_init/main.py
```

Agent 会检查 uv、项目依赖、`.env`（缺失则从 `.env.example` 复制）、`control_openlca` MCP，以及 Pi SDK runtime（Node + pi-runtime）是否就绪。没有 uv 时判定不通过，需按 [环境准备与配置](docs/lang_CN/env_setup.md) 手动安装。不要在引导里启动 whole-lca。`.env` 里的 `PI_MODEL` 与 BYOK 凭证说明见 `.env.example` / Web 设置页。

---

## 启动控制面板

项目提供 **Next.js + FastAPI** 控制面板（`src/frontend/web` + `src/backend/api`），由 Python 编排器监管 **Pi SDK** Node 运行时（`src/pi_agents/pi-runtime`）。这是启动、清理与查看结果的**唯一**用户入口。

```bash
uv sync
npm install
npm run build -w @harness/pi-runtime
npm run dev
```

浏览器访问 [http://127.0.0.1:3000](http://127.0.0.1:3000)。业务 API 默认在 `127.0.0.1:8800`。两条端口都在仓库根 `.env`：`GUI_WEB_PORT`（前端）、`GUI_API_PORT`（后端）。

### 1. 设置并完成初始化检查

打开 **设置与初始化**：

| 检查项 | 处理 |
| --- | --- |
| Pi SDK + 模型 | 选择 `model_profiles.json` 中的模型档案并保存（写入 `.env` 的 `PI_MODEL`）。为对应 Provider 填写自有 API Key（BYOK，写入 `.local/credentials/`，不回显）。点「测试连接」经 Pi `ModelRuntime` 验证凭证与模型，不开启业务对话。环境诊断确认 Node / pi-runtime / Python 就绪。 |
| OpenLCA | 打开目标数据库并启用 IPC Server。截图见 [环境准备与配置](docs/lang_CN/env_setup.md)。 |


![setting and check](docs/assets/images/readme/set-check.png)

### 2. 编写或传入计划并执行

1. 左侧点 **开始LCA工作**，打开计划模板。
2. 直接填写输入区，或点 **上传计划** 传入已有 `.md`。
3. 初始化检查已通过、计划非空后，点 **执行LCA计划**。
4. 完成后在 **LCA评估结果** 查看报告。

whole-lca 与 revise-lca 均在控制面板内选择并执行；执行前的工作区清理由面板接管。revise 走同一套 01–04：01 审查修订门禁，02–04 由 `reviser` 在既有产物上落实 `revise.md`，再由 reviewer 审核（用户意图优先）。

![start LCA](docs/assets/images/readme/start-lca.png)
