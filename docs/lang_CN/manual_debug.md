# 手动调试与文件同步指南

不使用 GUI 时，可以通过命令行准备资料、初始化项目并运行工作流。

## 1. 准备输入文件

将文件放入 `workspace/inputs/`：

- 参考文档：`workspace/inputs/references/file/`
- 结构化数据：`workspace/inputs/references/data/`
- 计划文件：`workspace/inputs/plan.md`
- 修订意见：`workspace/inputs/revise.md`（仅 revise-lca 需要）

## 2. 初始化前置

执行完整初始化：

```bash
uv run python src/scripts/initialization/main.py
```

默认 `manual` 模式会清理工作目录、同步 inputs、检查环境、构建知识库、检查 openLCA，
并清理当前项目分类下的 openLCA 前景实体。

> [!WARNING]
> 默认初始化和 `whole-lca` 都包含清理操作。请先确认活动数据库、项目分类和
> `workspace` 输入无误。只需执行单项检查或构建时应使用 `--only`，避免不必要的完整
> 初始化。

常用单项任务：

```bash
uv run python src/scripts/initialization/main.py --only env
uv run python src/scripts/initialization/main.py --only rag
uv run python src/scripts/initialization/main.py --only openlca
```

## 3. 启动完整工作流

```bash
opencode run --command whole-lca
```

该命令以 `workspace/inputs/plan.md` 作为唯一计划输入，完成计划门禁、证据检索、LCI
生成与审查、预检、导入读回、LCIA 计算和报告归档，并在以下固定路径保留证据：

- `workspace/memory/`
- `workspace/outputs/LCI/`
- `workspace/outputs/reports/`

不要仅根据命令退出码判断工作流是否完成。应检查
`workspace/memory/manifest.json`；`needs_input`、`needs_review` 和 `failed` 都表示
需要继续处理。

## 4. 修订既有结果

修订前必须保留上一轮的以下内容：

- `workspace/inputs/plan.md`
- `workspace/memory/manifest.json`
- `workspace/outputs/LCI/`
- `workspace/outputs/reports/lca_report.md`

将修改意见写入 `workspace/inputs/revise.md`，然后运行：

```bash
opencode run --command revise-lca
```

流程会保存直接上一轮 baseline，完整重建 LCI、重新导入、重算 LCIA，并覆盖当前最终
报告。缺少必需基线时会受控停止，不应手工拼接不完整结果。

## 5. 手动同步与清理

只同步用户资料到知识库输入目录：

```bash
uv run python src/scripts/file_sync/main.py --direction upload-to-work
```

预览 workspace 清理范围：

```bash
uv run python src/scripts/clean_dir/main.py --dry-run --target workspace
```

确认后执行：

```bash
uv run python src/scripts/clean_dir/main.py --yes --target workspace
```

> 注意：清理会删除生成产物。始终先查看 dry-run 输出，并确认输入文件不在删除范围内。
