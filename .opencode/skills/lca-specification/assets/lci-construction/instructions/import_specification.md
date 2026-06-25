# openLCA 批量数据导入规范 (import_specification)

本规范规定了如何将生成并经过自检校验合格 of LCI JSON 数据文件（流、过程、产品系统等）批量导入到本地运行 of openLCA 数据库中。

## 前置要求

1. **客户端与 IPC 服务**：请确保本地已开启 openLCA 桌面客户端，并启动了 IPC Server 服务（默认端口 `8080`）。
2. **导入工具**：使用 `external-tools` 技能下的导入脚本：
   `.opencode/skills/external-tools/assets/control-openlca/scripts/import_from_json/main.py`

## 执行命令

请运行以下命令进行批量导入：

```bash
uv run python .opencode/skills/external-tools/assets/control-openlca/scripts/import_from_json/main.py src/LCI
```

### 参数说明与规则：
- `src/LCI`：包含 LCI JSON 文件的根目录。脚本会自动检测子目录结构，并按照依赖关系（`flows` -> `processes` -> `product_systems`）顺序依次导入。
- **自动获取并配置项目名称**：
  - 脚本会**直接读取工作目录的名称**（例如当前为 `202606-Multi-agent-LCA`）作为导入实体的分类目录名。
  - 如果由于任何原因读取工作目录名称失败，脚本会自动将其命名为 `'auto_LCA_project'`。
- **同名目录覆盖机制**：如果 openLCA 数据库中已存在同名分类/目录（如 `202606-Multi-agent-LCA`），脚本会**自动清空该目录下的所有旧实体数据**，然后再重新上传当前最新生成的数据。这能保证每次导入后的数据都是最新且无冗余的。

*注：如果调用时显式提供了自定义的 `--host`、`--port`，请对应追加到运行命令末尾，例如 `--host 127.0.0.1 --port 8080`。*

## 结果确认与汇报

1. 观察控制台输出，确认每个实体的导入状态为 `[成功]`。
2. 导入完成后，向人类汇报总计导入的实体类别、数量以及是否成功覆盖旧同名目录。
