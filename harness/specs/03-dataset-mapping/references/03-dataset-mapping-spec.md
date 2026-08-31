# 03 背景数据集映射

## 谁做

主编排先委派 `sub-executor` 映射并写 LCI，再委派 `eval-reviewer`。最多 3 轮。审查通过前禁止 `import_lci`。

首次调用 openLCA 前做 `health_check`。UUID 必须来自正式查询；禁止编造。不得用错误功能冒充（再生粒料不得代替原生，除非计划要求）。地域无精确候选时自行选区域市场或 `RoW`/`GLO`，并记下请求值、选用值和理由。

## 产物

`workspace/outputs/inventory/process-mapping.json`（工作细节面板渲染此文件），每行：

- `item_id`（对 BOM）
- 选用 Flow / Process / Provider 的名称与 UUID
- 请求地域、实际地域
- `selection_reason`
- 候选摘要（可短）

同时写出 `workspace/outputs/LCI/`：仅 `flows/`、`processes/`、`product_systems/`，一文件一实体的 openLCA JSON-LD；根目录 `human_readable_mapping.md` 写换算与地域代理。写入时使用工具能导入的字段：exchange 显式布尔 `isInput`；每个 Process 恰好一个输出 `isQuantitativeReference: true`；前景输入给 `defaultProvider`；Product System 用 `linkingMode: auto`、`preferDefaultProviders: true`，不要写 `processLinks` 当待导入拓扑。不要使用会被忽略的 `input` 或 `quantitativeReference` 别名。

示例：`examples/process-mapping.json`。

## 审查

Reviewer 看映射是否功能对应、理由是否写清、LCI 是否能对上 BOM `item_id`。明显错配则 `failed` 并指出要改的行。
