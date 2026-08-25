# 后端业务逻辑层 (`src/GUI/functions`)

本目录包含后台命令的执行流程、CLI 命令编排器以及供 GUI 使用的底层工具方法。

## 目录架构设计

为保持代码的模块化和清晰度，本层目录遵循严格的包装（Packaging）结构规范：

- **统一的功能入口 (`main.py`)**：在每个功能子目录根下，必须且只能包含**一个**统一的业务入口流程函数 `main()`。
- **私有实现包 (`private_utils/`)**：所有该功能专用的、不对外公开的辅助函数 and 脚本文件都必须放在该子目录下的 `private_utils/` 文件夹中。
- **公共/共享工具函数 (`utils/`)**：能够被多个功能模块或 UI 层直接调用的通用辅助脚本，统一放置在公用的 `functions/utils/` 目录下。

---

## 功能模块目录指引

### 1. 公共工具库 (`functions/utils/`)
包含可被所有特征模块全局调用的公共工具：
- **[process_manager.py](utils/process_manager.py)**：负责跟踪当前活动命令执行子进程，并提供强制杀死底层任务进程树的统一实现。
- **[log_exporter.py](utils/log_exporter.py)**：管理命令输出日志存放目录、路径规则以及将 stdout 实时追加写入本地日志文件。
  - **[path_utils.py](utils/path_utils.py)**：负责自动定位项目/仓库根目录（通过寻找包含 `pyproject.toml`、`.opencode` 或 `.git` 的父目录）。
- **命令执行子包 (`functions/utils/executor/`)**：负责按所选 harness CLI 运行 whole-lca / revise-lca，以及其它 OpenCode 命令。
  - **功能入口**：[main.py](utils/executor/main.py) 中的 `main` 函数。
  - **私有辅助包 (`private_utils/`)**：
    - `executor_utils.py`：流式捕获进程输出、过滤 ANSI 颜色与特殊控制符，并将日志以符合 Gradio 页面组件渲染的方式输出。
- **文件处理子包 (`functions/utils/file_loader/`)**：承担不同类型的文件读取、保存以及 LCA 计划模板解析与填写值加载的工作。
  - **功能入口**：[main.py](utils/file_loader/main.py) 中的 `main` 函数。
  - **私有辅助包 (`private_utils/`)**：
    - `template_parser.py`：解析 plan.md 表单模板，拆分成静态 markdown 与用户输入区。
    - `toc_extractor.py`：保留给旧文件加载入口的 HTML 目录兼容工具；当前文档型
      Tab 的目录与锚点统一由 `MarkdownDocumentView` 使用 `plan_editor.py` 生成。
    - `value_handler.py`：读取已有的 markdown 计划文件回填到表单，或将表单内容保存合成到模板中。

### 2. 设置模块 (`functions/settings/`)
提供设置页门禁探测与参考资料写入：
- **[check_status.py](settings/check_status.py)**：依次探测 AI Agent CLI 与 openLCA，供「开始初始化检查」使用。
- **[settings.py](settings/settings.py)**：读写 `.env` 中的 `HARNESS_AGENT` 与端口配置。
- **私有辅助包 (`private_utils/`)**：
  - `file_handler.py`：将左侧上传的材料/数据文件写入 `harness/knowledge/`。

环境和 openLCA 不再捆绑为单一门禁。「开始初始化检查」依次探测 AI Agent CLI
与 openLCA；两项全部通过后才解锁“执行LCA计划”。
Agent 页的单项检查只弹对话框，不解锁执行。选择的 Agent 写入
`.env` 的 `HARNESS_AGENT`。

### 3. LCA 工作流结果模块

- `lca_run.py`：识别本次 whole-lca v2 或 revise-lca v1 manifest，区分完成与
  提前中止，并从阶段、审查及工具报告中聚合失败原因。
- `plan_editor.py`：仅用 `PLAN_TEXTBOX` 注释识别其后的“用户填写内容区”，
  并把正文拆成原位交替的 Markdown/Textbox；无 front matter、任意 front matter
  和纯 Markdown 均可解析，已有 front matter 原样保留且不校验类型或版本。
  同时为所有文档型 Tab 生成可配置标题层级的 Markdown 目录和匹配锚点。
  上传内容只在内存暂存；计划执行时原子写入唯一计划路径，改进执行时原子写入
  `workspace/inputs/revise.md`；其他文档视图输入不写入 workspace。
