# Harness-driven LCA agents project

这是一个使用多智能体（Multi-agent）在 harness 框架下进行合规化 **LCA（Life Cycle Assessment，生命周期评价）** 输出的项目。


## 前置要求

运行本仓库前请先安装：

1. **uv** - Python 包和项目管理工具（[下载&安装链接](https://docs.astral.sh/uv/getting-started/installation/)）
2. **Codex、Claude Code、OpenCode 三者之一的 CLI**（终端里能执行 `codex` / `claude` / `opencode` 任一即可）。仅 IDE 插件或网页对话不算满足前置要求。
3. **[openLCA](https://www.openlca.org/download/)** 桌面客户端。**每次开始项目前**必须打开 openLCA、打开目标数据库，并启用 IPC Server（默认 `127.0.0.1:8080`），否则后续导入与计算无法进行。

## 环境配置

在首次运行本项目前需要完成的工作（）

### 命令行让 agent 一键配环境（推荐）

通过终端在仓库根目录下执行下列CLI命令（之一），让agent自主完成环境配置工作：

```bash
# opencode 用户在终端中粘贴并执行
opencode run --command bootstrap-env

# codex 用户在终端中粘贴并执行
codex exec -s workspace-write '$bootstrap-env'

# claude 用户在终端中粘贴并执行
claude -p "/bootstrap-env"
```



### 手动配环境

也可以自行安装 uv、执行 `uv sync`、复制并填写 `.env`。详细步骤见 [环境准备与配置](docs/lang_CN/env_setup.md)。

---

## 🖥️ 启动控制面板 GUI (推荐)

项目已提供 **Gradio Web 控制面板**（位于 [src/GUI](src/GUI)），支持可视化所有工作内容。

### 启动方式 (通用)

在项目根目录下，于终端执行以下命令：
```bash
uv run python src/GUI/main.py
```
启动成功后，在浏览器中手动访问 [http://127.0.0.1:7860](http://127.0.0.1:7860)。

7860为默认端口，端口值可以在`.env`文件中进行修改






---

## 🛠️ 辅助功能（手动/命令行执行）

在无图形界面（GUI）环境下或开发调试时，核心交互逻辑为：**先将输入文件放入 `workspace/inputs/`（参考文件放在 `workspace/inputs/references/file/`、数据文件放在 `workspace/inputs/references/data/`），再运行对应的 `opencode` 指令执行任务**。


> 💡 **关于文件放置路径、人工审核交互及完整调试步骤，请参见**：[手动调试与文件同步指南](docs/lang_CN/manual_debug.md)
