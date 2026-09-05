# LCA 修订主工作流

Python 主编排读取同名 `LCA-revise.yaml`。本文件只给人看。

启动前由 GUI 或用户用 `src/scripts/clean_dir/main.py -y --preset revise-lca` 清理 knowledge 与 openLCA 前景（不清 workspace）。意见：`workspace/inputs/revise.md`。

主编排先跑 `baseline.py` snapshot/activate，再按 YAML 委派 08，通过后覆盖 `plan.md` 并复用 `LCA-main.yaml` 的 01–04。
