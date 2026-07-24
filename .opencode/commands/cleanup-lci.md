---
description: 删除 openLCA 活动数据库中当前项目分类下的所有前景 LCI 实体（ProductSystem、Process、Flow），并清理 workspace 生成文件
agent: major-orchestrator
---

**任务执行**：

## 第一部分：清理 openLCA 数据库

1. 以预览模式运行清理工具，列出待删除实体：
   `uv run python harness/tools/control_openlca/cleanup_output/main.py`
2. 将预览结果呈现给用户，等待用户确认；
3. 用户确认后，执行删除：
   `uv run python harness/tools/control_openlca/cleanup_output/main.py --yes`
4. 报告 openLCA 清理结果。

## 第二部分：清理 workspace 生成文件

5. 以演练模式运行 workspace 清理脚本，列出待删除文件：
   `uv run python src/scripts/clean_dir/main.py --dry-run --target workspace`
6. 将预览结果呈现给用户，等待用户确认；
7. 用户确认后，执行删除：
   `uv run python src/scripts/clean_dir/main.py --yes --target workspace`
8. 汇总两部分清理结果并结束。
