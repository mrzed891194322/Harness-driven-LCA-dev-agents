# workspace 目录结构规范 (Workspace Structure)

## 1. 工作区目录树

```text
workspace/
├── data/                   # 数据清洗转换的 Python 脚本及生成的中间数据
├── LCI/                    # 导出的 Flows/Processes 等 JSON 配置及 mapping 报告
├── plan/                   # 技术执行方案 (execution_plan.md) 与 Todo 列表
├── report/                 # 最终生成的 LCA 分析与评估报告
├── logs/                   # 系统运行日志
├── memory/                 # 智能体长期/短期记忆存储
└── tmp/                    # 运行时临时缓存；严禁在此存放 AI 临时脚本
```

## 2. 核心规则与约束

* **脚本与中间数据 (`data/`)**：处理原始输入数据，清洗转换脚本与输出中间数据存放于此，不得直接修改原始数据。
* **清单实体设计 (`LCI/`)**：生成待导入 openLCA 的 JSON 文件及人类可读映射报告。
* **临时文件约束 (`tmp/`)**：仅用于存放运行工具产生的临时缓存。**严禁**在此或任何其他目录编写“阅后即焚”的探索性或一次性临时脚本。
