# 工作流装配（默认版本）

`LCA-main.yaml`（whole-lca）与 `LCA-revise.yaml`（revise-lca）为 git 中的**默认**装配图。

运行与编排实际读取的是 `.local/harness/workflows/` 下的副本（首次 `npm start` 或后端启动时从本目录复制；默认更新且本地未改时会自动同步）。恢复默认：`POST /api/harness/workflows/<文件名>/restore-default`。

任务名到文件的映射见 `src/backend/services/workflow_cli.py` 的 `WORKFLOW_YAML_BY_TASK`。
