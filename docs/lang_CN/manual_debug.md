# 手动调试指南

有 GUI 时按[项目 README](../../README.md) 操作。本文仅用于无图形界面或开发调试：用命令行准备资料、初始化并运行工作流。

## 1. 准备输入文件

- 参考资料：`harness/knowledge/`（扁平目录，唯一落点）
- 计划文件：`workspace/inputs/plan.md`
- 修订意见：`workspace/inputs/revise.md`（仅 revise-lca 需要）

## 2. 初始化前置

执行完整初始化：

```bash
uv run python src/scripts/check_status/main.py
```

默认会清理 workspace 生成物并检查环境与 openLCA 连接。openLCA 前景实体清理由 whole-lca / revise-lca 工作流通过 MCP `cleanup_output` 执行，不在初始化脚本中。

> [!WARNING]
> 默认初始化和 `whole-lca` 都包含清理操作。请先确认活动数据库、项目分类和
> `workspace` 输入无误。只需执行单项检查时应使用 `--only`，避免不必要的完整
> 初始化。

常用单项任务：

```bash
uv run python src/scripts/check_status/main.py --only agents
uv run python src/scripts/check_status/main.py --only openlca
```

## 3. 启动完整工作流

正式入口是各平台一行 CLI，不要把 IDE 对话当成启动器。

```bash
opencode run --command whole-lca
codex exec -s workspace-write '$whole-lca'
claude --agent major-orchestrator -p "/whole-lca" --permission-mode dontAsk
```

该命令以 `workspace/inputs/plan.md` 作为唯一计划输入，完成计划门禁、证据检索、LCI
生成与审查、预检、导入读回、LCIA 计算和报告归档，并在以下固定路径保留证据：

- `workspace/memory/`
- `workspace/outputs/LCI/`
- `workspace/outputs/reports/`

不要仅根据命令退出码判断工作流是否完成。应检查
`workspace/memory/manifest.json`。只有 `completed` 才算完成；`failed` 必须带
`status_reason`，并根据该原因与阶段证据继续处理。

## 4. 修订既有结果

修订前必须保留上一轮的以下内容：

- `workspace/inputs/plan.md`
- `workspace/memory/manifest.json`
- `workspace/outputs/LCI/`
- `workspace/outputs/reports/lca_report.md`

将修改意见写入 `workspace/inputs/revise.md`，然后运行：

```bash
opencode run --command revise-lca
codex exec -s workspace-write '$revise-lca'
claude --agent major-orchestrator -p "/revise-lca" --permission-mode dontAsk
```

工作流启动时会自动执行基线快照、MCP `cleanup_output` 与基线激活。手动调试基线步骤：

```bash
uv run python harness/specs/08-lca-revise-workflow/references/scripts/baseline.py snapshot --yes
# 通过 control_openlca MCP 调用 cleanup_output（先 confirm=false，再 confirm=true）
uv run python harness/specs/08-lca-revise-workflow/references/scripts/baseline.py activate --yes
```

流程会保存直接上一轮 baseline，完整重建 LCI、重新导入、重算 LCIA，并覆盖当前最终
报告。缺少必需基线时会受控停止，不应手工拼接不完整结果。

## 5. 清理

预览 workspace 清理范围：

```bash
uv run python src/scripts/clean_dir/main.py --dry-run --target workspace
```

确认后执行：

```bash
uv run python src/scripts/clean_dir/main.py --yes --target workspace
```

手动清理 openLCA 前景实体时，通过 `control_openlca` MCP 调用 `cleanup_output`（先 `confirm=false` 预览，再 `confirm=true` 删除），或使用 `opencode run --command cleanup-lci`。

> 注意：清理会删除生成产物。始终先查看 dry-run 输出，并确认输入文件不在删除范围内。
