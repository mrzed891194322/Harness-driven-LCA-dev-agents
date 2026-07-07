# 项目目录规范与文件位置约定 (Directory Structure README)

本规范规定了项目开发及智能体（Agent）执行任务时所涉及的目录操作权限及参考指南。

## 1. 文件操作安全边界 (File Operations)

* **允许文件操作的目录**：所有在运行和开发过程中需要进行新建、修改、写入、删除等文件操作的场景，全部限定在 **`workspace/`** 目录。严禁在此目录以外（包括项目外部，如系统临时文件夹等）进行任何写操作。

## 2. 资源读取边界 (Resource Reading)

* **允许读取的目录**：**`harness/`** 目录。智能体及脚本仅可从此目录读取项目知识、技术规范与工具方法，除规则或知识显式更新外，严禁向此目录写入或修改文件。

## 3. 按需查阅详细参考规范 (References)

在需要查阅特定目录的命名约定、内部结构或模块职责时，请根据具体内容按需查看 **`references/`** 目录下的相关规范：

* **[global-structure.md](references/global-structure.md)**：用于查询全局根目录结构（如根目录下的通用约定、Python 虚拟环境与 `uv` 依赖管理规范）。
* **[harness-structure.md](references/harness-structure.md)**：用于查询 `harness/` 目录（包括 `knowledge/`、`tools/`、`rules/`、`specs/`）与 `GUI/`、`scripts/` 的目录结构以及各模块的职责定义。
* **[workspace-structure.md](references/workspace-structure.md)**：用于查询 `workspace/` 内部子目录（如 `LCI/`、`data/`、`plan/`、`tmp/` 等）的详细划分与文件管理规则。
