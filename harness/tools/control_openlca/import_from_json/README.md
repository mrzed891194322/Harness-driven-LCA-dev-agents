# 从 JSON 导入/更新实体 (import_from_json)

此脚本允许您读取符合 openLCA JSON-LD 规范的结构化 JSON 配置文件，并通过 Python IPC 接口直接将这些流（Flow）、过程（Process）等实体导入或更新到 openLCA 的数据库中。

## 适用场景

1. **结构化批量录入**：当需要大量录入工艺数据或物料流，且已经整理为结构化的 JSON/JSON-LD 格式时。
2. **免 GUI 操作**：智能体（Agent）或其它自动化工作流可以直接在后台构建实体而无需启动或操作 openLCA GUI 界面。

## 文件格式与规范

实体必须使用 **camelCase** 的 JSON-LD 格式，并在最顶层以及所有关联的 Ref 中声明正确的 `@type` 和 `@id` (UUID)。
详细的 JSON-LD 数据结构模板与构建规范，请参考 `harness/specs/lci-construction/` 目录。

## 运行方式

通过命令行指定存放 JSON 文件的目录（支持子目录结构，并支持自动覆盖同名目录/分类）：

```bash
uv run python harness/tools/control_openlca/import_from_json/main.py <JSON配置文件目录> --host <主机地址> --port <端口>
```

**参数说明**：
*   `json_dir` (位置参数): 存放 JSON 结构化配置文件的文件夹路径。如果指定目录中含有 `flows`、`processes`、`product_systems` 等子目录，将按照该依赖顺序依次导入。
*   `--host` (可选): openLCA IPC Server 主机（默认：`127.0.0.1`）。
*   `--port` (可选): openLCA IPC Server 端口（默认：`8080`）。

### 特色机制

1. **自动获取项目名称**：脚本会自动从 `workspace/inputs/plan.md` 中解析出项目的英文缩写（如 `gold_plating`），直接作为导入实体的数据库分类目录名称，无须手动传参或进行多余的时间戳拼接。
2. **同名分类覆盖机制**：如果 openLCA 中已存在同名分类/目录，脚本将在导入前自动清空该分类下的所有已有实体，确保数据最新且不重复。
