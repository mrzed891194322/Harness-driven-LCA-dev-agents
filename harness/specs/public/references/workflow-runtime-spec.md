# Whole-LCA 运行、状态与证据公共契约

## 1. 状态机

合法 manifest 状态为：运行中 `not_started`、`running`；终止只有 `failed`、`completed`。不得使用 `needs_input` 或 `needs_review`。

执行顺序固定为：

1. `01-plan-quality-gate`：计划质量门禁；
2. `02-evidence-retrieval`：资料与 openLCA 候选检索；
3. `03-lci-construction`：LCI 制定；
4. `04-lci-quality-evaluation`：LCI 质量评估与定向修正；
5. `05-openlca-preflight-confirmation`：openLCA 写入预检（保留既有包名作为兼容标识）；
6. `06-openlca-import-readback`：导入与模型图读回；
7. `07-lcia-calculation-reporting`：LCIA 计算、结果验收与报告。

不得跳过计划审查、LCI 审查或写入预检。启动 whole-LCA 即授权在当前预检范围（库名、分类、LCI 目录）一致时执行导入。本框架无人值守，运行中不得征求用户建模决定，也不得因判断分歧暂停。凡可留档的选择由执行 Agent 自行决定并写入证据。计划缺少第 01 阶段阻断性事实时将运行置为 `failed`，并在 `status_reason` 写明缺哪一项。各阶段的进入、通过和受控停止条件由对应编号规范定义。

所有需要访问 openLCA 的委派在首次相关工具调用前必须调用 `health_check`。该工具在首次
失败后重新建立客户端并重连 3 次，共最多 4 次有界探测。若仍返回 `ok=false`，主 Agent
必须保存完整 attempts 证据、将 manifest 置为 `failed` 并立即停止；不得继续 openLCA
候选查询、预检、导入、读回或计算。后续只读调用发生连接或 timeout 错误时重新执行同一
健康门禁，恢复后才可重试只读调用。`import_lci` 不得因断连盲目重试，仍按第 06 阶段查询
operation journal；计算中断也不得自动重复。

## 2. 固定运行目录

- 运行记忆根目录：`workspace/memory/`。
- LCI 根目录：`workspace/outputs/LCI/`。
- 结果根目录：`workspace/outputs/reports/`。
- 初始化时创建 `manifest.json`，记录计划路径、平台、主 agent、状态和产物索引。
- 同时从 `harness/specs/public/references/templates/checklist.md` 复制
  `workspace/memory/checklist.md`，并在每个阶段结束时更新对应小节。
- 阶段文件写入 `stages/<三位序号>-<stage>.json`；交接写入 `handoffs/<三位序号>-<from>-to-<to>.json`。
- 计划审查固定为 `reviews/plan-review.json`；LCI 审查为 `reviews/lci-review-<attempt>.json`。
- 阶段、审查和交接记录一经写入不得覆盖。需要修订时创建后续序号文件，并用 issue ID 和产物路径建立关联。

运行开始前的旧产物清理分工如下：`harness/knowledge/`、workspace 生成物（`memory/`、`outputs/`、`tmp/`，whole-lca）与 openLCA 前景实体由 GUI 或 CLI 在启动 agent 前调用 `src/scripts/clean_dir/` 清理（whole-lca：`--preset whole-lca`；revise-lca：`--preset revise-lca`，不清理 workspace）。须保留 `workspace/inputs/` 中的 `plan.md` 与 `revise.md`。GUI 通过 `file_sync` 同步用户资料与计划/意见；CLI 用户手工复制到 `harness/knowledge/` 并编辑 inputs。工作流使用上述固定路径，不生成运行 ID 或按运行 ID 分层；如果旧文件仍然存在，固定文件可以被本次运行覆盖，但同一次运行内不得覆盖已有阶段、审查或交接历史。

所有时间戳使用带 `Z` 的 RFC 3339 UTC 格式。不要在记忆、handoff、checklist 或报告中记录 SHA-256。

## 3. Agent 交接

每次委派前后都在 `workspace/memory/handoffs/` 保存符合 `handoff.schema.json` 的记录，至少包含 schema/version、handoff/stage ID、from/to agent、时间、输入产物路径、决策、证据引用、未解决项、状态、下一动作和关联 issue ID。检索交接应写明所用工具、查询词、选用理由和原文位置或 UUID。受委派 Agent 可按任务需要读取相关记忆，但只有主编排 Agent 负责持久化运行状态和历史记录。

每个阶段记录必须包含 `basis`（本阶段依据）和 `sources`（资料或工具）。主编排在写 stage 的同时更新 `checklist.md` 对应小节。

公共 handoff、stage、manifest 与 review 握手机制见 `harness/specs/public/references/handshake-common.md`。

## 4. 通用终止状态

终止只有两种状态，都必须写入非空 `status_reason`：

- `completed`：第 07 阶段的全部完成条件已有结构化证据。`status_reason` 概括通过依据（导入零失败、模型图无断链、LCIA 非空、资源已释放等）。
- `failed`：运行无法继续完成。包括计划缺少第 01 阶段阻断性事实、LCI 审查三次仍未通过、以及工具/导入/计算不可恢复失败。`status_reason` 必须写明停止阶段、具体原因，以及关联 issue ID 或工具错误；不得只写 `failed`。

不得因文件存在、工具返回 exit 0 或 agent 自称完成而标记 `completed`。不得将运行置为 `needs_input` 或 `needs_review`。
