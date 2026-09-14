# 离线产物工具使用规则

本工具不连接 openLCA。只加载本阶段 spec 指定的检查 profile，不扫描无关 spec。

- 运行上下文由主编排写入 `--context-file`（每轮覆盖 attempt/role）；MCP 每次调用重读该文件。无该参数时才回退环境变量或 standalone。
- validate_artifacts 生成独立审计文件；get_validation_state 重新比较依赖并标记 stale。主编排在写者提交后运行对应检查。校验状态不等同于阶段通过。
- 引用返回的 checks_ref.path 和 evidence_manifest_ref；路径相对 workspace，完整 raw 通过路径与 SHA-256 对应。
- read_artifact 按 offset/limit 读取局部内容，避免全量展开证据。输入资料优先从运行 source_manifest 定位。
- 04 返工先 get_rework_status；eligible=true 且 report_only 才可复用全部原始结果。calculation_changed 需重新核对计算计划和缺失证据；model_changed 需上游审查。
- render_report_tables 仅供写者使用。reviewer 可调用 validate_artifacts 对相同表格逻辑进行比对，不替写者修改报告。
- 不通过添加少量汉字宣称语言检查通过；语言提示只是线索，reviewer 仍逐项判断面向用户的解释。
- 新运行不能引用上一运行的通过状态。不可手工编辑 checks 或 evidence manifest 来获得复用资格。
