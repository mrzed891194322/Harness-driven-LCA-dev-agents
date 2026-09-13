# 02 前景清单修订（执行）

按本阶段共有契约与修订补充契约写出完整 BOM。不要查询 openLCA、不要写 LCI。不要覆盖 `plan.md`。

## 需要解决的问题

- 同时读取上一轮 `extracted-bom.json` / `.md`、`workspace/inputs/plan.md`、`workspace/inputs/revise.md` 与本任务资料来源（默认 `harness/knowledge/`）。
- `revise.md` 与原计划冲突时以 `revise.md` 为准。
- 用户未点名的 BOM 行默认保留；点名的增删改必须写入完整新 BOM，并在 `source_locations` 或缺口说明中回链意见原文。
- 读得出的资料必须抽取；读不出的二进制标为 `unreadable`，不得编造数量。
- 写出完整的 `extracted-bom.json` 与 `extracted-bom.md`，不要只交差量文件。

## 返工方式

若在原修订会话中收到审查意见：先落实指出的用户意图缺口，再改正确定性错误，重新提交完整 BOM 与 handoff。历史对话中的旧 BOM 不能替代本轮落盘文件。

## 提交

写 handoff：`role=reviser`，`status` 为 `ok` / `failed` / `blocked`，列出 `artifacts`。`status_reason` 非空。

使用本阶段绑定的 lca_artifacts：`get_validation_state("inventory")` 查看状态，`validate_artifacts("inventory")` 核对最新证据。只引用工具生成的检查，不自报权威校验计数。
