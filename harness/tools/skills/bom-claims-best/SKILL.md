# BOM 数量抽取 · 最好条件护栏

需要时阅读本文件；按条执行，不要发挥成长散文。


## 读资料（`harness/knowledge/inputs/`）

- 先 `ls` 看清文件，再用 `grep`（关键词 / 表头 / 单位）定位行号，然后 `read` 时带 **`offset` / `limit`** 只取证据窗口。
- **禁止**对同一长文反复无参整文件 `read`；已读过的段落用 `grep` 回查，不要把全文再喂一遍。
- 大文件策略：`grep` → 按命中行号向两侧扩一小段 `read` → 不够再扩；需要多处证据就多次小窗口，而不是一次读完整份。
- `reference.md` 与同源 `*.pdf.txt` / `*.md` 内容重叠时：**只深读一份**（优先纯文本），另一份最多 `grep` 核对。
- 引用写明文件名与位置（行号或小节标题）；数值必须能回链窗口内原文。

## 单位（防双 claim）

- 同一物料、同一数量字段：**只留一条** `(value, unit)` claim。
- 原文并列写出两种单位（如 `2.16lbs (0.98kg)`）：**只保留一档**，优先保留原文主写单位（通常是 lbs / kg 中先出现的）；**禁止**再为换算结果另建一条 claim。
- 自行做 lbs→kg（或其它）换算时：交付物里仍只写一条；不要「原文一条 + 换算一条」。
- 单位用短符号：`g` / `kg` / `%` / `lbs` / `lb` 等，不要写 `grams`、`percent`。
- 数值区间（a–b）：拆成两端点两条数值 claim；`value` 必须是数。

## 工具参数类型

- `write` / `edit` 等工具里，**对象型参数必须先序列化为 string** 再传入。
- 尤其是 `content`：要写 JSON 时，传入 **JSON 文本字符串**（`{"claims":[...]}`），**禁止**把 object/array 直接当参数值。

## 输出契约

- 写到 `workspace/artifacts/bom/claims.json`，对齐 `.benchmark/schemas/claim_set.schema.json`。
- 有可用证据：`abstained` 可省略或 `false`，`claims` 非空；每条尽量含 `claim_id`、`item_id`、`field`、`value`、`unit`、`text`、`evidence`。
- 无可用文档或信息不足：`abstained: true` 且 `claims: []`，不要编造。
- 只抽题面要求的量；脏表尽量抽可辨数字，完全无法恢复才 abstain。

## 交卷

- 执行者写完 `claims.json` 后立刻 `submit`（`status=done` + `summary` + `artifacts`）。
- 审核者只读核对后立刻 `submit`（`verdict=approve|reject|terminate|approve_redo_upstream`）；未用参数省略，勿传 null。
- 审核者若写笔记，只用 `workspace/runs/<node>/reviewer/notes.md`；禁止把 `…/reviewer` 目录本身写成文件。
- 不要在仓库根目录 `ls`/`find`；只读允许的 artifacts / skills / specs 路径。
