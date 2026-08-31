---
description: 删除 openLCA 活动数据库中当前项目分类下的所有前景 LCI 实体（ProductSystem、Process、Flow），并清理 workspace 生成文件
agent: major-orchestrator
---

**任务执行**：

## 第一部分：清理 openLCA 数据库

1. 读取 `harness/rules/tools/control_openlca.md`。
2. 调用 openLCA MCP `health_check`。
3. 调用 MCP `cleanup_output`，`confirm=false` 预览待删除实体，将结果呈现给用户并等待确认。
4. 用户确认后，调用 MCP `cleanup_output`，`confirm=true` 执行删除。
5. 报告 openLCA 清理结果。

## 第二部分：清理 workspace 生成文件

6. 以演练模式运行 workspace 清理脚本，列出待删除文件：
   `uv run python src/scripts/clean_dir/main.py --dry-run --target workspace`
7. 将预览结果呈现给用户，等待用户确认；
8. 用户确认后，执行删除：
   `uv run python src/scripts/clean_dir/main.py --yes --target workspace`
9. 汇总两部分清理结果并结束。
