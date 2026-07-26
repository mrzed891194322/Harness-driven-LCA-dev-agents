# Harness-driven LCA Agents 项目准备说明

本文档说明运行 LCA 工作流前需要准备的输入资料与环境。

## 1. 准备输入文件

在 `workspace/inputs/` 下整理以下内容：

1. **参考资料**

   - 原始参考文档：`workspace/inputs/references/file/`
   - 结构化参考数据：`workspace/inputs/references/data/`
   - 同步后分别进入 `harness/knowledge/inputs/user_ref/file/` 和
     `harness/knowledge/inputs/user_ref/data/`。
   - 项目内置标准与 openLCA 手册位于 `harness/knowledge/inputs/static_ref/`；普通
     用户资料不要放入该目录。

2. **计划文件**

   - 使用模板
     [`src/GUI/ui/assets/template/plan.md`](../../src/GUI/ui/assets/template/plan.md)
     生成或编辑 `workspace/inputs/plan.md`。
   - 计划至少需要明确研究对象、功能单位、系统边界、背景数据库和 LCIA 方法。
   - `workspace/inputs/plan.md` 是 whole-lca 的唯一计划输入。

3. **修订意见（仅修订时需要）**

   - 将意见写入 `workspace/inputs/revise.md`。
   - revise-lca 还要求上一轮 plan、memory、LCI 和最终报告保持完整。

## 2. 打开 openLCA 与 IPC

启动 openLCA Desktop，打开目标数据库，并启用 IPC Server（默认端口 `8080`）。

![openLCA IPC Service](../assets/images/project_prep/openlca-ipc.png)

在项目根目录检查连接：

```bash
uv run python src/scripts/initialization/main.py --only openlca
```

底层操作约束和工具接口分别记录在 `harness/rules/openlca-operation/README.md` 与
`harness/tools/control_openlca/README.md`。

## 3. 构建 RAG 数据库

执行：

```bash
uv run python src/scripts/initialization/main.py --only rag
```

构建过程会：

1. 根据 `src/scripts/initialization/rag_init/mapping_rules.py` 选择知识源。
2. 转换、分块并向量化资料。
3. 校验新库后原子替换活动库；失败时保留旧库。

更多说明见 [RAG 数据库构建与查询指南](rag_guide.md)。

## 4. 运行前检查

可以分别检查 Python 环境与 openLCA：

```bash
uv run python src/scripts/initialization/main.py --only env
uv run python src/scripts/initialization/main.py --only openlca
```

> [!WARNING]
> 不带 `--only` 的默认手动初始化会清理运行目录、同步参考资料，并清理活动数据库中当前
> 项目分类下的前景实体。`whole-lca` 启动时也会清理旧前景实体和旧生成物。运行前请确认
> 当前数据库、项目分类和需要保留的结果。
