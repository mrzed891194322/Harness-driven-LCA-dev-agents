# BOM 数量抽取 · 审核护栏

审核者专用。需要时阅读本文件；按条核对后立刻交卷，不要发挥成长散文。

## 角色分工

- **executor**：从长文抽出 claims。
- **reviewer**：读**同一份**长文（`harness/knowledge/inputs/` 下的 `reference.md` 等），**对照原文**核对 claims 的对错、多报、漏报、单位是否合题。侧重点是核对，不是重新抽一套。

## 范围（应读）

- 对照题面：`<plan>` / query 要什么，就只接受什么。
- 对照交付物：已有 `workspace/artifacts/bom/claims.json`。
- **应读**知识库同一份长文，按需 `read` / `grep` / 分段窗口（可参照 `bom-claims-read` 的读法）；不要只凭题面空想。
- 不要自己当抽数人再交一套 claims：有问题用 `reject` 让 executor 改（除非当前宿主机制明确允许 reviewer 直接改产物）。

## 审核清单（reject 时 issues 写清 where / problem / expected）

1. **对错**：claim 的数值/对象是否能在原文找到依据；明显编造或张冠李戴 → reject。
2. **多报**：同表邻居行、扫参端点、分解项、无关百分比——题面没要就应删；金标=只答所问。
3. **单位**：`unit` 尽量保留原文完整短语（勿丢 `of X` / `glass`；`lbm` 与 `lb` 勿混）；同一量勿双单位双 claim；单位是否合题。
4. **漏报**：题面要一组 / 上下界 / 多种工艺时，claims 明显只交子集 → reject，要求补全。
5. **合计**：题面要合计时交一条合计；勿拆成工序两条却无合计。
6. **交卷**：核对完立刻 `submit`（`verdict=approve|reject|…`，**必须带参**）；禁止空 `{}`。勿为空转 evidence 行号打满 max_turns。有 claims 且可修 → `reject`，勿 `no_submit` 卡死。未用参数省略，勿传 null。
