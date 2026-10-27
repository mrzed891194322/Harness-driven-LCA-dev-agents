# LCI 映射分流 · 最好条件护栏

需要时阅读本文件；按条执行，不要发挥成长散文。

## 判定口径

- 题面给出一个**市场节点**（名 + 说明）与**上级产品语境**。
- `should_map: true`：该节点粒度已够，可直接当作背景过程去映射。
- `should_map: false`：节点过粗或是装配/组合件（如整车轮组相对整车），应继续分解。
- 不要编造题面未给的过程名；不要查询 openLCA。

## 输出契约

- 写到 `workspace/artifacts/triage/triage.json`。
- 必有 `should_map`（boolean）与中文 `rationale`。
- 可选 `confidence`（0–1）；建议回填 `candidate_name` 为题面市场全名。

## 工具参数类型

- `write` / `edit` 等工具里，**对象型参数必须先序列化为 string** 再传入。
- 尤其是 `content`：要写 JSON 时，传入 **JSON 文本字符串**，**禁止**把 object/array 直接当参数值。

## 交卷

- 执行者写完 `triage.json` 后立刻 `submit`（`status=done` + `summary` + `artifacts`）。
- 审核者只读核对后立刻 `submit`（`verdict=approve|reject|terminate|approve_redo_upstream`）；未用参数省略，勿传 null。
- 审核者若写笔记，只用 `workspace/runs/<node>/reviewer/notes.md`；禁止把 `…/reviewer` 目录本身写成文件。
- 不要在仓库根目录 `ls`/`find`；只读允许的 artifacts / skills / specs 路径。
