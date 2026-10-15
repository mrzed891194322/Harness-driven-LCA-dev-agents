# 项目布局与 Harness 装配（workspace runs / artifacts）

面向改 harness、Python core 与 Web 控制面板的开发者。路径均相对仓库根，除非注明为「尝试目录内相对路径」。

## 1. 顶层目录

| 目录 | 职责 |
| --- | --- |
| `harness/` | 唯一声明源：workflow 装配、阶段 `spec.yaml`、规则、知识、MCP |
| `src/backend/core/` | 解析 harness、编排、注入、workspace 布局 |
| `src/backend/services/` | FastAPI 薄壳：启动、清理、结果 API |
| `src/pi-runtime/` | Pi SDK 会话与 MCP 子进程 |
| `workspace/` | 一次 LCA 运行留在磁盘上的可浏览产物（不含 run id 路径段） |
| `.local/runs/<run_id>/` | 按 run 隔离的 events、会话快照、workflow 快照（预清理不删） |

## 2. Harness 如何组装 workflow

1. **Workflow YAML**（`src/backend/workflows/LCA-main.yaml`、`LCA-revise.yaml`）定义 `registry`（rules、knowledge、MCP、host_action）与 `stages[].spec`。
2. **`load_workflow`**（`config/resolve.py`）解析每个 `spec:` 为 `harness/specs/<stage>/spec.yaml`，得到 `StageSpec`（`spec/loader.py`）。
3. **阶段契约** `spec.yaml` v2 清单字段：
   - `inputs` / `deliverables`：每项 `kind: handoff|deliverable`；存储形状用 `path_kind: file|directory`（目录型交付如 LCI）。
   - 路径写在**尝试目录内**（如 `extracted-bom.json`、`LCI/`），不再写 `workspace/outputs/...`。
   - 跨阶段输入用 `from: <stage-id>/<file>`，由宿主在审查通过后根据 `accepted.json` 解析为磁盘路径。
4. **注入**：`compile_turn` / `launch_spec` 把规则、知识、MCP、`spec_mcp` binding 写入 Pi 会话；`get_spec()` 提供交付物路径、schema、验收摘要（`spec_mcp/spec_view.py`）。
5. **权限**：`permissions.yaml` + `harness/specs/shared/permissions/`；路径白名单与 spec 声明对齐。

## 3. Workspace 布局（目标）

```text
workspace/
  runs/
    _run/                    # 运行级（无 run id）
      orchestrator.sqlite
      orchestrator.lock      # whole-lca 清理时保留
      manifest.json
      progress.txt
      rework/                # 返工记录 upstream-<n>.json
    <stage-id>/
      <role>-<n>/            # 单次尝试（编号跨 revise/resume 连续）
        handoff.json
        review.md            # reviewer 尝试
        session/             # 运行结束从 .local 复制
        raw/<call_id>/raw.json
        checks/
        sources.json
        import-operations/   # 04：openLCA 导入日志
      attempts.json          # 宿主维护的尝试列表
      accepted.json          # 本阶段验收通过的 executor/reviewer 目录与指纹
  artifacts/                 # 审查通过后复制的 deliverable（跨阶段只读）
    lca_report.md
    calculation-plan.json
    results.json
    LCI/
    extracted-bom.json
    extracted-bom.md
    process-mapping.json
    human_readable_mapping.md
  tmp/                       # 草稿；不进结果页
```

- **run id** 只出现在 `.local/runs/<run_id>/`，不出现在 `workspace/runs/` 路径中。
- **handoff** 固定文件名 `handoff.json`；审查记录 `review.md`。
- **03 `lca.model` 验收**写入 `accepted.json`（不再依赖 evidence manifest 的 `accepted` 键作为唯一真相）。

## 4. 各阶段产物（声明摘要）

| 阶段 | handoff | deliverable（尝试目录内） | 复制到 `artifacts/` |
| --- | --- | --- | --- |
| 01 | `handoff.json` | （无） | — |
| 02 | `handoff.json` | `extracted-bom.json`、`.md` | 是 |
| 03 | `handoff.json` | `LCI/`、`process-mapping.json`、`human_readable_mapping.md` | 是 |
| 04 | `handoff.json` | `calculation-plan.json`、`lca_report.md`、`results.json`（宿主由 raw 生成） | 是 |

`inputs` 示例（04）：

```yaml
- from: 03-dataset-mapping/LCI
  path: LCI
  kind: deliverable
  path_kind: directory
```

## 5. 清理规则

| 预设 | workspace | openLCA |
| --- | --- | --- |
| `whole-lca` | 删除 `runs/`（保留 `runs/_run/orchestrator.lock` 与 `**/README.md`）、`artifacts/`、`tmp/`；**整目录**删除遗留的 `outputs/`、`records/`（不保留其中 README） | 项目分类内实体（先于 workspace；openLCA 步失败则不清 workspace） |
| `revise-lca` | **不清理** | 同 whole-lca 的 openLCA 步 |
| `resume-lca` | **不清理** | 不按整轮清理；04 在尝试开始前按 import 日志删未 accepted 的旧尝试实体 |

知识文件 `harness/knowledge/` 永不随 whole-lca 删除。

openLCA 清理（开跑前预览/删除、04 尝试前清理）**只用 descriptor**（`data/get/descriptors` 按分类列出、`data/get/descriptor` 按 @id 复核分类），删除按 Ref 发 `data/delete`；**从不对实体做完整 `data/get`**——连着 ecoinvent 的 ProductSystem 完整序列化会把 IPC 堵住数分钟。旧实体靠分类列表即可找到，不依赖 workspace 文件；UUID 来源只读 `artifacts/LCI` 与 `runs/**/import-operations`，不再回退旧 `outputs/LCI`。分类判断要求第一级恰为项目名（`202606-harness-agent-LCA-old` 之类拒绝）。

## 6. 校验链（不变）

入口 `validate_inputs` → 写者 `submit` / `submit_handoff` → `validate_outputs` + host_checks → 审查 `_guard_reviewer_passed` + lifecycle → 复制 deliverable 到 `artifacts/`。

`checks.upstream_files`、handoff 路径、结果页 `kind: intermediate|deliverable` 均从 spec / workflow 聚合表生成，禁止在 Python/TS 再维护第三份路径清单。

## 7. 改代码时同步更新

- `harness/specs/*/spec.yaml`
- `docs/ARTIFACTS.md`、`docs/PROJECT_LAYOUT.md`（本文）
- `workspace/runs/README.md`
- `.cursor/rules/workspace-files.mdc`
- `harness/rules/project/paths.md`
