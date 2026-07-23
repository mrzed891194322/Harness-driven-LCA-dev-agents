---
name: workflow-main
description: 通过分阶段的计划接收、证据检索、最多三次 LCI 审查循环、openLCA 写入预检、自动导入回读、LCIA 计算及结果归档，来无人值守地执行已有的 LCA 执行计划（plan.md）。适用于本仓库中的 whole-lca 或端到端 plan-to-LCIA 运行。
---

# 全生命周期评价（Whole-LCA）主工作流

将此技能作为 Codex 平台适配器使用。将 `harness/specs/public/` 与 `harness/specs/01-*` 至 `07-*` 视为运行契约、阶段规则和结果结构的唯一来源；不要重述或弱化其中的内容。

## 启动运行

1. 在读取计划之前，先运行 `uv run python src/scripts/file_sync/main.py --direction upload-to-work`，将参考资料同步到 harness 知识源。当环境需要时，可使用可写的临时 uv 缓存。
2. 仅使用 `workspace/inputs/plan.md` 作为计划输入。
3. 完整阅读 `harness/specs/public/README.md` 及其运行契约。只在进入某一阶段前完整阅读对应编号目录的 `README.md` 和阶段 spec；在生成相应产物前立即读取公共目录中的对应 JSON schema 或报告模板。不得在启动时一次加载全部七个阶段规范。
4. 如果当前活动的 Agent 不是 `major-orchestrator`，则仅生成一个 `major-orchestrator` 实例，并传递 `platform=codex`、计划路径以及指示其进入预检阶段的指令。不要在根线程中执行其业务阶段。

## 无人值守中继

`major-orchestrator` 仅可生成 `sub-executor` 和 `eval-reviewer`。等待其返回结果。

- 如果返回 `needs_input`、`needs_review` 或 `failed`，则保留已记录的状态并报告确切问题。
- 运行启动即授权在当前预检范围与哈希完全一致时执行导入。预检通过后由同一编排器立即继续第 06 阶段，不得返回 `awaiting_confirmation` 或请求用户额外确认。
- `import_lci` 会重新预检。任何范围或哈希变化都必须拒绝写入、保存结构化失败证据并结束运行，不得等待用户输入。

## 强制完成

- 将每个阶段/审查/交接都保存到 `workspace/memory/` 的固定结构中；同一次运行内不要覆盖历史记录，不生成运行 ID 或运行 ID 目录。
- 严格按 `01-plan-quality-gate` 至 `07-lcia-calculation-reporting` 的顺序推进，并使用当前阶段规范决定进入、通过或停止。
- 在第三次 LCI 审查失败后停止，不再进行第四次自动修复。
- 要求达到以下条件后才能标记为 `completed`：零导入失败、无断裂的模型链接、非空的原始 LCIA 结果、已释放的计算资源，以及所有必需的结果产物。
- 工作流产物直接保存在 `workspace/memory/`、`workspace/outputs/LCI/` 和 `workspace/outputs/reports/`，返回后不执行反向文件同步。
