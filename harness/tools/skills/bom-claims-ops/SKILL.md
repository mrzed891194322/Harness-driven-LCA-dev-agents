# BOM 数量抽取 · 操作 / 单位 / 交卷护栏

需要时阅读本文件；按条执行，不要发挥成长散文。


## 只交所问（防多报）

- **只提交题面要求的量**；禁止把同表邻居行、扫参端点、分解项、无关百分比一并交上。
- 金标口径=只答所问；多报与漏报同等有害。

## 单位（防双 claim / 防丢修饰）

- 同一物料、同一数量字段：**只留一条** `(value, unit)` claim。
- 原文并列写出两种单位（如 `2.16lbs (0.98kg)`）：**只保留一档**，优先保留原文主写单位；**禁止**再为换算结果另建一条 claim。
- **`unit` 用短符号/短规范名**（如 `kg`、`%`、`MJ/kg`）；勿把描述性短语、限定语写进 `unit`。
- 数值区间（a–b）：用**中点**作一条数值 claim；`value` 必须是数。

## 工具参数类型

- `write` / `edit` 等工具里，**对象型参数必须先序列化为 string** 再传入。
- 尤其是 `content`：要写 JSON 时，传入 **JSON 文本字符串**（`{"claims":[...]}`），**禁止**把 object/array 直接当参数值。

## 输出契约

- 写到 `workspace/runs/_run/artifacts/bom/claims.json`，对齐 `.benchmark/schemas/claim_set.schema.json`。
- 有可用证据：`claims` 非空；每条尽量含 `claim_id`、`item_id`、`field`、`value`、`unit`、`text`、`evidence`。
- 无可用文档或信息不足：交 **`claims: []`**，不要编造（`abstained` 字段可选，非必需）。
- 只抽题面要求的量；完全无法恢复才交空数组。

## 交卷

- 执行者写完 `claims.json` 后立刻 `mcp__submit__submit`（`status=done` + `summary` + `artifacts`）。
- 审核者只读核对后立刻 `mcp__submit__submit`（`verdict=approve|reject|terminate|approve_redo_upstream`）；未用参数省略，勿传 null。
- 审核者若写笔记，只用 `workspace/runs/_run/notes/<node>/reviewer/notes.md`；禁止把 `…/reviewer` 目录本身写成文件。
- 不要在仓库根目录 `ls`/`find`；只读允许的 artifacts / skills / specs 路径。
