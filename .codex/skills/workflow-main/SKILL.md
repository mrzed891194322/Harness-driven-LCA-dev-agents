---
name: workflow-main
description: 通过分阶段的计划接收、证据检索、最多三次 LCI 审查循环、openLCA 写入预检、自动导入回读、LCIA 计算及结果归档，来无人值守地执行已有的 LCA 执行计划（plan.md）。适用于本仓库中的 whole-lca 或端到端 plan-to-LCIA 运行。
---

# 全生命周期评价（Whole-LCA）主工作流

将此技能作为 Codex 平台适配器使用。将 `harness/specs/public/` 与 `harness/specs/01-*` 至 `07-*` 视为运行契约、阶段规则和结果结构的唯一来源；不要重述或弱化其中的内容。

## 启动与渐进式加载

1. 在读取计划之前，运行 `uv run python src/scripts/file_sync/main.py --direction upload-to-work`，将参考资料同步到 harness 知识源。当环境需要时，可使用可写的临时 uv 缓存。
2. 仅使用 `workspace/inputs/plan.md` 作为计划输入。如果当前活动 Agent 不是 `major-orchestrator`，只生成一个该 Agent，并传递 `platform=codex`、计划路径及执行下述资源加载顺序的要求；根线程不执行业务阶段。
3. `major-orchestrator` 启动时只读取 `harness/specs/public/README.md` 和 `harness/specs/public/references/workflow-runtime-spec.md`，不得预读任何编号阶段规范。
4. 创建 manifest 前读取 `harness/specs/public/references/schemas/workflow-manifest.schema.json`；以后只在即将写某类对象前读取对应的 `harness/specs/public/references/schemas/stage.schema.json`、`harness/specs/public/references/schemas/handoff.schema.json` 或 `harness/specs/public/references/schemas/review.schema.json`。
5. 每次委派明确列出当前阶段、此时允许读取的文件、输入产物及哈希、允许的输出、关联 issue ID 或 `preflight_hash`。子 Agent 不得自行扫描其他阶段。
6. 进入一个阶段时，主 Agent 才读取该阶段 README 及其路由的 spec；当前子任务需要同一规范时，在该次委派中再要求对应子 Agent 读取。完成并持久化当前阶段后，不预读下一阶段。

知识检索与 openLCA 规则在 Codex 中均不全局加载。只有当前检索或审查任务需要核对知识来源时才读取 `harness/rules/knowledge-retrieval/README.md`；只有确实要调用 openLCA MCP 时才读取 `harness/rules/openlca-operation/README.md`。

## 七阶段执行

### 01 计划质量门禁

- 主 Agent 此时完整读取 `harness/specs/01-plan-quality-gate/README.md` 和 `harness/specs/01-plan-quality-gate/references/01-plan-quality-gate-spec.md`，并在写 handoff/review/stage 前读取对应 schema。
- 调用 `eval-reviewer` 时，委派任务必须明确要求它在审查前完整读取上述两个第 01 阶段文件和 `harness/specs/public/references/schemas/review.schema.json`；只交付计划及当前阶段输入，阻断时持久化结果并停止。

### 02 证据检索

- 计划通过后，主 Agent 才完整读取 `harness/specs/02-evidence-retrieval/README.md` 和 `harness/specs/02-evidence-retrieval/references/02-evidence-retrieval-spec.md`。
- 从计划提取 `GAP-*` 和背景映射任务后调用 `sub-executor`；委派任务必须明确要求它在检索前完整读取上述两个第 02 阶段文件和知识检索规则。只有 MCP 暴露的参数或错误不足以解释当前调用时，才在首次相关调用前读取 `harness/tools/query_rag/README.md`。只有任务包含 openLCA 候选查询时，才要求它在调用 MCP 前读取 openLCA 规则。

### 03 LCI 制定

- 第 02 阶段通过后，主 Agent 才完整读取 `harness/specs/03-lci-construction/README.md` 和 `harness/specs/03-lci-construction/references/03-lci-construction-spec.md`。
- 调用 `sub-executor` 时，委派任务必须明确要求它在制定 LCI 前完整读取上述两个第 03 阶段文件；只交付已通过计划、当前检索 handoff 和允许生成的 LCI 产物范围。

### 04 LCI 质量评估

