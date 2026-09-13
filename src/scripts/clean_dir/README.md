# clean_dir

按目标清理 `harness/knowledge/`、`workspace/inputs/`、workspace 生成物或 openLCA 前景实体。

## 用法

```bash
# 默认：仅 workspace（memory/、outputs/、tmp/），保留 inputs/
uv run python src/scripts/clean_dir/main.py -y

# 单目标
uv run python src/scripts/clean_dir/main.py -y -t knowledge
uv run python src/scripts/clean_dir/main.py -y -t inputs
uv run python src/scripts/clean_dir/main.py -y -t workspace
uv run python src/scripts/clean_dir/main.py -y -t openlca

# 预设（与 GUI 执行前清理一致）
uv run python src/scripts/clean_dir/main.py -y --preset whole-lca
uv run python src/scripts/clean_dir/main.py -y --preset revise-lca

# 跳过 knowledge + inputs（仍清 workspace 生成物与 openLCA）
uv run python src/scripts/clean_dir/main.py -y --preset whole-lca --no-staging
```

## 退出码

- `0`：全部请求目标清理成功（stdout 含 `[OK]`）
- `1`：未知目标、删除失败或 openLCA 清理失败（stderr 含 `[FAIL]`）

`--target` 与 `--preset` 互斥。preset 任一步失败会中止后续步骤。

`whole-lca` 会清 `knowledge`、`inputs`（`plan.md` / `revise.md`）、`workspace` 生成物与 openLCA 前景。`revise-lca` 清 `knowledge` 与 openLCA，保留 `workspace/inputs/plan.md`。`--no-staging` 从任一序列中去掉 `knowledge` 与 `inputs`。初始化检查默认的 `clean_dir -y` 仍只清 workspace 生成物。

## Agent 直跑前置步骤

whole-lca：

1. `clean_dir -y --preset whole-lca`
2. 复制资料到 `harness/knowledge/`，编写 `workspace/inputs/plan.md`
3. `uv run python harness/workflows/lca_orchestrator/main.py --task whole-lca`

revise-lca：

1. `clean_dir -y --preset revise-lca`（不清理 workspace / inputs）
2. 更新 `harness/knowledge/` 与 `workspace/inputs/revise.md`
3. `uv run python harness/workflows/lca_orchestrator/main.py --task revise-lca`
