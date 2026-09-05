# clean_dir

按目标清理 `harness/knowledge/`、workspace 生成物或 openLCA 前景实体。

## 用法

```bash
# 默认：仅 workspace（memory/、outputs/、tmp/）
uv run python src/scripts/clean_dir/main.py -y

# 单目标
uv run python src/scripts/clean_dir/main.py -y -t knowledge
uv run python src/scripts/clean_dir/main.py -y -t workspace
uv run python src/scripts/clean_dir/main.py -y -t openlca

# 预设（与 GUI 执行前清理一致）
uv run python src/scripts/clean_dir/main.py -y --preset whole-lca
uv run python src/scripts/clean_dir/main.py -y --preset revise-lca
```

## 退出码

- `0`：全部请求目标清理成功（stdout 含 `[OK]`）
- `1`：未知目标、删除失败或 openLCA 清理失败（stderr 含 `[FAIL]`）

`--target` 与 `--preset` 互斥。preset 任一步失败会中止后续步骤。

## 无 GUI 前置步骤

whole-lca：

1. `clean_dir -y --preset whole-lca`
2. 复制资料到 `harness/knowledge/`，编写 `workspace/inputs/plan.md`
3. `uv run python src/scripts/lca_orchestrator/main.py --task whole-lca`

revise-lca：

1. `clean_dir -y --preset revise-lca`（不清理 workspace）
2. 更新 `harness/knowledge/` 与 `workspace/inputs/revise.md`
3. `uv run python src/scripts/lca_orchestrator/main.py --task revise-lca`
