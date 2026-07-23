---
description: 删除 openLCA 活动数据库中当前项目分类下的所有前景 LCI 实体（ProductSystem、Process、Flow）
agent: major-orchestrator
---

**任务执行**：

1. 以预览模式运行清理工具，列出待删除实体：
   `uv run python harness/tools/control_openlca/cleanup_output/main.py`
2. 将预览结果呈现给用户，等待用户确认；
3. 用户确认后，执行删除：
   `uv run python harness/tools/control_openlca/cleanup_output/main.py --yes`
4. 返回删除结果摘要并结束。
