# workspace 目录结构规范 (Workspace Structure)

## 1. 工作区目录树

```text
workspace/
├── inputs/                 # plan.md、可选 revise.md
├── memory/                 # manifest.json、checklist.md、stages/reviews/handoffs；revise 可含 baseline/
├── outputs/
│   ├── LCI/                # Flows/Processes/Product Systems 与 mapping 报告
│   └── reports/            # 导入报告、模型图、LCIA 原始结果与报告
└── tmp/                    # 运行时临时缓存；严禁在此存放 AI 临时脚本
```

## 2. 核心规则与约束

* **输入 (`inputs/`)**：**仅**包含 `plan.md` 与可选的 `revise.md`；不得放置参考资料，也不建 `references/` 子树。用户知识只放在 `harness/knowledge/`。
* **清单实体设计 (`outputs/LCI/`)**：仅在 `flows/`、`processes/`、`product_systems/` 中保存一文件一实体的 openLCA JSON-LD，并在根目录保存 `human_readable_mapping.md`；机器报告写入 `outputs/reports/`。
* **运行记忆 (`memory/`)**：固定保存 `manifest.json`、`checklist.md` 以及 `stages/`、`reviews/`、`handoffs/`。revise-lca 在 `baseline/` 保存直接上一轮的只读 plan、LCI、reports 和 memory，不递归保留更早 baseline；基线由 [`harness/specs/08-lca-revise-workflow/references/scripts/baseline.py`](../../../specs/08-lca-revise-workflow/references/scripts/baseline.py) 快照与激活。不同 Agent 可按阶段任务读取相关记忆；主编排 Agent 负责写入和维护关联。不要在记忆中记录 SHA-256。
* **运行结果 (`outputs/reports/`)**：固定保存导入报告、模型图读回、原始 LCIA 结果、计算清单和最终报告，不再创建运行 ID 子目录。
* **运行前置条件**：旧运行产物由外部流程在开始前清理；工作流自身不负责删除。
* **临时文件约束 (`tmp/`)**：仅用于存放运行工具产生的临时缓存。**严禁**在此或任何其他目录编写“阅后即焚”的探索性或一次性临时脚本。
