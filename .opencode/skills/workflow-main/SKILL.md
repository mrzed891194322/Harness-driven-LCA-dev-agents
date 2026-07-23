---
name: workflow-main
description: 从既有 plan.md 执行带计划门禁、证据检索、三轮 LCI 审查、openLCA 写入预检、自动导入读回、LCIA 计算和结果归档的无人值守 whole-lca 工作流时使用。
---

# Whole-LCA 主工作流

本 skill 是 OpenCode 平台适配层。共享状态机和产物契约只存在于 `harness/specs/public/`，阶段规则只存在于 `harness/specs/01-*` 至 `07-*`；不要在本文件中重定义 schema。

## 渐进式资源加载

1. 确认当前 Agent 是 `major-orchestrator`，并只使用 `workspace/inputs/plan.md` 作为计划输入。
2. 启动时只读取 `harness/specs/public/README.md` 和 `harness/specs/public/references/workflow-runtime-spec.md`。不得在此时读取任何编号阶段规范。
3. 创建 manifest 前读取 `harness/specs/public/references/schemas/workflow-manifest.schema.json`。以后只在即将写某类对象前读取对应 schema：stage 读取 `harness/specs/public/references/schemas/stage.schema.json`，handoff 读取 `harness/specs/public/references/schemas/handoff.schema.json`，review 读取 `harness/specs/public/references/schemas/review.schema.json`。
4. 每次委派必须明确列出当前阶段、此时允许读取的文件、输入产物及哈希、允许的输出、关联 issue ID 或 `preflight_hash`。子 Agent 不得自行扫描其他阶段。
5. 进入一个阶段时，主 Agent 才读取该阶段的 README 及其路由的 spec；当前任务需要同一规范的子 Agent，在该次委派中再被明确要求读取。完成阶段并持久化证据后，不预读下一阶段。

OpenCode 已通过 `.opencode/opencode.json` 全局加载 `harness/rules/knowledge-retrieval/README.md`，不要重复加载。`harness/rules/openlca-operation/README.md` 不属于全局指令，只能在某次任务确实要调用 openLCA MCP 时按需读取。

## 七阶段执行

### 01 计划质量门禁

- 主 Agent 此时完整读取 `harness/specs/01-plan-quality-gate/README.md` 和 `harness/specs/01-plan-quality-gate/references/01-plan-quality-gate-spec.md`，并在写 handoff/review/stage 前读取对应 schema。
- 调用 `eval-reviewer` 时，委派任务必须明确要求它在审查前完整读取上述两个第 01 阶段文件和 `harness/specs/public/references/schemas/review.schema.json`；只交付计划及当前阶段输入，阻断时持久化结果并停止。

### 02 证据检索

- 计划通过后，主 Agent 才完整读取 `harness/specs/02-evidence-retrieval/README.md` 和 `harness/specs/02-evidence-retrieval/references/02-evidence-retrieval-spec.md`。
- 从计划提取 `GAP-*` 和背景映射任务后调用 `sub-executor`；委派任务必须明确要求它在检索前完整读取上述两个第 02 阶段文件。RAG 检索遵守已加载的知识检索规则；只有 MCP 暴露的参数或错误不足以解释当前调用时，才在首次相关调用前读取 `harness/tools/query_rag/README.md`。只有任务包含 openLCA 候选查询时，才要求它在调用 MCP 前读取 `harness/rules/openlca-operation/README.md`。

### 03 LCI 制定

- 第 02 阶段通过后，主 Agent 才完整读取 `harness/specs/03-lci-construction/README.md` 和 `harness/specs/03-lci-construction/references/03-lci-construction-spec.md`。
- 调用 `sub-executor` 时，委派任务必须明确要求它在制定 LCI 前完整读取上述两个第 03 阶段文件；只交付已通过计划、当前检索 handoff 和允许生成的 LCI 产物范围。

### 04 LCI 质量评估

