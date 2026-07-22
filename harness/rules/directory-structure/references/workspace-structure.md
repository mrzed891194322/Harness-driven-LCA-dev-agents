# workspace 目录结构规范 (Workspace Structure)

## 1. 工作区目录树

```text
workspace/
├── data/                   # 数据清洗转换的 Python 脚本及生成的中间数据
├── LCI/                    # 导出的 Flows/Processes 等 JSON 配置及 mapping 报告
├── plan/                   # 技术执行方案 (execution_plan.md) 与 Todo 列表
├── report/                 # 最终生成的 LCA 分析与评估报告
├── logs/                   # 系统运行日志
│   └── whole-lca/<run_id>/ # 端到端运行 manifest、阶段、审查与交接证据
├── results/                # 按 run_id 隔离的模型图、导入报告、LCIA 原始结果与报告
│   └── <run_id>/
├── memory/                 # 智能体长期/短期记忆存储
└── tmp/                    # 运行时临时缓存；严禁在此存放 AI 临时脚本
```

## 2. 核心规则与约束

* **脚本与中间数据 (`data/`)**：处理原始输入数据，清洗转换脚本与输出中间数据存放于此，不得直接修改原始数据。
* **清单实体设计 (`LCI/`)**：生成待导入 openLCA 的 JSON 文件及人类可读映射报告。
* **端到端运行日志 (`logs/whole-lca/<run_id>/`)**：只追加阶段、审查与交接文件，通过稳定 ID、哈希和 manifest 关联；不得覆盖历史审查或交接记录。
* **运行结果 (`results/<run_id>/`)**：保存导入报告、模型图读回、原始 LCIA 结果、计算清单和最终报告，不与其他运行混写。
* **记忆 (`memory/`)**：保留给未来长期记忆工作流；当前 `whole-lca` 不读取或写入该目录。
* **临时文件约束 (`tmp/`)**：仅用于存放运行工具产生的临时缓存。**严禁**在此或任何其他目录编写“阅后即焚”的探索性或一次性临时脚本。
