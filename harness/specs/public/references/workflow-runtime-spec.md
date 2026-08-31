# Whole-LCA 运行说明

工作流编成四个编号阶段，语义上是 **1 个启动门禁 + 3 个 LCA 业务步**。没有 JSON Schema 门禁，也没有阶段 `validation.py`。

## 阶段

1. `01-intake-gate`：初始化检查。不是 ISO LCA 步骤。主编排只派 `eval-reviewer`，不派 `sub-executor`。一次未通过即 `failed`。
2. `02-inventory-extraction`：从用户资料提取前景 BOM。
3. `03-dataset-mapping`：把 BOM 映射到活动库 Process/Flow/Provider，并写出可导入 LCI。通过前不 import。
4. `04-openlca-reporting`：预检、导入、读回、LCIA、写报告。

`08-lca-revise-workflow` 不是第 5 步，只是 revise 外壳；通过后复用 01–04。

进入某阶段时才读该阶段 README/spec；启动只读本文，不预读编号包。

## 路径

- 输入：`workspace/inputs/plan.md`（revise 另加 `workspace/inputs/revise.md`）
- 知识：`harness/knowledge/`
- 状态：`workspace/memory/manifest.json`、`workspace/memory/reviews/`；可选 `checklist.md`
- 前景产物：`workspace/outputs/inventory/extracted-bom.json`、`extracted-bom.md`、`process-mapping.json`。GUI「工作细节」只渲染两份 JSON，不读 `.md`。
- LCI：`workspace/outputs/LCI/`（`flows/`、`processes/`、`product_systems/`，外加 `human_readable_mapping.md`）
- 报告：`workspace/outputs/reports/lca_report.md`；MCP 原始返回原样落在 `reports/` 即可

## 循环

01：主编排委派 `eval-reviewer` 读计划与知识目录。`passed` 进入 02；`failed` 停止。

02–04：每阶段先派 `sub-executor` 产出，再派 `eval-reviewer` 审查。未通过且未满 3 次则定向返工；第 3 次仍失败则 `failed`。04 通过后 `completed`。

审查笔记写 `workspace/memory/reviews/<stage>-<n>.md`，写明 `passed` 或 `failed`、摘要、要改什么。不必使用 issue ID 正则。

## 状态

`manifest.json` 至少包含：

- `status`：`running` | `failed` | `completed`
- `current_stage`：当前阶段 id 或 `null`
- `status_reason`：终止时非空说明

不要设 `needs_input` / `awaiting_confirmation`。运行中不征求用户建模决定。可留档的匹配由执行方自行选择并写入 BOM/映射/报告。

首次调用 openLCA MCP 前，由 **该步的 `sub-executor`** 调用 `health_check`；失败则 `failed` 并写明原因。

示例见 `references/examples/`。
