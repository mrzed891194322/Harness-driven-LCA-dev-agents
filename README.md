# Harness-driven LCA agents project

这是一个使用多智能体（Multi-agent）在 harness 框架下进行合规化 **LCA（Life Cycle Assessment，生命周期评价）** 输出的项目。

## 前置要求

运行本仓库前请先安装：

1. **uv** - Python 包和项目管理工具（[下载&安装链接](https://docs.astral.sh/uv/getting-started/installation/)）
2. **Codex、Claude Code、OpenCode、DSH 四者之一的 CLI**（终端里能执行 `codex` / `claude` / `opencode` / `dsh` 任一即可）。仅 IDE 插件或网页对话不算满足前置要求。
3. **[openLCA](https://www.openlca.org/download/)** 桌面客户端。**每次开始项目前**必须打开 openLCA、打开目标数据库，并启用 IPC Server（默认 `127.0.0.1:8080`），否则后续导入与计算无法进行。

## 环境配置

首次运行前，通过终端在仓库根目录下执行下列 CLI 命令（之一），让 agent 自主完成环境配置：

```bash
# opencode 用户在终端中粘贴并执行
opencode run --command bootstrap-env

# codex 用户在终端中粘贴并执行
codex exec -s workspace-write '$bootstrap-env'

# claude 用户在终端中粘贴并执行
claude -p "/bootstrap-env"

# dsh 用户在终端中粘贴并执行
DSH_PERMISSION_MODE=danger-full-access dsh --profile headless --patch .dsh/cordis.patch.yml "读取并执行 .dsh/skills/bootstrap-env/SKILL.md"
```

详细步骤见 [环境准备与配置](docs/lang_CN/env_setup.md)。

---

## 🖥️ 启动控制面板 GUI (推荐)

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
| AI Agent 工具 | 配置目录「设置 AI Agent 工具」选 `codex` / `claude` / `opencode`，点「保存并检查可用性」。对应 CLI 必须在 PATH 上。 |
| OpenLCA | 打开目标数据库并启用 IPC Server。截图见 [环境准备与配置](docs/lang_CN/env_setup.md)。 |


![setting and check](docs/assets/images/readme/set-check.png)

### 2. 编写或传入计划并执行

1. 左侧点 **开始LCA工作**，打开计划模板。
2. 直接填写输入区，或点 **上传计划** 传入已有 `.md`。
3. 初始化检查已通过、计划非空后，点 **执行LCA计划**。
4. 完成后在 **LCA评估结果** 查看报告。

![start LCA](docs/assets/images/readme/start-lca.png)

---

## 命令行直接运行（无 GUI）

GUI 会在执行前自动清理并同步文件；命令行用户需手动完成等价步骤：

### whole-lca

```bash
uv run python src/scripts/clean_dir/main.py -y --preset whole-lca
# 复制资料到 harness/knowledge/，编写 workspace/inputs/plan.md
opencode run --command whole-lca --dangerously-skip-permissions
```

### revise-lca

```bash
uv run python src/scripts/clean_dir/main.py -y --preset revise-lca
# 更新 harness/knowledge/ 与 workspace/inputs/revise.md（保留既有 plan/manifest/报告）
opencode run --command revise-lca --dangerously-skip-permissions
```

其他平台一行命令见 [.dsh/README.md](.dsh/README.md)。`clean_dir` 详见 [src/scripts/clean_dir/README.md](src/scripts/clean_dir/README.md)。
