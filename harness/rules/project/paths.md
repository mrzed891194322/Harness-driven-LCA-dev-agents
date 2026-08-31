# 固定路径

```text
workspace/
├── inputs/                 # plan.md、可选 revise.md
├── memory/                 # manifest.json、可选 checklist.md、reviews/；revise 可含 baseline/
├── outputs/
│   ├── inventory/          # extracted-bom.json/.md、process-mapping.json
│   ├── LCI/                # Flows/Processes/Product Systems 与 mapping 报告
│   └── reports/            # MCP 原始返回与 lca_report.md
└── tmp/                    # 运行时临时缓存；严禁在此存放一次性脚本
```

## 约束

- **`workspace/inputs/`**：仅 `plan.md` 与可选 `revise.md`。不得放置参考资料，也不建 `references/` 子树。用户知识只在 `harness/knowledge/`。
- **`harness/knowledge/`**：用户参考资料的唯一落点，扁平目录。
- **`workspace/outputs/inventory/`**：BOM 与工艺映射。GUI「工作细节」渲染 `extracted-bom.json` 与 `process-mapping.json`。不要把这些 JSON 放进 `outputs/LCI/`（导入工具只认 JSON-LD 实体目录）。
- **`workspace/outputs/LCI/`**：仅在 `flows/`、`processes/`、`product_systems/` 中保存一文件一实体的 openLCA JSON-LD，并在根目录保存 `human_readable_mapping.md`。
- **`workspace/memory/`**：`manifest.json`、审查笔记，可选 `checklist.md`。revise-lca 在 `baseline/` 保存直接上一轮的只读 plan、LCI、inventory、reports 和 memory，不递归保留更早 baseline。不要在记忆中记录 SHA-256。
- **`workspace/outputs/reports/`**：MCP 原始返回和最终报告，不再创建运行 ID 子目录。
- 旧运行产物由外部流程在开始前清理；工作流自身不负责删除。
