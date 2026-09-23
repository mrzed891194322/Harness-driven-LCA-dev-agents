# LCA Specification Index

阶段顺序和路径见 `public/README.md`。进入阶段后再读对应编号包。不要一次加载全部 spec。

## Whole-LCA

1. `01-intake-gate/README.md`（审查任务：`reviewer.md`）
2. `02-inventory-extraction/README.md`（`executor.md` / `reviewer.md`；修订另用 `reviser.md`）
3. `03-dataset-mapping/README.md`
4. `04-openlca-reporting/README.md`

编排入口：`harness/LCA-main.yaml`。启动命令：

```bash
uv run python src/scripts/workflow.py --workflow harness/LCA-main.yaml
```

## Revise-LCA

同一套 01–04。编排入口：`harness/LCA-revise.yaml`（`reuse` 主工作流后把 02–04 的写者换成 `reviser.md`）。修订契约在各包 `references/revise.md`；01 仍只派 reviewer。

```bash
uv run python src/scripts/workflow.py --workflow harness/LCA-revise.yaml
```
