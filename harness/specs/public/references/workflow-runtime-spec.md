# Whole-LCA 运行说明

薄路径与 `manifest.json` 字段。阶段循环以 `harness/workflows/` 的 YAML 为准。没有 JSON Schema 门禁，也没有阶段 `validation.py`。

## 路径

- 输入：`workspace/inputs/plan.md`（revise 另加 `workspace/inputs/revise.md`）
- 知识：`harness/knowledge/`
- 状态：`workspace/memory/manifest.json`、`workspace/memory/reviews/`、`workspace/memory/handoffs/`
- 前景产物：`workspace/outputs/inventory/extracted-bom.json`、`extracted-bom.md`、`process-mapping.json`
- LCI：`workspace/outputs/LCI/`（`flows/`、`processes/`、`product_systems/`，外加 `human_readable_mapping.md`）
- 报告：`workspace/outputs/reports/lca_report.md`

## 状态

`manifest.json` 至少包含：

- `status`：`running` | `failed` | `completed`
- `current_stage`：当前阶段 id 或 `null`
- `status_reason`：终止时非空说明

不要设等待用户确认的状态。

示例见 `references/examples/`。
