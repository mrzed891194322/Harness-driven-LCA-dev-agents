# 上传脚本占位（分数结果）

本文件只管**打分结果**的上传设想，不管开跑。

- **开跑参考资料**：走 `POST /api/references`（multipart），步骤写在技能正文的 **`run`** 节。那是 knowledge inputs，不是交卷。
- **分数 / 交卷**：P0 没有后端接收 `scores.jsonl` / `summary.json` 的接口。不要新建 POST 路径，也不要调用 `/api/workflow/*` 或 `/api/references` 来「交分数」。

以后如果要做分数上传，脚本应只做两件事，并且仍然不把 PCFBench 源文件读进仓库：

1. 读本地 `--out-dir` 里的 `scores.jsonl` 与 `summary.json`（`score_case.py` 已经能写出这两份）。
2. 把这两份小 JSON 交给当时已经存在的结果接口。大 jsonl、PDF、picklist 继续留在 `$BENCHMARK_CACHE`。

在那个接口出现之前，把分数留在 `--out-dir` 或终端 JSON 里即可。
