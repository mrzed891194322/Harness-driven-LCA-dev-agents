# 代码维护指南

## 适用范围

本文件只服务于代码修改、审查、调试和重构。项目是面向 Codex 与 OpenCode 的受控 Whole-LCA harness，覆盖计划门禁、证据检索、LCI 构建与审查、openLCA 预检/导入/计算、报告归档和质量评价。

代码维护任务不得自行启动 Whole-LCA、LCA 计算或质量评价。用户明确要求执行这些任务时，应改用对应 skill 和 Agent 工作流，不以本文件替代业务运行契约。

## 目录职责

| 路径 | 职责 |
| --- | --- |
| `.codex/`、`.opencode/` | Codex/OpenCode 平台配置、skills、agents、命令和平台专用评价契约 |
| `harness/specs/` | 公共工作流状态机、JSON schema、报告模板及 01–07 阶段规范；是跨平台运行语义的来源 |
| `harness/rules/` | 跨任务的知识检索、openLCA 和代码/目录约束 |
| `harness/tools/` | `query_rag`、`control_openlca` 等 MCP 工具及其离线测试 |
| `harness/knowledge/` | 静态标准、openLCA 手册、同步后的用户资料和生成的 RAG 数据库 |
| `src/GUI/` | Gradio 界面、事件、组件和 GUI 业务函数 |
| `src/scripts/` | 初始化、文件同步、清理、环境准备和 GUI 启停等维护脚本 |
| `workspace/` | 用户输入、运行记忆和运行结果；不是源码目录或测试夹具目录 |

## 关键入口与固定路径

- Codex Whole-LCA 入口：`$workflow-main`，实现位于 `.codex/skills/workflow-main/SKILL.md`。
- OpenCode Whole-LCA 入口：`/whole-lca`，命令位于 `.opencode/commands/whole-lca.md`，并加载 `.opencode/skills/workflow-main/SKILL.md`。
- Codex 质量评价入口：`$evaluate-lca-quality` 或项目注册的 `lca-quality-evaluator`，契约位于 `.codex/specs/lca-quality-evaluation/`。
- 唯一计划输入：`workspace/inputs/plan.md`。
- 运行状态与阶段证据：`workspace/memory/`。
- LCI 产物：`workspace/outputs/LCI/`。
- 导入、模型图、LCIA 和最终报告：`workspace/outputs/reports/`。
- 用户资料链路：`workspace/inputs/references/{file,data}/` 经 `src/scripts/file_sync/main.py --direction upload-to-work` 同步到 `harness/knowledge/inputs/user_ref/{file,data}/`，再由 RAG 初始化代码建立对应知识库。

这些路径是运行契约的一部分。不要恢复旧的 `workspace/plan/`、`workspace/LCI/`、`workspace/results/` 或按运行 ID 分层的结果目录。

## 修改定位

| 变更内容 | 首要修改位置 | 同步检查 |
| --- | --- | --- |
| 状态机、阶段、schema、模板或产物语义 | `harness/specs/public/` 与对应 `harness/specs/01-*`–`07-*` | 两个平台 adapter、质量 rubric、公共契约测试 |
| Codex 行为 | `.codex/config.toml`、`.codex/skills/`、`.codex/agents/` | `harness/specs/public/references/scripts/tests/test_platform_config.py` |
| OpenCode 行为 | `.opencode/opencode.json`、`.opencode/commands/`、`.opencode/skills/`、`.opencode/agents/` | 同一平台配置测试及 Codex 语义一致性 |
| openLCA 查询、预检、导入、读回或计算 | `harness/tools/control_openlca/`、`harness/rules/openlca-operation/README.md` | `harness/tools/control_openlca/tests/` 和阶段 05–07 契约 |
| RAG 检索、建库或用户知识源 | `harness/tools/query_rag/`、`harness/rules/knowledge-retrieval/README.md`、`src/scripts/initialization/rag_init/` | 对应 tool、建库和文件同步测试 |
| 初始化、同步、清理、环境或 GUI 启停 | `src/scripts/` | 对应脚本内 tests、固定 workspace 路径 |
| GUI 页面或交互 | `src/GUI/` | `src/GUI/README.md`、事件/组件调用链和相关脚本 |
| LCA 质量评分、schema 或报告 | `.codex/specs/lca-quality-evaluation/` | `.codex/skills/evaluate-lca-quality/`、rubric 覆盖和质量契约测试 |

修改前先用 `rg` 定位引用和测试；优先修改语义来源，再更新 adapter。不要把公共状态机复制进平台 skill 或 agent。

## 契约联动

- `.codex` 与 `.opencode` 是 `harness/specs` 的 adapter。共享状态、阶段顺序、终止条件和产物 schema 只在 harness 契约中定义。
- schema、必需产物、模板、状态语义或固定路径发生变化时，必须在同一变更中更新 `.codex/specs/lca-quality-evaluation/references/rubric.json`、相关评价 schema/模板以及公共和质量契约测试。
- `workspace/outputs/LCI/` 中的实体经 `control_openlca` 预检、导入、读回和计算后，在 `workspace/outputs/reports/` 形成结构化证据；阶段、审查和 Agent 交接证据写入 `workspace/memory/`。
- 改动跨平台公共行为时，同时检查 Codex 与 OpenCode adapter；平台能力差异应保留在各自目录，不得反向污染公共契约。

## 验证

从仓库根目录运行与改动范围匹配的最小测试集：

```bash
# 平台配置、公共状态机、schema 和 workflow 契约
uv run python -m unittest discover -s harness/specs/public/references/scripts/tests -v

# LCA 质量评价 schema、rubric 和报告契约
uv run python -m unittest discover -s .codex/specs/lca-quality-evaluation/references/scripts/tests -v

# openLCA MCP 离线测试（mock IPC，不需要运行 openLCA）
uv run python -m unittest discover -s harness/tools/control_openlca/tests -v

# RAG 查询、建库和文件同步
uv run python -m unittest discover -s harness/tools/query_rag/tests -v
uv run python -m unittest discover -s src/scripts/initialization/rag_init/tests -v
uv run python -m unittest discover -s src/scripts/file_sync/tests -v
```

路径或配置变更至少补充以下检查：

```bash
uv run python -c "import tomllib; tomllib.load(open('.codex/config.toml', 'rb'))"
rg -n "workspace/(inputs/plan\.md|memory|outputs/LCI|outputs/reports)" .codex .opencode harness src
uv run python -m compileall -q src harness .codex/specs/lca-quality-evaluation/references/scripts
git diff --check
```

测试必须使用临时目录或仓库内的测试资源，不得读取或改写真实 `workspace` 运行产物。

## 禁止事项

- 不因代码维护任务调用 `$workflow-main`、`/whole-lca`、openLCA 写入工具或质量评价 Agent。
- 不修改 `workspace/inputs/plan.md`、`workspace/inputs/references/` 或用户运行产物，除非用户明确要求的是对应业务任务。
- 不把 `workspace/memory/`、`workspace/outputs/` 或生成的 `harness/knowledge/rag_db/` 当作源码、金标或应提交的修复位置。
- 不通过修改平台 adapter 绕过共享 schema、预检哈希、审查次数或终止状态。
