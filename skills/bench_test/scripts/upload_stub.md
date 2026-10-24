# 上传脚本占位

P0 没有前端上传，也没有后端接收分数的接口。不要新建 POST 路径，也不要调用控制面板的 `/api/workflow/*` 来「交卷」。

以后如果要做，脚本应只做两件事，并且仍然不把 PCFBench 源文件读进仓库：

1. 读本地 `--out-dir` 里的 `scores.jsonl` 与 `summary.json`（`score_case.py` 已经能写出这两份）。
2. 把这两份小 JSON 交给当时已经存在的结果接口。大 jsonl、PDF、picklist 继续留在 `$BENCHMARK_CACHE`。

在那个接口出现之前，把分数留在 `--out-dir` 或终端 JSON 里即可。
