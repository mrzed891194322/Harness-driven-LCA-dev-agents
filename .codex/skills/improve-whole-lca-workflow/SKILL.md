---
name: improve-whole-lca-workflow
description: 从干净的 openLCA 与 workspace 前向运行 Whole-LCA，在不中断业务运行的前提下用 workspace/tmp 临时适配 harness 缺陷，最后统一简化、修复并验证 harness/knowledge 以外的 pipeline、rule、spec、validator 和 tool。适用于改进、压力测试、回归验证或修复 Whole-LCA harness；只有用户在原始提示词中明确要求同时检查 LCA 质量时才执行质量评价。
---

# 持续改进 Whole-LCA 工作流

把本技能作为一次从真实运行到最终修正的闭环。业务执行只调用 `$workflow-main`；质量评价
只在显式启用时调用 `$evaluate-lca-quality`。不要复制编号阶段、schema、rubric 或 LCA
判定语义。

## 权限与时序

本任务混合代码维护和 Whole-LCA 运行：

- 修改代码前完整读取 `.codex/AGENTS.md`，仅用于最终代码维护。
- 执行 Whole-LCA、LCA 计算或质量评价时不要读取或传递 `.codex/AGENTS.md`；严格使用对应
  skill 和 Agent 工作流。
- 运行期间禁止修改任何 tracked 文件。只在 `workspace/tmp/` 创建临时接口文件、兼容副本、
  参数或诊断材料。
- 只有完成业务结论、`issues.md` 和可选 `eval.md` 后，才允许永久修改
  `harness/`；始终排除 `harness/knowledge/`。
- 不修改计划、用户资料、背景数据库、canonical 运行证据或质量评价对象。
- 不伪造证据，不静默改写阶段状态，不用 workaround 绕过必要的 openLCA 写入安全约束。

## 1. 建立无历史基线

记录启动 UTC、Git commit、工作树、计划 SHA-256 和初始 diff。禁止读取
`docs/dev/issues/`、其已解决目录和任何历史 `docs/dev/walkthrough/` 内容；不得沿用历史
issue 结论或 ID。

生成唯一 `run-id`，格式为 `whole-lca-improvement-YYYYMMDDTHHMMSSZ`，并为本轮保留：

```text
docs/dev/walkthrough/<run-id>/
├── issues.md
├── eval.md       # 仅显式启用质量评价时存在
└── README.md
```

目录已存在时生成新时间戳，不读取或覆盖原目录。开始阶段只保留路径，不用历史文件建立基线。

## 2. 清理 openLCA 与 workspace

先预览 openLCA 当前项目分类下的 ProductSystem、Process 和 Flow：

```bash
uv run python harness/tools/control_openlca/cleanup_output/main.py
```

核对项目分类和实体类型与预期一致后执行：

```bash
uv run python harness/tools/control_openlca/cleanup_output/main.py --yes
```

再预览 workspace 清理：

```bash
uv run python src/scripts/clean_dir/main.py \
  --dry-run --target workspace_without_inputs
```

确认目标不包含 `workspace/inputs/` 后执行：

```bash
uv run python src/scripts/clean_dir/main.py \
  --yes --target workspace_without_inputs
```

用户调用本技能即授权上述规定范围内的清理，不要再次暂停等待确认。任一预览发现目标超出
规定范围时不得执行删除；先修正调用目标。清理完成后创建新的 `workspace/tmp/`。

## 3. 前向运行并持续排障

完整读取 `.codex/skills/workflow-main/SKILL.md`，按其要求同步资料，再启动唯一
`major-orchestrator`，传递 `platform=codex`、`workspace/inputs/plan.md` 和必须持续推进到
明确业务终态的要求。根线程不执行编号业务阶段，不预读阶段规范，也不补造业务证据。

出现错误时先保存原始命令、输出、退出状态、相关输入哈希和证据路径，再判断根因是否来自：

- pipeline、rule、spec、schema 或 validator；
- `harness/tools/` 的接口或实现；
- Agent 偏离、案例数据、权限或外部服务。

不要因可诊断或可临时适配的问题结束运行。保持 tracked 文件不变，并优先采用最小运行时
方案继续，例如：

- 接口不匹配时，在 `workspace/tmp/` 生成符合现有消费者要求的兼容文件，而不是修改接口；
- 参数或格式不匹配时，在 `workspace/tmp/` 保存可追踪的转换输入、输出和哈希；
- 瞬时工具错误时重试、缩小复现并复用同一 orchestrator 继续；
- 需要重跑时从清晰、可回读的业务状态重新进入 `$workflow-main`。

