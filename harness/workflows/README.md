# 工作流装配（默认版本）

`LCA-main.yaml`（whole-lca）与 `LCA-revise.yaml`（revise-lca）为 git 中的**默认**装配图。

运行与编排实际读取的是 `.local/harness/workflows/` 下的副本（首次 `npm start` 或后端启动时从本目录复制；默认更新且本地未改时会自动同步）。恢复默认：`POST /api/harness/workflows/<文件名>/restore-default`。

任务名到文件的映射见 `src/backend/services/workflow_cli.py` 的 `WORKFLOW_YAML_BY_TASK`。

## 展示字段（PR1，不进注入哈希）

- 根级：`title`、`mode`、`plan`（计划 Markdown 路径）
- `global.permissions.ceiling`：权限上限规则 id 列表（如 `worker-default`、`reviewer`）；`registry.permissions` 声明组件路径
- `stages[]`：`title`、`short_title`、`resumable`、`phase_title`
- `assignments.<id>`：`title`（审查角色请写「审查」）
- 合并算法与错误码见 `src/backend/core/workflow/config/compose.py`；权限逐层收窄见 `permission_narrow.py`
- 模型优先级：assignment YAML `model` → `models.default` → `.local/workflow-models.json` → 运行默认
- 只读 API：`GET /api/workflows`、`GET /api/workflows/{name}/manifest`、`GET /api/harness/injection`
