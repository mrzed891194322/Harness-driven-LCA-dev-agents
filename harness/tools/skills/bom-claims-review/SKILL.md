# BOM 数量抽取 · 审核护栏

审核者专用。需要时阅读本文件；按条核对后立刻交卷，不要发挥成长散文。


## 范围（只读）

- 对照题面：`<plan>` / query 要什么，就只接受什么。
- 对照交付物：已有 `workspace/artifacts/bom/claims.json`（可扫 `evidence` 短句是否像所问）。
- **禁止**重读知识库长文；不要走 `bom-claims-read` 的 ls→grep→全文窗口流程。
- 不要挂、不要提示去读 `bom-claims-read` / `bom-claims-ops`。

## 审核清单（reject 时 issues 写清 where / problem / expected）

1. **多报**：同表邻居行、扫参端点、分解项、无关百分比——题面没要就删；金标=只答所问。
2. **单位**：`unit` 尽量保留原文完整短语（勿丢 `of X` / `glass`；`lbm` 与 `lb` 勿混）；同一量勿双单位双 claim。
3. **漏报**：题面要一组 / 上下界 / 多种工艺时，claims 明显只交子集 → reject，要求补全。
4. **合计**：题面要合计时交一条合计；勿拆成工序两条却无合计。
5. **交卷**：核对完立刻 `submit`（`verdict=approve|reject|…`）；勿空转打满 max_turns。有 claims 且可修 → `reject`，勿 `no_submit` 卡死。未用参数省略，勿传 null。
