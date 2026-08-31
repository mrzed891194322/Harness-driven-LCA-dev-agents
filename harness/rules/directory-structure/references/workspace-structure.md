# workspace 目录结构规范 (Workspace Structure)

## 1. 工作区目录树

```text
workspace/
├── inputs/                 # plan.md、可选 revise.md
├── memory/                 # manifest.json、可选 checklist.md、reviews/；revise 可含 baseline/
├── outputs/
│   ├── inventory/          # extracted-bom.json/.md、process-mapping.json（工作细节看 JSON）
│   ├── LCI/                # Flows/Processes/Product Systems 与 mapping 报告
│   └── reports/            # MCP 原始返回与 lca_report.md
└── tmp/                    # 运行时临时缓存；严禁在此存放 AI 临时脚本
```

## 2. 核心规则与约束

* **输入 (`inputs/`)**：**仅**包含 `plan.md` 与可选的 `revise.md`；不得放置参考资料，也不建 `references/` 子树。用户知识只放在 `harness/knowledge/`。
* **前景清单 (`outputs/inventory/`)**：BOM 与工艺映射。GUI「工作细节」渲染 `extracted-bom.json` 与 `process-mapping.json`。不要把这些 JSON 放进 `outputs/LCI/`（导入工具只认 JSON-LD 实体目录）。
* **清单实体设计 (`outputs/LCI/`)**：仅在 `flows/`、`processes/`、`product_systems/` 中保存一文件一实体的 openLCA JSON-LD，并在根目录保存 `human_readable_mapping.md`；机器原始返回写入 `outputs/reports/`。
* **运行记忆 (`memory/`)**：保存 `manifest.json`、审查笔记，可选 `checklist.md`。revise-lca 在 `baseline/` 保存直接上一轮的只读 plan、LCI、inventory、reports 和 memory，不递归保留更早 baseline；基线由 [`harness/specs/08-lca-revise-workflow/references/scripts/baseline.py`](../../../specs/08-lca-revise-workflow/references/scripts/baseline.py) 快照与激活。不要在记忆中记录 SHA-256。
* **运行结果 (`outputs/reports/`)**：保存 MCP 原始返回和最终报告，不再创建运行 ID 子目录。
* **运行前置条件**：旧运行产物由外部流程在开始前清理；工作流自身不负责删除。
* **临时文件约束 (`tmp/`)**：仅用于存放运行工具产生的临时缓存。**严禁**在此或任何其他目录编写“阅后即焚”的探索性或一次性临时脚本。
