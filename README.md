# Harness-driven LCA agents project

这是一个使用多智能体（Multi-agent）在 harness 框架下进行合规化 **LCA（Life Cycle Assessment，生命周期评价）** 输出的项目。

## 📁 项目目录总览

- `harness/`：workflow 契约、stage 规则、OpenLCA 和 RAG 工具实现。
- `src/`：GUI、脚本、初始化与文件同步逻辑。
- `workspace/`：当前运行期唯一输入与产物目录（`workspace/inputs/plan.md`、`workspace/outputs/LCI/`、`workspace/outputs/reports/`）。
- `docs/lang_CN/`：中文文档集合（原 `docs/wiki` 已迁移并清理）。
- `.opencode/`：OpenCode 命令、Agent 和适配配置。

## 🔖 中文文档入口

- [文档首页](docs/lang_CN/README_CN.md)
- [环境准备与配置](docs/lang_CN/env_setup.md)
- [项目准备说明](docs/lang_CN/project_prep.md)
- [RAG 构建与查询](docs/lang_CN/rag_guide.md)
- [用户指南](docs/lang_CN/user_guide.md)
- [手动调试与文件同步](docs/lang_CN/manual_debug.md)

## ⚡ Windows 一键脚本 (推荐)

为了方便 Windows 用户快速上手，项目 `src/scripts/` 目录下提供了两个一键批处理脚本，支持环境配置与控制面板的快速启动：

1. **环境配置**：**在已安装 [uv](https://github.com/astral-sh/uv) 的前提下**，**双击**运行 [src/scripts/_setup_env.bat](src/scripts/_setup_env.bat)。它将自动同步项目依赖（`uv sync`）并引导检查/创建本地 `.env` 环境变量配置文件（**注意**：OpenCode Agent 智能体设置与本地 `.env` 环境变量都分别需要配置，其中的 API Key 等具体配置内容仍需手动填写，具体可参考 [环境准备与配置详解](docs/lang_CN/env_setup.md)）。
2. **启动 GUI**：**双击**运行 [src/scripts/_launch_gui.bat](src/scripts/_launch_gui.bat)。它将自动运行后台服务并在默认浏览器中拉起控制面板（默认地址为 [http://127.0.0.1:7860](http://127.0.0.1:7860)）。在关闭该批处理窗口或在终端按 `Ctrl+C` 时，会自动清理相关的所有 Python/Gradio 后台进程。

---

## 🚀 基础环境配置 (通用)

若您不是 Windows 用户，或者希望手动配置环境，请按以下步骤操作：

1. **准备工具**：安装 [uv](https://github.com/astral-sh/uv) (Python 包管理工具) 和 [OpenCode](https://opencode.ai/)。
2. **配置 OpenCode 与 Agent 模型**：运行 `opencode auth login` 或使用 `/connect` 命令登录并添加 API 提供商密钥，并在 [.opencode/opencode.json](.opencode/opencode.json) 中为每个 Agent 配置合适的模型。
3. **添加虚拟环境**：在项目根目录下运行 `uv sync` 自动创建虚拟环境并同步项目依赖。
4. **配置环境变量**：复制并配置本地 `.env` 文件（用于配置 Embedding 模型的 API 环境变量，参考 [.env.example](.env.example)）。

> 💡 **详细的安装、配置指南请参考**：[环境准备与配置详解](docs/lang_CN/env_setup.md)

---

## 🖥️ 启动控制面板 GUI (推荐)

项目已提供 **Gradio Web 控制面板**（位于 [src/GUI](src/GUI)），当前支持可视化项目初始化、资料上传、RAG 构建、环境检查、完整 LCA 执行和结构化结果查看。

### 启动方式 (通用)

在项目根目录下，于终端执行以下命令：
```bash
uv run python src/GUI/main.py
```
启动成功后，在浏览器中手动访问 [http://127.0.0.1:7860](http://127.0.0.1:7860)。

### 2. 使用步骤说明

在使用控制面板时，请遵循以下流程：
1. **准备工作**：
   - **⚠️ 必须开启 openLCA 桌面客户端，并确保已启用 IPC Server（默认端口 8080）**。
   - 准备您的参考文档（如环评报告等 PDF/Word 文档）。历史计划模板仍位于 [src/GUI/ui/assets/template/plan.md](src/GUI/ui/assets/template/plan.md)。
2. **初始化项目与上传文档**：
   - 在控制面板左侧边栏的 **“文件交换区”** 直接上传准备好的参考资料（如环评报告等）与参考数据文件（**无需手动放置在后台文件夹中**）。
   - 切换到控制面板的 **“项目初始化”** 面板，检查 openLCA 连接状态。
   - 点击 **“构建 RAG 数据库”**（或清理后重新构建）导入并解析上传的参考文档。
3. **制定与修改计划**：
   - 在 **“制定计划”** 栏下填写/调整计划需求，并点击执行生成。
   - 如有需要，可在 **“修改计划”** 栏提供反馈意见让 Agent 自动调整。
4. **设计与导入清单**：
   - 确认生成的执行计划无误后，启动 **“设计与导入清单”**，Agent 将会自动生成 JSON 实体并将其通过 IPC 批量导入到已打开的 openLCA 客户端中。

> 💡 **更详细的 GUI 结构与开发扩展说明**，请参见：[GUI 模块说明文档](src/GUI/README.md)

---

## 🛠️ 辅助功能（手动/命令行执行）

在无图形界面（GUI）环境下或开发调试时，核心交互逻辑为：**先将输入文件放入 `workspace/inputs/`（参考文件放在 `workspace/inputs/references/file/`、数据文件放在 `workspace/inputs/references/data/`），再运行对应的 `opencode` 指令执行任务**。

### 1. 辅助准备脚本
```bash
# 初始化（默认会先清理目录、同步 workspace 数据，再建立 RAG 向量数据库并检测 openLCA 连接）
uv run python src/scripts/initialization/main.py
```

### 2. 核心操作流程
1. **准备/修改文件**：放置原始参考文档到 `workspace/inputs/references/file/`，原始数据到 `workspace/inputs/references/data/`，将计划文件放到 `workspace/inputs/plan.md`。
2. **执行 OpenCode 任务** (支持命令行或 CLI 交互界面) ：
   * **端到端受控执行**：以 `workspace/inputs/plan.md` 作为计划输入，运行 `opencode run --command whole-lca`（或 `/whole-lca`）；系统保存精确预检范围，并在哈希一致时自动完成导入、读回和计算。


> 💡 **关于文件放置路径、人工审核交互及完整调试步骤，请参见**：[手动调试与文件同步指南](docs/lang_CN/manual_debug.md)
