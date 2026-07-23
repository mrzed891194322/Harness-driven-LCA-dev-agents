# 后端业务逻辑层 (`GUI/functions`)

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
- **[path_utils.py](utils/path_utils.py)**：负责自动定位项目/仓库根目录（通过寻找包含 `.opencode` 或 `.git` 的父目录）。
- **命令执行子包 (`functions/utils/executor/`)**：负责运行后台 `opencode` 指令任务。
  - **功能入口**：[main.py](utils/executor/main.py) 中的 `main` 函数。
  - **私有辅助包 (`private_utils/`)**：
    - `executor_utils.py`：流式捕获进程输出、过滤 ANSI 颜色与特殊控制符，并将日志以符合 Gradio 页面组件渲染的方式输出。
- **文件处理子包 (`functions/utils/file_loader/`)**：承担不同类型的文件读取、保存以及 LCA 计划模板解析与填写值加载的工作。
  - **功能入口**：[main.py](utils/file_loader/main.py) 中的 `main` 函数。
  - **私有辅助包 (`private_utils/`)**：
    - `template_parser.py`：解析 plan.md 表单模板，拆分成静态 markdown 与用户输入区。
    - `toc_extractor.py`：扫描计划文件的标题，提取生成带有锚点的 HTML 目录导航。
    - `value_handler.py`：读取已有的 markdown 计划文件回填到表单，或将表单内容保存合成到模板中。

### 2. 项目初始化模块 (`functions/project_init/`)
整合项目启动阶段的资源清理与环境初始化流程：
- **功能入口**：[main.py](project_init/main.py) 中的 `main` 函数。
- **私有辅助包 (`private_utils/`)**：
  - `clean.py`：调用项目清理脚本 `clean_dir.py`。
  - `file_handler.py`：将左侧上传的材料/数据文件提取复制到项目的 `harness/knowledge/inputs/` 目录中。
  - `init_rag.py`：调用 RAG 向量库与模型数据库的本地初始化逻辑。

### 3. 计划制定与执行模块 (`functions/make_plan/`)
负责计划的整合保存与执行流程：
- **功能入口**：[main.py](make_plan/main.py) 中的 `main` 函数。
