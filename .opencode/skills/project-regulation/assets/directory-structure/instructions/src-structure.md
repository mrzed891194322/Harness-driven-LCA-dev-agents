# src 内部目录规范与 knowledge 目录规范

> **上下文提示**：如需了解项目整体结构（根目录、输入输出等），请另读同目录下的 `global-structure.md`。
>
> 本文件由 `project-regulation` skill 维护，聚焦**项目核心代码（src/）**与**项目知识库（knowledge/）**内部的目录结构、模块职责与关键约束。

---

## 1. 目录结构

### 1.1 `src/` (核心代码)
```text
src/
├── GUI/                    # Gradio 图形化控制面板界面代码
├── rules/                  # 项目运行与智能体行为规范
├── scripts/                # 环境部署、初始化、清理等辅助脚本
├── specs/                  # 各种 LCA 或技术规范规约文件
└── tools/                  # 各种独立工具脚本
```

### 1.2 `knowledge/` (知识库主目录)
```text
knowledge/
├── inputs/                 # 原始输入目录
│   ├── static_ref/         # 全局静态参考知识库（包含 standards, openlca_manual 等子目录）
│   ├── user_data/          # 原始上传数据目录
│   └── user_file/          # 零散上传文件目录
└── rag_db/                 # 动态转换生成的 RAG 向量数据库
```

### 1.3 `workspace/` (运行工作区)
```text
workspace/
├── LCI/                    # 导出的 Flows/Processes/ProductSystems JSON 文件与 mapping 报告
├── data/                   # 数据清洗转换的 Python 脚本及产生的中间数据
├── logs/                   # 系统运行时生成的日志文件
├── memory/                 # 智能体运行过程中的长期与短期记忆存储
├── plan/                   # 当前项目在运行中的内部设计执行方案与 Todo 清单
├── report/                 # 最终生成的 LCA 分析与评估报告
└── tmp/                    # 运行时临时缓存及 AI Agent 的“阅后即焚”脚本
```

---

## 2. 各目录详细约定

### 2.1 `knowledge/rag_db/` — 动态生成的 RAG 向量数据库
- **职责**：放的是以 RAG 形式构建的向量数据库。它通过 embedding 模型动态生成与读取，用于供 Agent 在解决特定 LCA 问题时作为“运行时热知识”进行检索，其内容直接来源于 `knowledge/inputs/` 中沉淀的静态规范与原始文件。

### 2.2 `workspace/data/` — 数据预处理与中间状态
- **职责**：处理来自于 `knowledge/inputs/user_data/` 的原始输入数据。包含数据清洗和转换的脚本文件（例如 Python 脚本），以及脚本处理后生成的中间输出文件（例如提取好的标准化 LCA 清单数据）。
- **约束**：原始数据不应直接复制到此处，而是由脚本动态读取 `knowledge/inputs/` 下的文件进行生成。

### 2.3 `workspace/plan/` — 具体执行规划与策略
- **职责**：存放代码和逻辑层面的执行设计文档。
- **关联**：相对于 `knowledge/plan.md` 所给出的粗粒度需求或产品级目标，`workspace/plan/` 里存放技术视角的细致执行方案 (`execution_plan.md`) 和多 Agent 协同拆解后的子任务与答复清单 (`todo_list.md`)。

### 2.4 `workspace/LCI/` — 清单数据输出
- **职责**：存放生成的用于导入 openLCA 的 Flows, Processes 和 Product Systems 结构化 JSON 实体配置，以及人类可读的映射报告 (`human_readable_mapping.md`)。

### 2.5 `workspace/tmp/` — 临时文件目录
- **职责**：存放运行时的所有临时缓存文件。
- **重要约束**：AI Agent 在执行过程中为了做实验、运行测试代码或探索环境等所编写的“阅后即焚”脚本（临时脚本），**必须并且只能**存放在此目录。不能将测试代码到处散落。

---

## 3. 开发执行流程推荐

1. **输入解析**：主 Agent 分析项目根目录的 `knowledge/plan.md` 需求文档与 `knowledge/inputs/user_data/` 数据。
2. **规划细化**：在 `workspace/plan/` 目录下将需求拆解出更具体的技术路线和执行清单。
3. **数据清洗**：在 `workspace/data/` 目录下编写和运行脚本，将原始数据转换提炼成后续流程能直接使用的标准化数据。
4. **知识填充与检索**：如果遇到复杂的 LCA 标准或特殊换算资料，系统会通过 embedding 模型将其构建为 RAG 知识库存放于 `knowledge/rag_db/`，Agent 可在后续处理环节动态检索读取。
5. **清单设计与导入**：在 `workspace/LCI/` 生成 openLCA JSON 结构，并将其导入 openLCA 数据库。
6. **归档与交付**：检查无误的结果导出至根目录 `output/`。
