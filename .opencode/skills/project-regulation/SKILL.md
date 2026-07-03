---
name: project-regulation
description: 本项目规则与边界的强路由入口。所有 agent 必须加载本技能；涉及代码、命令、文件、目录或子智能体调用时，按本文件揭示的 harness/rules 路径读取最小必要规则。
---

# 项目规范强路由 (project-regulation)

本技能负责把任务路由到 `harness/rules/` 中的最小必要规则，同时在路由前揭示少量不可绕过的通用护栏。

`harness/rules/` 是规则事实来源。不要一次性读取全部规则；按下方路由卡片读取。

> [!IMPORTANT]
> **通用护栏**
> - 任何 Python 命令必须使用项目 uv 环境：`uv run python ...`。
> - 不得直接调用系统 `python`、`python3`、`py` 或自行创建其他虚拟环境。
> - 严禁创建临时 Python 脚本；不得在 `workspace/tmp/` 或其他目录写入探索性、一次性、测试性脚本。
> - 不得绕过已有正式工具自行实现连接检测、数据库遍历、UUID 查询、RAG 查询、文件清理或导入逻辑。
> - 新增或修改正式脚本时，必须复用现有结构，放入正式目录，并同步相邻 README 或说明文档。
> - 调用子 Agent 时，必须在任务提示中显式传递本技能的硬约束和应读取的 harness 入口；不得只说“遵守规范”。

---

## 必读路由卡片

请根据当前任务类型读取对应的规则入口：

### A. 目录、文件位置、读写边界
适用：不确定文件放哪里、是否能写、workspace/harness/GUI/scripts 职责。

读取顺序：
1. `harness/rules/directory-structure/README.md`
2. 按该 README 路由继续读取 `instructions/global-structure.md` 或 `instructions/harness-structure.md`

### B. 代码、命令、Python、正式脚本
适用：写代码、改代码、运行命令、运行 Python、检查工具安全边界。

读取顺序：
1. `harness/rules/coding-specification/README.md`
2. `harness/rules/coding-specification/instructions/general_specification.md`
3. 涉及 Python 时再读 `harness/rules/coding-specification/instructions/python_specification.md`

### C. 子 Agent 调用与权限
适用：调用 doc-handler、eval-executor、code-builder、data-processor，或修改 agent frontmatter 的 `permission.task`。

读取顺序：
1. `harness/rules/subagent-invocation/README.md`
2. `harness/rules/subagent-invocation/instructions/invocation_guidance.md`

### D. 无法判断
读取：`harness/rules/README.md`
