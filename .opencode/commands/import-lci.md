---
description: 批量导入 src/LCI 中的 Flows、Processes 和 Product Systems JSON 配置文件到 openLCA 数据库
agent: subagents/tools/doc-handler
---

**前置检查**：
请确保本地已开启 openLCA 桌面客户端并启动了 IPC Server 服务（默认端口 8080）。

**任务执行**：
请作为 `doc-handler` 智能体根据以下批量导入步骤执行任务：

1. **确定任务/项目名称**：
   请根据当前具体的工作任务上下文（如当前要导入的 LCI 项目性质，例如 `gold_plating` 或 `copper_plating` 等，具体由分析 LCI 文件或执行计划得出），确定一个简短且描述性的任务/项目名称（例如：记为 `<TASK_NAME>`）。

2. **依次导入各实体数据**：
   运行以下命令（在末尾加上 `--project <TASK_NAME>` 参数，以确保所有 Flow 和 Process 实体在导入 openLCA 时放在以“时间+项目/任务名”命名的同一个文件夹中）：

   - **导入 Flows 数据**：
     ```bash
     uv run python .opencode/skills/control-openlca/assets/import_from_json/main.py src/LCI/flows --project <TASK_NAME>
     ```

   - **导入 Processes 数据**：
     ```bash
     uv run python .opencode/skills/control-openlca/assets/import_from_json/main.py src/LCI/processes --project <TASK_NAME>
     ```

   - **导入 Product Systems 数据**：
     ```bash
     uv run python .opencode/skills/control-openlca/assets/import_from_json/main.py src/LCI/product_systems --project <TASK_NAME>
     ```

*注：如果用户在调用本命令时显式提供了自定义的 `--host`、`--port` 或项目名称参数，请对应调整追加到运行命令末尾。*

**任务结束**：
待以上所有实体文件导入执行完毕后，你只需向用户汇报各步骤的导入结果（如成功导入的数量及任何异常报错），并立即终止当前会话。严禁执行任何多余工作（包括但不限于调用 `main-workflow`、其它技能或创建新的任务）。
如果是 `major-executor` 正在读取本命令，请严格执行“触发情形3”，不启动其他工作流并直接结束。
