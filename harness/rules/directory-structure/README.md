# 项目目录规范与文件位置约定 (Directory Structure README)

本规范规定了项目开发及智能体（Agent）执行任务时所涉及的目录操作权限及参考指南。

## 1. 文件操作安全边界 (File Operations)

* **允许文件操作的目录**：运行产物的新建、修改、写入、删除全部限定在 **`workspace/`**。用户参考资料由 GUI 或用户写入 **`harness/knowledge/`**（扁平目录，唯一落点）。严禁在上述目录以外（包括项目外部，如系统临时文件夹等）进行任何写操作。Agent 不得修改 `harness/rules/`、`harness/specs/`、`harness/tools/`。

## 2. 资源读取边界 (Resource Reading)

* **允许读取的目录**：**`harness/`** 目录。智能体及脚本从此目录读取规范、工具方法与用户资料。除 `harness/knowledge/` 中的用户文件外，严禁向 `harness/` 写入或修改文件。

## 3. 按需查阅详细参考规范 (References)

在需要查阅特定目录的命名约定、内部结构或模块职责时，请根据具体内容按需查看 **`references/`** 目录下的相关规范：

* **[global-structure.md](references/global-structure.md)**：用于查询全局根目录结构（如根目录下的通用约定、Python 虚拟环境与 `uv` 依赖管理规范）。
* **[harness-structure.md](references/harness-structure.md)**：用于查询 `harness/` 目录（包括 `knowledge/`、`tools/`、`rules/`、`specs/`）与 `src/GUI/`、`src/scripts/` 的目录结构以及各模块的职责定义。
* **[workspace-structure.md](references/workspace-structure.md)**：用于查询 `workspace/` 内部子目录（如 `LCI/`、`data/`、`plan/`、`tmp/` 等）的详细划分与文件管理规则。
* **[platform-adapter.md](references/platform-adapter.md)**：四平台在 AI 工具中输入的指令、GUI 内部一行 CLI、MCP 接线与 agent/command 分层核对清单。
