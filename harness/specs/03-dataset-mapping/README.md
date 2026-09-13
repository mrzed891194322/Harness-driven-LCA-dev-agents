---
id: 03-dataset-mapping
inputs:
  - workspace/outputs/inventory/extracted-bom.json
  - workspace/inputs/plan.md
outputs:
  - workspace/outputs/inventory/process-mapping.json
  - workspace/outputs/LCI/
---

# 03 背景数据集映射

把 BOM 行映射到活动库数据集并写出可导入 LCI。工作细节面板渲染 `process-mapping.json`。执行后审查，最多 3 轮。审查通过前禁止 `import_lci`。

## 阶段目标

为每条前景流选定 Flow / Process / Provider（名称与 UUID 来自正式查询），写出 mapping 与 JSON-LD LCI。

## 输入说明

- `workspace/outputs/inventory/extracted-bom.json`
- 计划与本任务已注册的资料来源（默认 `harness/knowledge/`）
- openLCA 活动库（经 `control_openlca`）

首次调用 openLCA 前做 `health_check`。UUID 必须来自正式查询；禁止编造。不得用错误功能冒充（再生粒料不得代替原生，除非计划要求）。地域无精确候选时自行选区域市场或 `RoW`/`GLO`，并记下请求值、选用值和理由。

## 提交要求

`workspace/outputs/inventory/process-mapping.json`，每行：

- `item_id`（对 BOM）
- 选用 Flow / Process / Provider 的名称与 UUID
- 请求地域、实际地域
- `selection_reason`
- 候选摘要（可短）

同时写出 `workspace/outputs/LCI/`：仅 `flows/`、`processes/`、`product_systems/`，一文件一实体的 openLCA JSON-LD；根目录 `human_readable_mapping.md` 写换算与地域代理。

JSON-LD 必需字段：exchange 显式布尔 `isInput`；每个 Process 恰好一个输出 `isQuantitativeReference: true`；前景输入给 `defaultProvider`；Product System 用 `linkingMode: auto`、`preferDefaultProviders: true`，不要写 `processLinks` 当待导入拓扑。不要使用会被忽略的 `input` 或 `quantitativeReference` 别名。

示例：`references/examples/process-mapping.json`。

## 验收标准

- 映射功能对应，理由与地域写清。
- LCI 实体能对上 BOM `item_id`。
- UUID 能指回正式查询。
- 审查通过前未执行导入。

## 前置及停止条件

明显错配则审查 `failed` 并指出要改的行。第 3 次仍失败则运行 `failed`。

## 机器证据

写者提交前调用 `validate_artifacts(profile="mapping")`，handoff 引用返回的 checks_ref.path 和运行 evidence_manifest_ref。reviewer 独立核对证据并决定通过，不把工具成功当作阶段通过。检查定义见公共 `references/evidence-contract.md`；旧检查输入变化即 stale。

选择理由 selection_reason 使用中文，正式数据集名称/UUID/地域代码保持原文。完成 BOM/mapping/LCI 后再运行正式 Provider 验证及 validate_artifacts，避免后续改动使证据过期。机器验收只证明已有结构可核查的条件，功能匹配和换算仍由 reviewer 判断。
