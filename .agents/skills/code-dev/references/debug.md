# 调试一次运行

每个 Pi 会话在 `.local/runs/<run_id>/sessions/<stage>.<role>.<attempt>/` 下留完整记录，字段见 `docs/ARTIFACTS.md`。按这个顺序查，查到能解释现象就停：

1. `npm run inspect -- <run> --only-anomalies`：哪些会话的注入有 warn / mismatch（模型、spec_mcp 工具、路径守卫钩子是关键项）。`events.jsonl` 里对应 `kind: injection_check`；运行结束的 `injection-summary.json` 列出全部 mismatch。
2. `npm run inspect -- <run> <stage.role.attempt>`：计划注入（`injection/intended.json`）与实际生效（`injection/effective.json`）的逐项比对；第一次模型请求的实际 payload 在 `injection/first_request.json`。
3. `npm run session -- <run> <stage.role.attempt> -o /tmp/s.md`：导出可读的完整对话，交给接手的 agent。
4. `npm run doctor`：不调模型的空会话自检，确认 runtime 当前的注入链路正常。

默认只记录、不中断。`HARNESS_INJECTION_STRICT=1` 才让关键项不一致的会话启动失败，以及暂停期间配置变化时拒绝恢复，只在测试或自检时开。这些文件已脱敏，不要把它们贴进提交。