- LCI 形成后，主 Agent 才完整读取 `harness/specs/04-lci-quality-evaluation/README.md` 和 `harness/specs/04-lci-quality-evaluation/references/04-lci-quality-evaluation-spec.md`。
- 调用 `eval-reviewer` 时，委派任务必须明确要求它在审查前完整读取上述两个第 04 阶段文件和 review schema；只交付计划目标、第 02/03 阶段证据、当前 LCI 与历史未解决 issue。需要核对知识来源时才要求读取知识检索规则；实际调用 openLCA MCP 核验时才读取 openLCA 规则。
- attempt 1/2 未通过时，调用 `sub-executor` 并明确要求它此时完整读取第 03 阶段和第 04 阶段的 README/spec，只交付关联 issue ID 与受影响产物进行定向修正；attempt 3 未通过时置为 `needs_review`，不得继续。

### 05 openLCA 写入预检

- LCI 审查通过后，主 Agent 才完整读取 `harness/specs/05-openlca-preflight-confirmation/README.md` 和 `harness/specs/05-openlca-preflight-confirmation/references/05-openlca-preflight-confirmation-spec.md`。
- 调用 `sub-executor` 时，委派任务必须明确要求它在预检前完整读取上述两个第 05 阶段文件和 openLCA 规则，再调用 `preflight_import_lci`。只有 MCP 暴露的 schema 或错误不足以解释当前调用时，才在调用前补读 `harness/tools/control_openlca/README.md`。保存活动数据库、目标分类、创建/更新/删除范围和 `preflight_hash`，不得执行导入或等待确认。

### 06 openLCA 导入与读回

- 预检通过后，主 Agent 才完整读取 `harness/specs/06-openlca-import-readback/README.md` 和 `harness/specs/06-openlca-import-readback/references/06-openlca-import-readback-spec.md`，并立即发起下一次委派。
- 调用 `sub-executor` 时，委派任务必须明确要求它在导入前完整读取上述两个第 06 阶段文件和 openLCA 规则；在生成对应结果前分别读取 `harness/specs/public/references/schemas/import-report.schema.json` 和 `harness/specs/public/references/schemas/model-graph.schema.json`。只把当前成功预检的范围与哈希交给它调用 `import_lci` 和 `get_model_graph`。
- `import_lci` 重新预检后若范围或哈希变化，不得写入；保存结构化失败证据并将运行置为 `failed`。

### 07 LCIA 计算与报告

- 第 06 阶段通过后，主 Agent 才完整读取 `harness/specs/07-lcia-calculation-reporting/README.md` 和 `harness/specs/07-lcia-calculation-reporting/references/07-lcia-calculation-reporting-spec.md`。
- 调用 `sub-executor` 时，委派任务必须明确要求它在计算前完整读取上述两个第 07 阶段文件和 openLCA 规则；在保存原始计算结果、计算清单和最终报告前，依次读取 `harness/specs/public/references/schemas/raw-lcia-results.schema.json`、`harness/specs/public/references/schemas/calculation-manifest.schema.json` 和 `harness/specs/public/references/templates/lca_report.md`，不得提前加载。
- 验收非空结果、模型连接、资源释放和全部必需产物后，主 Agent 才决定终止状态。

## 无人值守中继

`major-orchestrator` 仅可生成 `sub-executor` 和 `eval-reviewer`。等待其返回结果。

- 如果返回 `needs_input`、`needs_review` 或 `failed`，则保留已记录的状态并报告确切问题。
- 运行启动即授权在当前预检范围与哈希完全一致时执行导入。预检通过后由同一编排器立即继续第 06 阶段，不得返回 `awaiting_confirmation` 或请求用户额外确认。
- `import_lci` 会重新预检。任何范围或哈希变化都必须拒绝写入、保存结构化失败证据并结束运行，不得等待用户输入。

## 强制完成

- 将每个阶段/审查/交接都保存到 `workspace/memory/` 的固定结构中；同一次运行内不要覆盖历史记录，不生成运行 ID 或运行 ID 目录。
- 严格按 `01-plan-quality-gate` 至 `07-lcia-calculation-reporting` 的顺序推进；子 Agent 只读取本次交接列出的相关记忆，只有主 Agent 写入运行状态与历史。
- 在第三次 LCI 审查失败后停止，不再进行第四次自动修复。
- 要求达到以下条件后才能标记为 `completed`：零导入失败、无断裂的模型链接、非空的原始 LCIA 结果、已释放的计算资源，以及所有必需的结果产物。
- 工作流产物直接保存在 `workspace/memory/`、`workspace/outputs/LCI/` 和 `workspace/outputs/reports/`，返回后不执行反向文件同步。
