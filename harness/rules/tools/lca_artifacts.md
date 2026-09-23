# 离线产物工具调用纪律

- 每轮结束前**优先调用 `submit_handoff`** 交卷：由主机写入当前 assignment 的 handoff 路径并校验字段。不要手拼 `memory/handoffs/` 文件名，不要省略交卷。仅在工具不可用时，才回退写入运行上下文给出的 `handoff_path` JSON。
- 只使用当前阶段契约指定的检查 profile。`validate_artifacts` 生成审计，`get_validation_state` 刷新依赖与 stale 状态；检查通过不代替 reviewer 对方法和需求落实的判断。
- 引用工具返回的 `checks_ref.path` 和 `evidence_manifest_ref`；按其相对路径语义定位。`read_artifact` 分段读取，保留完整证据引用，不全量展开 raw。
- `render_report_tables` 仅供写者使用；生成区域数值不得手工修改。reviewer 可调用校验和做独立离线复核，不能代写报告。
- 新运行不能沿用上一运行的通过状态；不得手工编辑 checks、raw 或 evidence manifest 获取通过或复用资格。离线脚本结果不是权威检查状态。
- 04 返工的 `get_rework_status` 调用与复用条件按该阶段共有契约执行。语言检查提示不证明解释正确或可读，reviewer 仍须独立判断。