每个临时方案都记录原始输入、转换规则、输出、使用位置、风险和待验证的永久修正。临时文件
不得冒充 canonical 证据，不得改变计划含义，也不得削弱为防止错误 openLCA 写入所必需的
目标和哈希检查。

只有确认外部服务持续不可用、权限无法取得、缺少只能由用户提供的数据，或允许范围外的根因
不存在任何运行时适配时，才受控停止。停止前穷尽安全的重试、只读诊断和 `workspace/tmp/`
适配，并保存阻塞证据。

## 4. 固化本轮结论

获得明确 LCA 报告结论或证据充分的受控停止结论后，创建当前 run 目录并写入
`issues.md`。至少记录：

- Git 与计划基线、业务终态和 LCA 报告结论；
- 每个问题的本轮唯一 ID、严重度、根因类别和精确证据；
- 临时方案及其输入、输出、哈希、限制和实际效果；
- 建议删除、合并、放宽、保留或新增的接口、门禁和 validator；
- 外部阻塞、未解决风险和最终修正的验收条件。

只写本轮观察事实、证据推断和尚待验证假设，不读取历史记录补充内容。

## 5. 按显式请求评价 LCA 质量

检查用户的原始提示词。只有其中明确要求“同时检查 LCA 质量”、评价、评分或等价意图，并且
已经形成明确 LCA 报告结论时，才完整读取
`.codex/skills/evaluate-lca-quality/SKILL.md`，调用注册的 `lca-quality-evaluator` 并等待
完成。默认分支不要执行质量评价。

评价期间禁止修改被评对象。保留评价技能在
`workspace/outputs/reports/lca-quality/<review-id>/` 生成的 canonical JSON 和 Markdown。
把生成的 Markdown 内容归档为当前 run 的 `eval.md`，并在文件开头记录 `review_id`、两个
canonical 输出路径及其 SHA-256；不得手改 canonical 报告。

若用户明确要求评价但尚无 LCA 报告结论，在 `issues.md` 记录“未达到评价前置条件”，不要
用不完整材料冒充本次质量评价。

## 6. 最后统一修正

完成 `issues.md` 和可选 `eval.md` 后，读取当前
`docs/dev/walkthrough/<run-id>/` 中全部文件。此时才开始修改
`harness/`，并始终排除 `harness/knowledge/`。不要修改 `.codex/`、`.opencode/`、`src/`、
GUI、用户输入或本轮运行证据来掩盖根因。

按下列顺序处理每个问题：

1. 用最小确定性复现确认根因和消费者实际需要。
2. 盘点受影响的接口、字段、schema、validator 和阶段门禁，逐项写明必要性。
3. 优先删除、合并、放宽重复、推测性、过度格式化、无消费者或仅服务单一案例的约束。
4. 只有存在明确失败模式、现有简单机制无法覆盖且下游确实依赖时，才保留或新增最小接口或
   门禁。
5. 禁止写入案例 UUID、材料名、数据库内部名、地域常量或额外人工确认。
6. 保留能够证明必要性的安全约束，例如明确的 openLCA 写入目标、与实际写入内容一致的
   预检哈希以及可回读的原始证据；不要把“更严格”本身当作正确性。
7. 对 validator 使用同一原则：只校验消费者实际依赖、数据完整性或写入安全所需的内容。

每个修正都同步更新所在模块的 `README.md`、schema mapping、操作说明及所有直接引用该
行为的文档。不得只修改实现或测试而保留失真的说明。

## 7. 验证并完成 README

对每个修正运行：

1. 原问题的最小复现；
2. 简化后合法输入的正向测试；
3. 真正必要错误的负向测试；
4. 删除或放宽门禁后的兼容性测试；
5. 所有受影响的公共、阶段、rule、pipeline 或 tool 测试；
6. 文档引用搜索、skill validator、TOML/编译检查和 `git diff --check`。

若验证失败，继续留在最终修正阶段调整最小修复并重测，不再回到业务运行阶段引入中途修改。

全部验证完成后最后写 `docs/dev/walkthrough/<run-id>/README.md`，汇总业务结论、实际修正、
删除或削弱的门禁、保留门禁的必要性、同步文档、测试结果、质量评价路径和剩余外部阻塞。
最终返回 run 目录、业务终态、修正范围、验证结果和未解决阻塞。
