# 离线产物工具调用纪律

- 交付和交卷都走 spec_mcp（`get_spec` / `submit` / `status` / `submit_handoff`），本工具不再负责交卷。不要手拼 `records/handoffs/` 文件名，不要省略交卷。
- Core Host Action（`inventory_check` / `mapping_check` / `report_check`）由编排器在验收与 reviewer gate 重跑；Agent 不要自行调用这些 Host Action，也不要把 MCP 当成验收门。检查通过不代替 reviewer 对方法和需求落实的判断。
- 引用工具返回的 `checks_ref.path` 和 `evidence_manifest_ref`；按其相对路径语义定位。`read_artifact` 分段读取，保留完整证据引用，不全量展开 raw。
- `render_report_tables` 仅供写者使用；生成区域数值不得手工修改。reviewer 可调用只读 MCP 做独立离线复核，不能代写报告。
- 新运行不能沿用上一运行的通过状态；不得手工编辑 checks、raw 或 evidence manifest 获取通过或复用资格。离线脚本结果不是权威检查状态。
- 04 返工的 `get_rework_status` 调用与复用条件按该阶段共有契约执行。语言检查提示不证明解释正确或可读，reviewer 仍须独立判断。
