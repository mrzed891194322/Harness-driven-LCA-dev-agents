# harness 目录结构规范 (Harness Structure)

## 1. 内部目录树

```text
harness/
├── knowledge/              # 知识库与原始数据 (inputs, rag_db)
│   ├── inputs/             # 原始输入数据 (static_ref, user_ref)
│   └── rag_db/             # 动态转换生成的 RAG 向量数据库
├── rules/                  # 项目运行与智能体行为规范
├── specs/                  # LCA 标准规约与技术指南
└── tools/                  # LCA 独立工具包 (如 openLCA 与 RAG 工具)
```

## 2. 核心子目录说明

* **`knowledge/inputs/`**：存放静态参考库或用户上传的原始数据，作为读取输入。
* **`knowledge/rag_db/`**：通过 embedding 动态生成的向量库，用于运行时的 RAG 检索。
* **`tools/`**：封装好的 openLCA 数据库操作或向量库控制脚本，供 Agent 任务调用。
