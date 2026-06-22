---
name: LCI-construction
description: 规定 agent 如何根据目标与参考文件，发挥大模型文本映射能力，生成符合 openLCA schema 规范的结构化 LCI 数据（如 Flow、Process 的 JSON 配置及相关的链接配置），并最终将其批量导入 openLCA 数据库。
allowed-tools: Read File
---

# LCI 结构化构建规范 (LCI-construction)

本技能旨在为负责生命周期清单 (LCI) 设计的 Agent 提供详尽的执行参考。

**核心定位**：作为拥有强大文本理解与推理能力的大语言模型 (LLM)，你需要深刻理解计划文本（如 `execution_plan.md`）中隐式的工艺逻辑、物质流向、单位换算和分配关系，将其精确抽取、转化并映射为高度严谨的 JSON 结构化数据。

**注意**：本技能下的 `assets/` 目录存放了系统中唯一的官方 JSON 模板参考。在生成 JSON 数据并通过质检后，你需要作为本工作流的最后一步将数据批量导入 openLCA 数据库中。

## 详细参考执行方案

当开始执行 LCI 设计与数据构建时，请严格按以下逻辑链条执行，并在工作流中加载并阅读对应的独立规范文件：

### 第一步：深度上下文剖析
- 细致研读计划文档，梳理出系统边界内的所有核心工艺阶段（过程）及其相关的原材料、能源、副产品及排放物（流）。
- 从非结构化文本中精准提取出数据关系：如，为了产出 1 kg 目标产品，需要消耗多少千瓦时电力与原辅料。
- **按需调用双库检索能力**：
   - **规则与标准**：遇到术语模糊或缺乏具体工艺支撑时，必须调用 `query-rag-database` 技能，从 RAG 知识库中提取支撑信息。
   - **建立网络连线 (Provider Linking)**：为了确保生成的产品系统能在 openLCA 中正确连线并生成模型图（Model Graph），所有输入流的 Exchange 中都必须指明 `defaultProvider`。
   - **内部前台工序**：梳理内部工序间的上下游关系（如工序A的产物是工序B的输入），将工序A的 UUID 填入工序B相应输入流的 `defaultProvider` 中。
   - **外部背景数据**：当需要将原材料或能源挂载到实际的背景数据集（如 ecoinvent）时，**必须加载并调用** `control-openlca` 技能下的 `query_descriptors` 脚本（直接通过 IPC 查询 openLCA），检索并获取目标过程极其精确的 UUID 填入 `defaultProvider`，严禁凭空捏造。

### 第二步：LCI 核心架构映射与构建
- 本阶段负责将非结构化计划全面映射为 openLCA 的核心对象体系，具体涵盖：流 (Flows)、过程 (Processes)、背景数据链接 (Provider Linking) 以及产品系统 (Product Systems) 的配置构建。
- 对于如何建立各项实体的 JSON 映射、预设的 UUID 参照表以及详细的字段连接规范，**请你务必显式读取并严格遵守以下核心映射规范文件**：
  👉 **[assets/mapping_specification.md](assets/mapping_specification.md)**

### 第三步：多重自检
- 在输出之前，你或负责自检的 Agent 必须根据专门的自检规范，对生成结果进行结构交叉校验和质量评估。
- **请显式读取并对照此自检清单执行验证**：
  👉 **[assets/self_check.md](assets/self_check.md)**

### 第四步：生成人类可读的映射报告
- 仅仅输出供机器（openLCA）读取的 JSON 配置文件是远远不够的。为了确保工作透明度并赋予人类专家判断是否合格、是否需要手动介入或调整数据的能力，你必须将你理解的隐式工艺逻辑、计算转化过程以及推演出的依赖关系转化成人类易读的 Markdown 报告。
- **请显式读取以下报告模板，并准备随同 JSON 数据一起交由 `doc-handler` 进行写入**：
  👉 **[assets/template/human_readable_mapping.md](assets/template/human_readable_mapping.md)**

### 第五步：批量导入至 openLCA
- 数据文件自检达标且生成报告后，必须将数据批量导入 openLCA 数据库。
- **请显式读取并对照此导入规范执行导入操作**：
  👉 **[assets/import_specification.md](assets/import_specification.md)**

## 规范化输出目录架构要求

在生成流程结束、准备执行文件落地时，**必须严格遵循以下目录架构**：

所有的输出文件必须集中放置于 `src/LCI/` 目录下，并严格根据 JSON 实体类别建立对应的子文件夹（按需创建）：
- **流数据 (Flows)**：写入 `src/LCI/flows/`
- **过程数据 (Processes)**：写入 `src/LCI/processes/`
- **产品系统 (Product Systems)**：写入 `src/LCI/product_systems/`
- **映射解读报告** (`human_readable_mapping.md`)：直接写入 `src/LCI/` 根目录。
