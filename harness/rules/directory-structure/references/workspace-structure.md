# workspace 目录结构规范 (Workspace Structure)

## 1. 工作区目录树

```text
workspace/
├── inputs/                 # plan.md 与 references/{data,file}
├── memory/                 # 当前运行的 manifest、阶段、审查与 Agent 交接记忆
├── outputs/
│   ├── LCI/                # Flows/Processes/Product Systems 与 mapping 报告
│   └── reports/            # 导入报告、模型图、LCIA 原始结果与报告
└── tmp/                    # 运行时临时缓存；严禁在此存放 AI 临时脚本
```

## 2. 核心规则与约束

* **输入 (`inputs/`)**：唯一计划为 `plan.md`，参考资料存放在 `references/data/` 和 `references/file/`。
* **清单实体设计 (`outputs/LCI/`)**：生成待导入 openLCA 的 JSON 文件及人类可读映射报告。
* **运行记忆 (`memory/`)**：固定保存 `manifest.json` 以及 `stages/`、`reviews/`、`handoffs/`。不同 Agent 可按阶段任务读取相关记忆；主编排 Agent 负责写入和维护关联。
* **运行结果 (`outputs/reports/`)**：固定保存导入报告、模型图读回、原始 LCIA 结果、计算清单和最终报告，不再创建运行 ID 子目录。
* **运行前置条件**：旧运行产物由外部流程在开始前清理；工作流自身不负责删除。
* **临时文件约束 (`tmp/`)**：仅用于存放运行工具产生的临时缓存。**严禁**在此或任何其他目录编写“阅后即焚”的探索性或一次性临时脚本。
