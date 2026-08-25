# 项目准备说明

有 GUI 时，参考资料用左侧上传（写入 `harness/knowledge/`），计划在「开始LCA工作」里填写或上传。本文补充 openLCA IPC，以及不用 GUI 时的输入路径。

## 1. 打开 openLCA 与 IPC

启动 openLCA Desktop，打开目标数据库，并启用 IPC Server（默认端口 `8080`）。

![openLCA IPC Service](../assets/images/project_prep/openlca-ipc.png)

在项目根目录检查连接：

```bash
uv run python src/scripts/check_status/main.py --only openlca
```

底层操作约束和工具接口分别记录在 `harness/rules/openlca-operation/README.md` 与
`harness/tools/control_openlca/README.md`。

## 2. 不用 GUI 时的输入路径

- 参考资料：`harness/knowledge/`（扁平目录，唯一落点）
- 计划：`workspace/inputs/plan.md`（whole-lca 的唯一计划输入）
- 修订意见：`workspace/inputs/revise.md`（仅 revise-lca）

不要把用户资料放到 `workspace/inputs/references/`。LCA 方法要求见
`harness/rules/lca-knowledge/README.md`。

计划至少需要明确研究对象、功能单位、系统边界、背景数据库和 LCIA 方法。模板见
[`src/GUI/ui/assets/template/plan.md`](../../src/GUI/ui/assets/template/plan.md)。

命令行初始化与执行见 [手动调试](manual_debug.md)。`query_rag` 仍可作为独立 MCP 实现保留于 `harness/tools/query_rag/`，但当前 Agent 路径不使用它。

> [!WARNING]
> 不带 `--only` 的默认手动初始化会清理运行目录，并清理活动数据库中当前
> 项目分类下的前景实体。`whole-lca` 启动时也会清理旧前景实体和旧生成物。运行前请确认
> 当前数据库、项目分类和需要保留的结果。
