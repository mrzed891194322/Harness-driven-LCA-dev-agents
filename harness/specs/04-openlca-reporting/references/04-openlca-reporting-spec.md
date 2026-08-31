# 04 openLCA 建模与报告

## 谁做

主编排先委派 `sub-executor` 调 MCP 并写报告，再委派 `eval-reviewer`。最多 3 轮（工具写库失败则停止，不要无界重试 `import_lci`）。

## 执行顺序

1. `preflight_import_lci`。记下库名、分类、LCI 目录，把同一范围交给导入。
2. `import_lci`，再 `get_model_graph`。超时只查导入操作状态，不盲目重试写操作。范围若相对预检发生变化则停止。
3. `calculate_product_system`。原始结果原样写入 `workspace/outputs/reports/`。
4. 按 `templates/lca_report.md` 写 `workspace/outputs/reports/lca_report.md`，并写前景清单与数据集映射两节，行能指回 BOM `item_id`。

MCP 报错、空结果或资源未释放时如实返回，不得标 `completed`。不要为通过本阶段再跑一份结果 JSON Schema。

## 审查

Reviewer 读最终报告：是否可读、数值能否指到 raw、限制是否包含地域代理、能否指回 BOM/mapping。通过则主编排将 manifest 置为 `completed`。
