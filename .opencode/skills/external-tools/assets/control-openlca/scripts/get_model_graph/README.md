# 获取产品系统模型图连线信息 (get_model_graph)

此脚本允许您连接到运行中的 openLCA IPC Server，获取指定产品系统（Product System）的模型图（Model Graph）的节点（Processes）与连线（Process Links）信息，并支持以结构化的 JSON 格式导出拓扑连接关系。

## 适用场景

1. **关系链条溯源**：查明特定产品系统中，各个工序（Unit Processes）是如何通过流（Flow）互相关联与喂给的。
2. **可视化或二次建模**：将模型拓扑导出为 JSON 文件，用于后续的依赖分析或第三方画图、校验等。

## 运行方式

通过命令行指定要查找的产品系统（支持名称或 UUID）：

```bash
uv run python .opencode/skills/control-openlca/scripts/get_model_graph/main.py "产品系统名称" --host <主机地址> --port <端口> --output <输出JSON路径>
```

**参数说明**：
*   `system` (位置参数): 产品系统（Product System）的名称或 UUID。
*   `--host` (可选): openLCA IPC Server 主机地址（默认：`127.0.0.1`）。
*   `--port` (可选): openLCA IPC Server 端口号（默认：`8080`）。
*   `--output`, `-o` (可选): 将读取出的完整模型图节点与连接线以 JSON 格式输出至该路径。
