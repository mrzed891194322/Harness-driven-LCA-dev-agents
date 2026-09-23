# Harness-driven LCA agents project

这是一个使用多智能体（Multi-agent）在 harness 框架下进行合规化 **LCA（Life Cycle Assessment，生命周期评价）** 输出的项目。

## 前置要求

运行本仓库前请先安装：

1. **uv** - Python 包和项目管理工具（[下载&安装链接](https://docs.astral.sh/uv/getting-started/installation/)）
2. **Codex、Claude、OpenCode 或 Pi** 的官方 CLI（需在 PATH 上：`codex` / `claude` / `opencode` / `pi`）。走 GUI 时，在「设置&初始化」点「AI Agent 工具」卡片上的「配置」，选择其中一个并填写对应模型 id。认证使用各 CLI 的本机登录。Cursor 只用于本仓库开发，不当 LCA 操作员。
3. **[openLCA](https://www.openlca.org/download/)** 桌面客户端。**每次开始项目前**必须打开 openLCA、打开目标数据库，并启用 IPC Server（默认 `127.0.0.1:8080`），否则后续导入与计算无法进行。

## 环境配置

首次运行前，在所用 AI 工具中打开本仓库，输入：

```text
读取并执行 scripts/proj_init/PROMPT.md
```

或直接：

```bash
uv sync
uv run python src/scripts/proj_init/main.py
```

Agent 会检查 uv、项目依赖、`.env`（缺失则从 `.env.example` 复制）、`control_openlca` MCP，以及哪些 worker CLI 在 PATH 上。没有 uv 时判定不通过，需按 [环境准备与配置](docs/lang_CN/env_setup.md) 手动安装。不要在引导里启动 whole-lca。`.env` 里要填的 Worker 与模型见 `.env.example`。

---

## 启动控制面板 GUI (推荐)

项目已提供 **Gradio Web 控制面板**（位于 [src/gui](src/gui)），支持可视化所有工作内容。

### 启动方式 (通用)

在项目根目录下，于终端执行以下命令：
```bash
uv run python src/gui/main.py
```

浏览器访问 [http://127.0.0.1:7860](http://127.0.0.1:7860)。默认端口 `7860` 可在 `.env` 的 `GUI_PORT` 修改。

### 1. 设置并完成初始化检查

左侧点 **设置&初始化**，再点 **开始初始化检查**。两项全部通过后才会解锁 **执行LCA计划**。未通过时按失败项处理，然后重新检查：

| 检查项 | 处理 |
| --- | --- |
| AI Agent 工具 | 主页下拉选择当前 `codex` / `claude` / `opencode` / `pi`。点「配置」后用横向卡片切换各后端表单（缺省见 `.env.example` 的 `CODEX_MODEL` / `CLAUDE_MODEL` / `OPENCODE_MODEL` / `PI_MODEL`）。点「测试连接」用诊断指令验证本机登录，不开启对话。点「开始初始化检查」探测所选 CLI 是否在 PATH 上（`--version`）。 |
| OpenLCA | 打开目标数据库并启用 IPC Server。截图见 [环境准备与配置](docs/lang_CN/env_setup.md)。 |


![setting and check](docs/assets/images/readme/set-check.png)

### 2. 编写或传入计划并执行

1. 左侧点 **开始LCA工作**，打开计划模板。
2. 直接填写输入区，或点 **上传计划** 传入已有 `.md`。
3. 初始化检查已通过、计划非空后，点 **执行LCA计划**。
4. 完成后在 **LCA评估结果** 查看报告。

![start LCA](docs/assets/images/readme/start-lca.png)

---

## 用 Python 主编排器运行

不使用 GUI 时，在项目根目录执行。不要把 IDE 会话当成主编排。

### whole-lca

1. 已完成上方环境引导。
2. 手动清理：

```bash
uv run python src/scripts/clean.py -y --preset whole-lca
```

3. 复制参考资料到 `harness/knowledge/`，编写 `workspace/inputs/plan.md`。
4. 启动：

```bash
uv run python src/scripts/workflow.py --task whole-lca
```

可选 `--worker codex`（或 `claude` / `opencode` / `pi`）。模型 id 读 `.env` 的 `CODEX_MODEL` / `CLAUDE_MODEL` / `OPENCODE_MODEL` / `PI_MODEL`。恢复已有运行：`--resume <run_id>`（不执行新运行清理）。

### revise-lca

1. 已完成上方环境引导。
2. 手动清理（不清理 workspace）：

```bash
uv run python src/scripts/clean.py -y --preset revise-lca
```

3. 更新 `harness/knowledge/` 与 `workspace/inputs/revise.md`（保留既有 plan / manifest / 报告）。
4. 启动：

```bash
uv run python src/scripts/workflow.py --task revise-lca
```

revise 走同一套 01–04：01 审查修订门禁，02–04 由 `reviser` 在既有产物上落实 `revise.md`，再由 reviewer 审核（用户意图优先）。

`clean` CLI 见 `src/scripts/clean.py`。GUI 内部启动命令见 [platform-adapter.md](docs/lang_CN/platform-adapter.md)。
