---
name: evaluate-lca-quality
description: 对 whole-lca 运行的完整证据包进行 ISO 14040/14044 对齐的质量评估，覆盖目标与范围、LCI、LCIA、解释、报告、公开比较和关键审查，并产出标准化 JSON 评分与逐项 Markdown 表格报告。适用于用户要求评估、打分、复核或比较 LCA 报告及其底层证据时。
---

# 评估 LCA 质量

把 `.codex/specs/lca-quality-evaluation/` 视为评分、schema、rubric 和报告结构的唯一来源。不要在本技能中另行解释或修改评分规则。

## 建立评估范围

1. 接受 `run_id` 或 `workspace/logs/whole-lca/<run_id>/manifest.json`。拒绝把单独的 `lca_report.md` 当作完整证据；缺失证据按规范评分，而不是静默忽略。
2. 完整阅读 spec 索引和 `evaluation_spec.md`，再读取 `rubric.json`。在写 JSON 前读取 score schema。
3. 创建新的 `review_id`，格式为 `YYYYMMDDTHHMMSSZ-<8 位小写十六进制>`，目标目录固定为 `workspace/eval/lca-quality/<run_id>/<review_id>/`。目录已存在时生成新 ID，不覆盖历史。
4. 只读取并哈希计划、日志、LCI 和结果证据。禁止修改、补写或修复被评对象，禁止调用 openLCA 写入工具，禁止生成或委派其他 Agent。

## 核对标准与证据

1. 先调用 `list_rag_libraries` 确认 standards 库可用，再用最小查询定位适用条款。
2. 回读命中结果给出的 ISO 原文路径和定位；记录标准版本、原文 SHA-256 和实际使用的条款。RAG 片段不是最终证据。
3. 从执行计划确定研究类型、用途、受众、第三方沟通、公开比较意图、LCIA 可选元素和关键审查类型。没有证据时使用 `unresolved`，不要猜测不适用。
4. 按 rubric 的固定 `artifact_coverage` 检查整个证据包，记录每个实际文件的路径、哈希、文件状态和 schema 状态。通配路径需要展开到每个实际文件；零匹配时记录一个缺失 artifact。

## 完成逐项评价

1. 输出 rubric 中全部检查项，保持 ID、标题、维度和标准引用不变。
2. 逐项填写适用性、门禁状态、0–3 等级、精确证据、发现、责任建议和复审条件。`not_applicable` 使用 `null` 等级并给出证据充分的理由。
3. 对 `fail` 或 `needs_human_review` 创建唯一 `LCAQ-<criterion-id>-<四位序号>` issue。客观缺失使用 `fail`；只有材料存在但判断必须由合格人员负责时使用 `needs_human_review`。
4. 对每个维度取所有非 `not_applicable` 项的最低等级，并计算 0/1/2/3 分布。总体状态严格按 `fail > needs_human_review > conditional_pass > pass`。
5. 未支持的 workflow contract 版本必须进入 `needs_human_review`。不得输出百分制、平均总分、ISO 认证或关键审查通过声明。

## 写入与验证

1. 将唯一结构化结果写为 `lca_quality_score.json`。
2. 运行：

```bash
uv run python .codex/skills/evaluate-lca-quality/scripts/render_quality_report.py \
  --input <score-json> \
  --output <same-directory>/lca_quality_report.md
```

3. 如果 schema 或跨字段语义校验失败，只修评分 JSON 后重新运行。不得手改生成的 Markdown。
4. 再次计算所有输入哈希，确认被评对象未变化。向用户返回总体状态、主要失败/人工审查项和两个输出路径。
