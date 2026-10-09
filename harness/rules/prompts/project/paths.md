# 产物位置

| 路径 | 用途与约束 |
| --- | --- |
| `harness/knowledge/inputs/` | 用户参考资料；经 `knowledge_sources` / `source_manifest` 声明 |
| `harness/knowledge/plan/` | 只读的 `main_plan.md`、可选 `revise_plan.md`；不是默认证据检索域 |
| 运行上下文的 `source_manifest` | 资料定位的依据 |
| `workspace/outputs/inventory/` | `extracted-bom.json`、`extracted-bom.md`、`process-mapping.json`；GUI 读取两份 JSON |
| `workspace/outputs/LCI/` | `flows/`、`processes/`、`product_systems/` 中一文件一 JSON-LD 实体；根目录保存 `human_readable_mapping.md` |
| `workspace/outputs/reports/` | `calculation-plan.json`、`lca_report.md`；raw 使用工具返回的实际路径，不自行搬运或覆盖 |
| `workspace/records/` | 当前 handoff 与编排器/工具维护的状态、审查记录和证据；具体写权限按角色和公共协议 |
| `workspace/tmp/` | 临时离线脚本、复核结果及运行时中间文件；可被外部清理，不能作为唯一证据 |

revise-lca 提交完整的新版本到既有 outputs 位置；不另建 baseline 副本。BOM/mapping JSON 不放入 LCI 实体目录。路径相对 workspace 还是项目根以相应接口说明为准，不凭猜测拼接 raw 路径。
