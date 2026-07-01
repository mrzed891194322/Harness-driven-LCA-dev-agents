# LCI 结构化数据构建与导入规范 (LCI Construction Guidelines)

本规范旨在为负责生命周期清单 (LCI) 设计的 Agent 提供详尽的执行逻辑与步骤参考。

智能体在根据执行计划设计和生成 LCI 数据时，必须遵循以下执行逻辑：

---

## 1. 详细参考执行方案与步骤

### 第一步：深度上下文剖析
- 细致研读计划文档，梳理出系统边界内的所有核心工艺阶段（过程）及其相关的原材料、能源、副产品及排放物（流）。
- 从非结构化文本中精准提取出数据关系（例如：为产出 1 kg 目标产品，需要消耗多少千瓦时电力与原辅料）。
- **按需调用双库检索能力**：
   - **规则与标准**：遇到术语模糊或缺乏具体工艺支撑而产生读取数据库的需求时，应检索 RAG 知识库以提取支撑信息。
   - **建立网络连线 (Provider Linking)**：为了确保生成的产品系统能在 openLCA 中正确连线并生成模型图 (Model Graph)，所有输入流的 Exchange 中都必须指明 `defaultProvider`。
   - **内部前台工序**：梳理内部工序间的上下游关系（如工序A的产物是工序B的输入），将工序A的 UUID 填入工序B相应输入流的 `defaultProvider` 中。
   - **外部背景数据**：当需要将原材料或能源挂载到实际的背景数据集（如 ecoinvent）时，**必须加载并调用** `external-tools` 技能（具体参考 `assets/control-openlca/README.md`）下的 `query_descriptors` 脚本，检索获取目标过程的 UUID 并填入 `defaultProvider`，严禁凭空捏造。

### 第二步：LCI 核心架构映射与构建
- 将非结构化计划全面映射为 openLCA 的核心对象体系（Flows, Processes, Provider Linking 以及 Product Systems）。
- 建立各项实体的 JSON 映射与字段连接规范时，**智能体必须显式读取并遵守**：
  instructions/mapping_specification.md
- 本地参考 JSON 实体模板可查阅 `template/` 目录中的 `flow_example.json`、`process_example.json` 和 `product_system_example.json`。

### 第三步：多重数据自检与 Agent 循环 (Agent Loop)
- 在输出之前，你必须明确调用 sub-agent 对生成结果进行结构交叉校验和质量评估。
- **请要求 eval-executor 显式读取并对照此自检清单执行验证**：
  evaluation/self_check.md
- **请要求 eval-executor 同时显式读取并对照报告模板验证输出**：
  template/human_readable_mapping.md
- eval 环节必须确认最终写入 `src/LCI/human_readable_mapping.md` 的报告严格符合模板结构与元数据要求：文件开头必须保留 YAML front matter（`template_kind: lci_human_readable_mapping` 和 `template_version: "1"`），正文必须保留模板规定的一级/二级标题、核心表格、Mermaid 代码块与“人类审核提示”章节；不得输出缺少模板元数据、章节顺序错乱或无法被 GUI Markdown 页面渲染的报告。
- **构建 Agent 循环**：第一步至第三步在实际执行时应该形成一个闭环（Agent Loop）。如果 sub-agent 的评估结论认为当前结果未达标（仍需修改），你必须根据评估结论返回至第一步或第二步进行修正，随后再次提交评估，如此循环，直到 sub-agent 给出可交付的结论为止。

### 第四步：生成人类可读的映射报告
- 为了确保工作透明度并方便人类专家审查，你必须将你理解的隐式工艺逻辑、计算转化过程以及推演出的依赖关系转化成人类易读的 Markdown 报告。
- **请显式读取并填充以下报告模板**，随 JSON 数据一同输出：
  template/human_readable_mapping.md
- 输出到 `src/LCI/human_readable_mapping.md` 时，必须完整保留模板开头的 YAML front matter。GUI 的 LCI 映射 Tab 会依赖该元数据识别并渲染报告。

### 第五步：批量导入至 openLCA
- 数据文件自检达标且生成报告后，必须将数据批量导入 openLCA 数据库。
- **请显式读取并对照此导入规范执行导入操作**：
  instructions/import_specification.md

---

## 2. 规范化输出目录架构要求

在生成流程结束、准备文件落地时，**必须严格遵循以下目录架构**：
所有的输出文件必须集中放置于 `src/LCI/` 目录下，并严格根据 JSON 实体类别建立对应的子文件夹（按需创建）：
- **流数据 (Flows)**：写入 `src/LCI/flows/`
- **过程数据 (Processes)**：写入 `src/LCI/processes/`
- **产品系统 (Product Systems)**：写入 `src/LCI/product_systems/`
- **映射解读报告** (`human_readable_mapping.md`)：直接写入 `src/LCI/` 根目录。
