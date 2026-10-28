# 工作记录调试约定 & 第二套端口

## 出错先看工作记录

运行结束后（或失败收尾时）优先打开：

1. `workspace/runs/_run/work-record.md` — 步数、注入 planned vs actual、事件摘要  
2. `workspace/runs/_run/work-record.json` — 同上结构化  
3. `workspace/runs/_run/events.jsonl` — 逐步完整日志（含 `injection` / `turn_*` / `node_*`）

会话级注入全文见 `.local/runs/<run_id>/sessions/<node>.<agent>.<attempt>/injection.md`（字段说明：[SESSION_INJECTION.md](SESSION_INJECTION.md)）。

GUI：**结果浏览 → 工作记录**。最终交付侧栏只列 BOM / LCI / 报告；过程文件与注入记录都在工作记录。

`issue-diag` 除 `.local/logs/backend.log` 外，也应先核对上述工作记录。

## 计划模板（YAML）

表单分区由 `harness/plan-templates/*.yaml` 的 `sections` 驱动（`full-lifecycle` / `bom-only` / `lca-only`）。  
计划页「预设计划类型」与下载模板共用同一 `template_id`；骨架不同（完整 LCA / 仅 BOM / LCI 映射）。

落盘：`workspace/artifacts/plan/main_plan.yaml`（新工作）或 `revise_plan.yaml`（修订表单）。计划 YAML 只有 `template_id` 与 `items`（一般项 `title`+`content`；仅 `database` / `lcia` 可有 `enable`），**不含** `references`。非法 `items` 在表单与启动时不渲染、不下发。

参考资料单独管理：类型为知识库 / BOM / LCI；编辑期分别在 `harness/knowledge/inputs/`、`uploads/bom/`、`uploads/lci/`；fresh 开跑时 BOM/LCI 复制到 `workspace/artifacts/bom|mapping/references/`（见 `ARTIFACTS.md`）。

预览执行（PreviewBoard）区块顺序：**工作内容 → 参考资料 → 工作流**。

API：`GET /api/plan/templates`、`GET /api/plan/templates/{id}`、`GET /api/plan/template?template_id=`（下载骨架 YAML）。

## 另开第二套前后端（不占现网 8800/3000）

现网 serve 占用 `8800`/`3000`（及 `pi-v5serve.sock`）。在本功能 worktree 用环境变量偏移端口：

```bash
cd /path/to/repo/.local/wt/feat-work-log   # 或本分支任意 checkout
export GUI_API_PORT=8810
export GUI_WEB_PORT=3010
# 可选：显式避开默认 pi-runtime.sock（serve 已用 pi-v5serve.sock 时通常不冲突）
export PI_RUNTIME_SOCKET="/home/yuandu/Programming/202606-harness-agent-LCA/.local/run/pi-feat-work-log.sock"  # short path; nested wt sock exceeds UNIX_SOCK_PATH_MAX=104
npm run dev
```

健康检查：`curl --noproxy '*' http://127.0.0.1:8810/api/health`  
浏览器：`http://127.0.0.1:3010`

停止：在同一目录 `npm run stop`（评测默认主仓；勿误停无关可选 WT）。
