# LCA 修订主工作流

本工作流由 `/revise-lca` 与 `$revise-lca` 加载。修订专属语义只存在于
`harness/specs/08-lca-revise-workflow/`；公共证据对象和阶段 02–07 的业务契约继续使用
`harness/specs/public/` 与对应编号阶段包，不在本文件重定义 schema。

## 运行前基线准备

1. 运行 `uv run python harness/specs/08-lca-revise-workflow/references/scripts/baseline.py snapshot --yes`；失败时保留旧 workspace/openLCA 并停止。
2. 读取 `harness/rules/openlca-operation/README.md`；调用 MCP `health_check`，再以 `cleanup_output` 预览（`confirm=false`）后立即执行删除（`confirm=true`）；失败时不得激活快照。
3. 运行 `baseline.py activate --yes`；失败时保留旧 canonical 结果并停止。

## 渐进式资源加载

1. 确认当前 Agent 是 `major-orchestrator`，固定意见输入为
   `workspace/inputs/revise.md`。用户参考资料只从 `harness/knowledge/` 读取，不得把 `workspace` 其他目录当作知识库。
2. 基线激活后只读取 `harness/specs/08-lca-revise-workflow/README.md`、
   `harness/specs/08-lca-revise-workflow/references/revise-lca-spec.md`、
   `harness/specs/public/README.md` 和
   `harness/specs/public/references/workflow-runtime-spec.md`；不得预读编号阶段规范。
3. 写 revision brief 和 manifest 前分别读取
   `harness/specs/08-lca-revise-workflow/references/schemas/` 中的对应 schema；
   写 stage、handoff、review 前按需读取 public 中的对应 schema。
4. 每次委派列出当前阶段、允许读取的 baseline/current memory、输入产物路径、
   允许输出、`REV-*`/issue ID 或 `import_scope`。子 Agent 不得扫描其他阶段。
5. 进入 02–07 的某阶段时才读取该阶段 README/spec，完成并持久化后不预读下一阶段。

OpenCode 已全局加载 LCA 知识规则；Codex 仅在当前检索或审查需要时加载
`harness/rules/lca-knowledge/README.md`。两平台都只有实际调用 openLCA
MCP 时才读取 `harness/rules/openlca-operation/README.md`。

## 01 修订基线与计划门禁

- 主 Agent 按
  `harness/specs/08-lca-revise-workflow/references/revise-lca-spec.md`
  核对已激活的 `workspace/memory/baseline/` 与当前
  `workspace/inputs/revise.md`，生成 `revision-brief.json` 和候选计划。
- 调用 `eval-reviewer` 时，委派任务必须明确要求它完整读取
  `harness/specs/08-lca-revise-workflow/README.md`、该包的 spec/revision brief
  schema、01 计划质量门禁 README/spec 和 public review schema；
  只交付意见、baseline、revision brief 与候选计划。
- 审查通过后主 Agent原子覆盖 `workspace/inputs/plan.md`，把新旧计划及意见的
  路径与修订关系写入 revise manifest。未通过则持久化证据并停止。

## 02 证据检索

- 此时才完整读取 `harness/specs/02-evidence-retrieval/README.md` 和对应 spec。
- 调用 `sub-executor` 时，委派任务必须明确要求它读取上述文件，只交付修订后计划、
  revision brief、允许的 baseline memory 和检索任务。旧 memory 推断仅作线索；
  关键事实必须回读原始来源。需要 openLCA 候选时才加载 openLCA 规则。

## 03 LCI 完整重建

- 此时才完整读取 `harness/specs/03-lci-construction/README.md` 和对应 spec。
- 调用 `sub-executor` 时，委派任务必须明确要求它读取上述文件，并根据修订后计划、
  检索证据、revision brief 和 baseline LCI 生成完整 canonical LCI。不得只提交
  无法独立预检的差量。返回前运行第 03 阶段 validator。

## 04 LCI 质量评估

- 此时才完整读取 `harness/specs/04-lci-quality-evaluation/README.md` 和对应 spec。
- 调用 `eval-reviewer` 时，委派任务必须明确要求它读取上述文件与 review schema，
  核对 03 validator、全部 `REV-*`、baseline 差异和新 LCI。
- attempt 1/2 未通过时，调用 `sub-executor` 并明确要求它读取 03/04 README/spec，
  只修关联 issue；attempt 3 未通过时置为 `failed` 并停止。

## 05 openLCA 写入预检

- 此时才完整读取 `harness/specs/05-openlca-preflight-confirmation/README.md` 和对应 spec。
- 调用 `sub-executor` 时，委派任务必须明确要求它读取上述文件和 openLCA 规则，
  使用明确数据库运行 `preflight_import_lci`，保存完整 `import_scope`，
  不执行导入或等待确认。

## 06 openLCA 导入与读回

- 此时才完整读取 `harness/specs/06-openlca-import-readback/README.md` 和对应 spec。
- 调用 `sub-executor` 时，委派任务必须明确要求它读取上述文件、openLCA 规则及三个
  结果 schema，只使用紧邻的成功预检 `import_scope` 调用 `import_lci` 并读回模型图。
- 超时、范围变化、部分失败和验证失败完全按 06 规范停止，不得重试写操作或
  使用 legacy CLI。

## 07 LCIA 重算与报告覆盖

- 此时才完整读取 `harness/specs/07-lcia-calculation-reporting/README.md` 和对应 spec。
- 调用 `sub-executor` 时，委派任务必须明确要求它读取上述文件、openLCA 规则、
  raw/calculation schema、07 报告模板，以及
  `harness/specs/08-lca-revise-workflow/references/templates/revision-report-sections.md`。
- 保存全部 raw、计算清单和带修订三节的新 `lca_report.md` 后运行 07 validator。
  通过后再运行
  `harness/specs/08-lca-revise-workflow/references/scripts/validation.py`。
  报告中的旧新数值差异必须回链双方 raw 文件路径；无法比较时明确说明。

## 完成与停止

- 当前运行的 manifest、stage、review、handoff 写入 `workspace/memory/`；baseline
  只读且不得覆盖。只有主 Agent 持久化运行状态。
- 只有全部阶段通过、导入零失败、模型无断链、LCIA 非空且资源释放、报告已覆盖，
  且每个 `REV-*` 均有实施或明确未实施结论时才能标记 `completed`。
- `failed` 必须保存非空 `status_reason`（停止阶段、具体原因、issue ID 或路径）后停止。`completed` 也必须写入完成依据。不得征求用户建模决定。
