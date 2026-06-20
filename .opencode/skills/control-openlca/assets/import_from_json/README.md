# 从 JSON 导入/更新实体 (import_from_json)

此脚本允许您读取符合 openLCA JSON-LD 规范的结构化 JSON 配置文件，并通过 Python IPC 接口直接将这些流（Flow）、过程（Process）等实体导入或更新到 openLCA 的数据库中。

## 适用场景

1. **结构化批量录入**：当需要大量录入工艺数据或物料流，且已经整理为结构化的 JSON/JSON-LD 格式时。
2. **免 GUI 操作**：智能体（Agent）或其它自动化工作流可以直接在后台构建实体而无需启动或操作 openLCA GUI 界面。

## 文件格式与规范

实体必须使用 **camelCase** 的 JSON-LD 格式，并在最顶层以及所有关联的 Ref 中声明正确的 `@type` 和 `@id` (UUID)。

*   **Flow 示例**：参见 [flow_example.json](examples/flow_example.json)
*   **Process 示例**：参见 [process_example.json](examples/process_example.json)

> [!NOTE]
> 在配置嵌套的 `Ref` 对象（如 `flowProperty` 或 `unit`）时，`@id` 必须使用 openLCA 中的有效 UUID。常用参考：
> - 质量 FlowProperty 的 UUID: `bca7e4ea-ad3a-4424-aa61-fb9617300c82`
> - 千克 (kg) 单元的 UUID: `20a8dd24-3405-47d4-9f50-cd467688c69d`

## 运行方式

通过命令行指定存放 JSON 文件的目录（该目录下的所有 `.json` 文件都将被遍历解析并导入）：

```bash
uv run python .opencode/skills/control-openlca/assets/import_from_json/main.py <JSON配置文件目录> --host <主机地址> --port <端口>
```

**参数说明**：
*   `json_dir` (位置参数): 存放 JSON 结构化配置文件的文件夹路径。
*   `--host` (可选): openLCA IPC Server 主机（默认：`localhost`）。
*   `--port` (可选): openLCA IPC Server 端口（默认：`8080`）。
