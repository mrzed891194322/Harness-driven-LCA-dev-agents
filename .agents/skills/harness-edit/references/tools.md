# 工具

`registry.tools` 只有 `mcp` 和 `host_action`。core 不 import `harness.tools`。

MCP 登记在 `registry.tools.mcp.<id>`：`transport: stdio`、`command`、`args`、可选 `env`、`tool_timeout_sec`、`rules`（规则 ID 列表）、`runtime`。`runtime` 只使用 `run_context_env`、`context_file`、`context_file_flag`、`env_prefix`、`use_host_python`。现有服务：

- `lca_artifacts`：`harness/tools/mcp/lca_artifacts/main.py`
- `control_openlca`：`harness/tools/mcp/control_openlca/workflow_mcp.py`

调用纪律写在 `harness/rules/tools/`，用该 MCP 的 `rules` 字段绑上。签名以运行时发现的工具为准，不要在规则里抄实现。

Host Action 登记在 `registry.tools.host_action.<id>`：`command`、`args`、可选 `env`、`timeout_sec`。现有检查是 `inventory_check`、`mapping_check`、`report_check`、`record_acceptance`，入口都是 `harness/tools/host_action/lca_artifacts/main.py`。验收要跑哪个检查，写在对应阶段的 `acceptance.yaml` 里，不要在 YAML 里另造 checker。

实现分三层：`harness/tools/mcp/`、`harness/tools/host_action/`、`harness/tools/shared/`。共享逻辑放 `shared/`，两个入口只做适配。
