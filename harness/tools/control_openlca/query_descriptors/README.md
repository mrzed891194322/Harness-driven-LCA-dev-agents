# 检索数据库实体描述符 (query_descriptors)

此脚本用于通过 Python IPC 接口直接向当前正在运行的 openLCA 桌面端发起查询，从当前激活的数据库中检索各种实体（如 `Process`, `Flow` 等）的名称和 UUID。

## 适用场景

1. **背景数据链接匹配**：当 Agent 规划 LCI 需要将某项输入指定到特定数据库资源（如检索 ecoinvent 中的某个特定的电力生产过程），获取它的精确 UUID 以便写入 `defaultProvider`。
2. **快速实体探查**：无需打开 openLCA 的 GUI 搜索框，直接在终端中进行关键词模糊搜索。

## 运行方式

```bash
uv run python harness/tools/control_openlca/query_descriptors/main.py <Type> [--search <keyword>] [--limit <number>]
```

**参数说明**：
*   `type` (必选位置参数): 要查询的实体类型。支持的值有：`Process`, `Flow`, `ProductSystem`, `ImpactMethod`。
*   `--search` (可选): 名称的模糊搜索关键词（不区分大小写）。如果不提供，则返回所有实体的列表。
*   `--limit` (可选): 控制台最多显示多少条结果。默认 50。
*   `--host` / `--port`: 指定 IPC 连接地址（默认 `localhost:8080`）。

## 运行示例

查找名称中包含 "electricity" 的所有过程：
```bash
uv run python harness/tools/control_openlca/query_descriptors/main.py Process --search electricity
```
