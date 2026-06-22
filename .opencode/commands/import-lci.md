---
description: 批量导入 src/LCI 中的 Flows、Processes 和 Product Systems JSON 配置文件到 openLCA 数据库
agent: subagents/tools/doc-handler
---

**前置检查**：
请确保本地已开启 openLCA 桌面客户端并启动了 IPC Server 服务（默认端口 8080）。

**任务执行**：
请作为 `doc-handler` 智能体执行以下批量导入任务：

运行以下导入命令：
```bash
uv run python .opencode/skills/control-openlca/assets/import_from_json/main.py src/LCI
```

*注：脚本会自动检测 `src/LCI` 中的子目录结构（flows -> processes -> product_systems）并按依赖顺序导入，且会自动将当前工作目录名称作为分类目录导入 openLCA。如果用户在调用本命令时显式提供了自定义的 `--host` 或 `--port` 参数，请对应调整追加到运行命令末尾。*

**任务结束**：
待导入执行完毕后，你只需向用户汇报导入结果（如成功导入/覆盖的数量及任何异常报错），并立即终止当前会话。严禁执行任何多余工作（包括但不限于调用 `main-workflow`、其它技能或创建新的任务）。
如果是 `major-orchestrator` 正在读取本命令，请严格执行“触发情形3”，不启动其他工作流并直接结束。
