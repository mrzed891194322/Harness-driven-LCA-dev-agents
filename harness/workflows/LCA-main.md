# LCA 主工作流

平台入口加载本文件。阶段细节在 `harness/specs/` 编号包；不要在这里加 schema。

## 运行前清理（由 GUI 或用户完成）

启动前已用 `src/scripts/clean_dir/`（`--preset whole-lca`）清理 `harness/knowledge/`、`workspace` 生成物与 openLCA 前景。保留 `workspace/inputs/plan.md`。用户资料在 `harness/knowledge/`。不要在 agent 内再调 `clean_dir` 或 MCP `cleanup_output`。

## 渐进加载

1. 当前 Agent 是 `major-orchestrator`。计划只来自 `workspace/inputs/plan.md`；资料只来自 `harness/knowledge/`。
2. 启动只读 `harness/specs/public/README.md` 和 `harness/specs/public/references/workflow-runtime-spec.md`。不得预读编号阶段 spec。
3. 写 `workspace/memory/manifest.json`（`status`、`current_stage`、`status_reason`）。可选复制 `harness/specs/public/references/templates/checklist.md`。
4. 每次委派必须明确要求子 Agent 读取本阶段 README/spec 与本次输入路径。子 Agent 不得再委派、不得扫描其他阶段。
5. 进入阶段时才读该阶段 README 及其 spec；完成后不预读下一阶段。

LCA 知识规则由平台按配置加载，需要时读 `harness/rules/lca-knowledge/README.md`。真正调用 openLCA MCP 时再读 `harness/rules/openlca-operation/README.md`。

## 启动门禁 + 三步 LCA

### 01 初始化检查

- 主 Agent 此时完整读取 `harness/specs/01-intake-gate/README.md` 和 `harness/specs/01-intake-gate/references/01-intake-gate-spec.md`。
- 委派任务必须明确要求 `eval-reviewer` 读取上述文件、`workspace/inputs/plan.md` 和 `harness/knowledge/`。不派 `sub-executor`。未通过则写入审查笔记，manifest `failed`，停止。

### 02 前景清单提取

- 主 Agent 此时完整读取 `harness/specs/02-inventory-extraction/README.md` 和 `harness/specs/02-inventory-extraction/references/02-inventory-extraction-spec.md`。
- 委派任务必须明确要求 `sub-executor` 读取上述文件并写出 BOM。
- 委派任务必须明确要求 `eval-reviewer` 读取上述文件并审查 BOM。attempt 1/2 未通过则只把修改意见交给 `sub-executor`；attempt 3 未通过则 `failed`。

### 03 背景数据集映射

- 主 Agent 此时完整读取 `harness/specs/03-dataset-mapping/README.md` 和 `harness/specs/03-dataset-mapping/references/03-dataset-mapping-spec.md`。
- 委派任务必须明确要求 `sub-executor` 读取上述文件，并在调用 MCP 前读取 `harness/rules/openlca-operation/README.md`，写出 mapping 与 LCI。
- 委派任务必须明确要求 `eval-reviewer` 审查映射与 LCI。返工规则同 02。通过前不 import。

### 04 openLCA 建模与报告

- 主 Agent 此时完整读取 `harness/specs/04-openlca-reporting/README.md` 和 `harness/specs/04-openlca-reporting/references/04-openlca-reporting-spec.md`。
- 委派任务必须明确要求 `sub-executor` 读取上述文件和 openLCA 规则，按预检→导入→读回→计算→报告执行，模板为 `harness/specs/04-openlca-reporting/references/templates/lca_report.md`。
- 委派任务必须明确要求 `eval-reviewer` 审查 `lca_report.md`。通过则 `completed`；工具失败或三次审查失败则 `failed`。均须非空 `status_reason`。

## 停止

运行中不得征求用户建模决定，不得设 `awaiting_confirmation`。可留档的选择由执行方写入产物。终止只有 `completed` 和 `failed`。
