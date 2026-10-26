# LCI 封闭映射 · 最好条件护栏

需要时阅读本文件；按条执行，不要发挥成长散文。

## item_id

- 每个题面物料写一条 `items[]`。
- `item_id` **优先用题面给出的 id**；题面未给时用 `m1`、`m2`…，且须与题面条目一一对应、整份交付自洽。

## 弃权 / 选定口径

- 候选只认题面列出的名字（及真值侧封闭集）；**禁止**发明集合外过程名。
- 封闭集中有明显唯一更贴近题面描述的候选：**必须选它**。
- 多个候选同等合理、无法区分时：相关 `process_name` / `provider_name` / id 等置 `null`，在 `selection_reason` 用中文说明无法选定的原因（弃权）。不要瞎猜。
- `process_name` / `provider_name` 填所选候选全名；无 UUID 时 `process_id` / `provider_id` / `flow_*` 可写 `null`。
- `candidates` 数组回填题面可见候选名（展示用）。

## 工具参数类型

- `write` / `edit` 等工具里，**对象型参数必须先序列化为 string** 再传入。
- 尤其是 `content`：要写 JSON 时，传入 **JSON 文本字符串**，**禁止**把 object/array 直接当参数值。

## 输出契约

- 写到 `workspace/artifacts/mapping/mapping.json`，对齐 `.benchmark/schemas/mapping_deliverable.schema.json`。
- 必有 `items` 数组；每项含 schema 要求字段（含 `selection_reason`、`candidates`）。
- 缺产物、编造集合外名字、blocked：不得视为完成。

## 交卷

- 执行者写完 `mapping.json` 后立刻 `submit`（`status=done` + `summary` + `artifacts`）。
- 审核者只读核对后立刻 `submit`（`verdict=approve|reject|terminate|approve_redo_upstream`）；未用参数省略，勿传 null。
- 不要在仓库根目录 `ls`/`find`；只读允许的 artifacts / skills / specs 路径。
