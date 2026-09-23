# 独立 lca_artifacts MCP

```bash
uv run python harness/tools/lca_artifacts/main.py
```

本入口不导入 workflow、不读取 `LCA_*` 上下文，也不写工作流检查/批准记录。所有路径和证据由调用方显式传入；相对路径基于启动目录。返回普通结构化结果。

| 工具 | 输入与行为 |
| --- | --- |
| `validate_inventory` | `bom_path`、`declared_sources`；检查清单与来源引用 |
| `validate_mapping` | `bom_path`、`mapping_path`、`lci_dir`、`provider_pairs`；检查覆盖、LCI 格式及外部 provider 对 |
| `render_report_tables` | `report_path`、`bom_path`、`mapping_path`、`calculation_rows`；替换 inventory/mapping/lcia 标记区，保留叙述 |
| `read_artifact` | `path`、`sha256`、可选 offset/limit/json_pointer；检查校验和后读取有界片段 |

`provider_pairs` 的每项包含 `process_id`、`flow_id`。`calculation_rows` 的每行依次是产品系统 UUID、方法 UUID、影响类别、数值、单位、证据路径。

whole-lca / revise-lca 使用工作流适配入口 `harness/tools/lca_artifacts/main.py`。原有 `validate_artifacts`、`get_validation_state`、`get_rework_status`、无参数的 `render_report_tables` 以及 v2 证据响应保持在适配层。
