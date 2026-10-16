# 产物位置

| 路径 | 用途与约束 |
| --- | --- |
| `harness/knowledge/inputs/` | 用户参考资料；经 `knowledge_sources` / `source_manifest` 声明 |
| `harness/knowledge/plan/` | 只读的 `main_plan.md`、可选 `revise_plan.md`；不是默认证据检索域 |
| 运行上下文的 `source_manifest` | 资料定位的依据 |
| `workspace/runs/<stage>/<role>-<n>/` | 单次尝试：handoff、review、raw、checks、sources、import-operations（路径以 spec 声明为准） |
| `workspace/runs/<stage>/accepted.json` | 审查通过后下游 inputs 解析源 |
| `workspace/artifacts/` | 跨阶段只读 deliverable（审查通过后由宿主复制） |
| `workspace/runs/_run/` | manifest、progress、orchestrator 状态（详见 `docs/PROJECT_LAYOUT.md`） |
| `workspace/tmp/` | 临时离线脚本、复核结果及运行时中间文件；可被外部清理，不能作为唯一证据 |

revise-lca 提交完整的新版本到既有 outputs 位置；不另建 baseline 副本。BOM/mapping JSON 不放入 LCI 实体目录。路径相对 workspace 还是项目根以相应接口说明为准，不凭猜测拼接 raw 路径。
