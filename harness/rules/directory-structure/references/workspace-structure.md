# workspace 目录结构规范 (Workspace Structure)

## 1. 工作区目录树

```text
workspace/
├── data/                   # 数据清洗转换的 Python 脚本及生成的中间数据
├── LCI/                    # 导出的 Flows/Processes 等 JSON 配置及 mapping 报告
├── plan/                   # 技术执行方案 (execution_plan.md) 与 Todo 列表
├── report/                 # 最终生成的 LCA 分析与评估报告
├── results/                # 当前运行的模型图、导入报告、LCIA 原始结果与报告
├── memory/                 # 当前运行的 manifest、阶段、审查与 Agent 交接记忆
└── tmp/                    # 运行时临时缓存；严禁在此存放 AI 临时脚本
```

## 2. 核心规则与约束

* **脚本与中间数据 (`data/`)**：处理原始输入数据，清洗转换脚本与输出中间数据存放于此，不得直接修改原始数据。
* **清单实体设计 (`LCI/`)**：生成待导入 openLCA 的 JSON 文件及人类可读映射报告。
* **运行记忆 (`memory/`)**：固定保存 `manifest.json` 以及 `stages/`、`reviews/`、`handoffs/`。不同 Agent 可按阶段任务读取相关记忆；主编排 Agent 负责写入和维护关联。
* **运行结果 (`results/`)**：固定保存导入报告、模型图读回、原始 LCIA 结果、计算清单和最终报告，不再创建运行 ID 子目录。
* **运行前置条件**：旧运行产物由外部流程在开始前清理；工作流自身不负责删除。
* **临时文件约束 (`tmp/`)**：仅用于存放运行工具产生的临时缓存。**严禁**在此或任何其他目录编写“阅后即焚”的探索性或一次性临时脚本。