- LCI 形成后，主 Agent 才完整读取 `harness/specs/04-lci-quality-evaluation/README.md` 和 `harness/specs/04-lci-quality-evaluation/references/04-lci-quality-evaluation-spec.md`。
- 调用 `eval-reviewer` 时，委派任务必须明确要求它在审查前完整读取上述两个第 04 阶段文件和 review schema；只交付计划目标、第 02/03 阶段证据、当前 LCI 与历史未解决 issue。核对来源时使用已加载的知识检索规则；只有实际调用 openLCA MCP 核验时才读取 openLCA 规则。
- attempt 1/2 未通过时，调用 `sub-executor` 并明确要求它此时完整读取第 03 阶段和第 04 阶段的 README/spec，只交付关联 issue ID 与受影响产物进行定向修正；attempt 3 未通过时置为 `needs_review`，不得继续。

### 05 openLCA 写入预检

- LCI 审查通过后，主 Agent 才完整读取 `harness/specs/05-openlca-preflight-confirmation/README.md` 和 `harness/specs/05-openlca-preflight-confirmation/references/05-openlca-preflight-confirmation-spec.md`。
- 调用 `sub-executor` 时，委派任务必须明确要求它在预检前完整读取上述两个第 05 阶段文件和 `harness/rules/openlca-operation/README.md`，再调用 `preflight_import_lci`。只有 MCP 暴露的 schema 或错误不足以解释当前调用时，才在调用前补读 `harness/tools/control_openlca/README.md`。保存活动数据库、目标分类、创建/更新/删除范围和 `preflight_hash`，不得执行导入或等待确认。

### 06 openLCA 导入与读回

- 预检通过后，主 Agent 才完整读取 `harness/specs/06-openlca-import-readback/README.md` 和 `harness/specs/06-openlca-import-readback/references/06-openlca-import-readback-spec.md`，并立即发起下一次委派。
- 调用 `sub-executor` 时，委派任务必须明确要求它在导入前完整读取上述两个第 06 阶段文件和 openLCA 规则；在生成对应结果前分别读取 `harness/specs/public/references/schemas/import-report.schema.json` 和 `harness/specs/public/references/schemas/model-graph.schema.json`。只把当前成功预检的范围与哈希交给它调用 `import_lci` 和 `get_model_graph`。
- `import_lci` 重新预检后若范围或哈希变化，不得写入；保存结构化失败证据并将运行置为 `failed`。

### 07 LCIA 计算与报告

- 第 06 阶段通过后，主 Agent 才完整读取 `harness/specs/07-lcia-calculation-reporting/README.md` 和 `harness/specs/07-lcia-calculation-reporting/references/07-lcia-calculation-reporting-spec.md`。
- 调用 `sub-executor` 时，委派任务必须明确要求它在计算前完整读取上述两个第 07 阶段文件和 openLCA 规则；在保存原始计算结果、计算清单和最终报告前，依次读取 `harness/specs/public/references/schemas/raw-lcia-results.schema.json`、`harness/specs/public/references/schemas/calculation-manifest.schema.json` 和 `harness/specs/public/references/templates/lca_report.md`，不得提前加载。
- 验收非空结果、模型连接、资源释放和全部必需产物后，主 Agent 才决定终止状态。

## 证据与停止

- 每次委派前后在 `workspace/memory/` 写 handoff，每个阶段写新 stage 文件；同一次运行内不得覆盖历史记录。
- Reviewer 只读；由主 Agent 持久化其返回的 review。
- 不调用任何既有 Agent。子 Agent 只读取本次交接列出的相关记忆，只有主 Agent 持久化运行状态与历史记录。
- 运行启动即授权在当前预检哈希与范围完全一致时导入；运行中不得设置 `awaiting_confirmation` 或向用户请求额外确认。
- 无部分失败、无断链、非空结果且全部契约通过前，不得标记 `completed`。
