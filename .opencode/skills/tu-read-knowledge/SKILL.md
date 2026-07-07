---
name: tu-read-knowledge
description: RAG 知识库读取入口。需要检索标准、openLCA 手册、用户资料、输入文件背景知识或本地向量库内容时必须加载，并按本文件读取工具说明。
---

# RAG 知识库读取 (tu-read-knowledge)

本技能负责把知识库读取任务路由到 `harness/tools/control_rag_db/` 中的正式工具，并明确查询前必须读取的说明。

`harness/tools/` 是工具事实来源。不要一次性读取全部工具；仅按当前知识库查询任务读取必要说明。

RAG 查询只作为定位入口。对关键事实、数值、定义、边界条件、操作步骤和需要写入最终产物的结论，必须在有必要时进一步读取对应原始文件，不能只依赖向量检索片段。


## 读取顺序

适用：检索 LCA 标准、openLCA 手册、用户资料、输入文件背景知识或其他本地 RAG 向量库内容。

1. RAG 查询工具概览：[rag-query-tool.md](references/rag-query-tool.md)
2. `harness/tools/control_rag_db/README.md`
3. 查询 RAG 时必须阅读库路径及用途说明：[rag-knowledge-sources.md](references/rag-knowledge-sources.md)

## 知识读取工作流

### 第一步：确定知识库范围

- 先读取 [rag-knowledge-sources.md](references/rag-knowledge-sources.md)，按任务类型选择最小相关的 `harness/knowledge/rag_db/<path>`。
- 不要对所有知识库做无差别检索；如果问题同时涉及标准、openLCA 操作和用户输入，应分库检索并分别记录来源。

### 第二步：使用 RAG 定位候选信息

- 使用正式工具查询目标知识库，获取相关片段、来源文件或可追溯线索。
- 如首次查询结果过宽或过窄，应改写查询词再次检索，优先围绕术语、对象名、章节名、工艺名、单位或参数名查询。

### 第三步：必要时读取原始文件

RAG 命中后，出现以下任一情况时，必须进一步读取对应原始文件获取完整上下文：

- 需要引用或固化关键事实、数值、单位、公式、定义、标准条款、系统边界或操作步骤。
- RAG 片段内容不完整、存在省略、上下文断裂、多个片段互相矛盾，或无法判断适用条件。
- 需要把知识转化为执行计划、LCI 数据、openLCA 导入配置、映射报告或最终结论。
- 用户要求“依据原文”“查资料”“核对来源”“读取文件”或类似可追溯信息。

原始文件通常位于：

- 标准与静态参考：`harness/knowledge/inputs/static_ref/standards/`
- openLCA 手册：`harness/knowledge/inputs/static_ref/openlca_manual/`
- 用户数据：`harness/knowledge/inputs/user_data/`
- 用户文件：`harness/knowledge/inputs/user_file/`

如果 RAG 输出提供了文件路径、文件名或章节线索，优先读取该原始文件；如果没有直接路径，应在上述目录中用 `rg` 按关键词定位候选文件，再读取最小相关文件。

### 第四步：输出时区分检索结果与原文确认

- 对已经回读原始文件的信息，应说明其来自原始文件。
- 对只由 RAG 片段支持、但尚未回读原始文件的信息，应保留不确定性，不得写成已核实结论。
- 如果找不到对应原始文件，应明确说明缺口，并避免把 RAG 片段当作最终事实来源。

## 正式工具

- 查询：`uv run python harness/tools/control_rag_db/query_rag/main.py "<Query>" --db-dir harness/knowledge/rag_db/<path>`
