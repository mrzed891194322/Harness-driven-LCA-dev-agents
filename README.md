# Harness-driven LCA agents project

这是一个使用多智能体（Multi-agent）在 harness 框架下进行合规化 **LCA（Life Cycle Assessment，生命周期评价）** 输出的项目。

## 前置要求

运行本仓库前请先安装：

1. **uv** - Python 包和项目管理工具（[下载&安装链接](https://docs.astral.sh/uv/getting-started/installation/)）
2. **Codex、Claude Code、OpenCode、DSH 四者之一**（CLI、IDE 插件或 Desktop 均可）。若走下方 GUI，所选 Agent 必须是 PATH 上能执行的 CLI（`codex` / `claude` / `opencode` / `dsh`）。Cursor 只用于本仓库开发，不当 LCA 操作员。
3. **[openLCA](https://www.openlca.org/download/)** 桌面客户端。**每次开始项目前**必须打开 openLCA、打开目标数据库，并启用 IPC Server（默认 `127.0.0.1:8080`），否则后续导入与计算无法进行。

## 环境配置

首次运行前，在所用 AI 工具（CLI、IDE 插件或 Desktop）中打开本仓库，输入：

```text
读取并执行 src/scripts/proj_init/PROMPT.md
```

快捷方式（效果相同）：OpenCode / Claude Code 输入 `/bootstrap-env`；Codex 输入 `$bootstrap-env`；DSH 输入「读取并执行 `.dsh/skills/bootstrap-env/SKILL.md`」。

Agent 会检查 uv、项目依赖、`.env`、`control_openlca` MCP、哪些 Agent CLI 可用，并建议将可用 CLI 设为 auto-review；随后检查 openLCA IPC。没有 uv 时判定不通过，需按 [环境准备与配置](docs/lang_CN/env_setup.md) 手动安装。不要在引导里启动 whole-lca。

---

## 启动控制面板 GUI (推荐)

项目已提供 **Gradio Web 控制面板**（位于 [src/GUI](src/GUI)），支持可视化所有工作内容。

### 启动方式 (通用)

在项目根目录下，于终端执行以下命令：
```bash
uv run python src/GUI/main.py
```

浏览器访问 [http://127.0.0.1:7860](http://127.0.0.1:7860)。默认端口 `7860` 可在 `.env` 的 `GUI_PORT` 修改。

### 1. 设置并完成初始化检查

左侧点 **设置&初始化**，再点 **开始初始化检查**。两项全部通过后才会解锁 **执行LCA计划**。未通过时按失败项处理，然后重新检查：

| 检查项 | 处理 |
| --- | --- |
| AI Agent 工具 | 配置目录「设置 AI Agent 工具」选 `codex` / `claude` / `opencode` / `dsh`，点「保存并检查可用性」。对应 CLI 必须在 PATH 上。 |
| OpenLCA | 打开目标数据库并启用 IPC Server。截图见 [环境准备与配置](docs/lang_CN/env_setup.md)。 |


![setting and check](docs/assets/images/readme/set-check.png)

### 2. 编写或传入计划并执行

1. 左侧点 **开始LCA工作**，打开计划模板。
2. 直接填写输入区，或点 **上传计划** 传入已有 `.md`。
3. 初始化检查已通过、计划非空后，点 **执行LCA计划**。
4. 完成后在 **LCA评估结果** 查看报告。

![start LCA](docs/assets/images/readme/start-lca.png)

---

## 在 AI Agent 中直接运行

不使用 GUI 时，在 Codex / Claude Code / OpenCode / DSH（CLI、IDE 插件或 Desktop）中打开本仓库，按下列顺序操作。

### whole-lca

1. 已完成上方环境引导。
2. 手动清理：

```bash
uv run python src/scripts/clean_dir/main.py -y --preset whole-lca
```

3. 复制参考资料到 `harness/knowledge/`，编写 `workspace/inputs/plan.md`。
4. 在当前 AI 工具中输入：
   - OpenCode / Claude Code：`/whole-lca`
   - Codex：`$whole-lca`
   - DSH：「读取并执行 `.dsh/skills/whole-lca/SKILL.md`」

### revise-lca

1. 已完成上方环境引导。
2. 手动清理（不清理 workspace）：

```bash
uv run python src/scripts/clean_dir/main.py -y --preset revise-lca
```

3. 更新 `harness/knowledge/` 与 `workspace/inputs/revise.md`（保留既有 plan / manifest / 报告）。
4. 在当前 AI 工具中输入 `/revise-lca`、`$revise-lca`，或 DSH「读取并执行 `.dsh/skills/revise-lca/SKILL.md`」。

`clean_dir` 详见 [src/scripts/clean_dir/README.md](src/scripts/clean_dir/README.md)。GUI 内部启动命令见 [platform-adapter.md](docs/lang_CN/platform-adapter.md)。
