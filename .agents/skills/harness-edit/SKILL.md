---
name: harness-edit
description: >-
  编辑 harness 装配图和注入内容：工作流 YAML、规则、规格、工具、知识与偏好。
  用户要改阶段、角色、提示词、验收、权限、MCP、Host Action 或计划资料的存放方式时使用。
---

# 编辑 harness 元素

`harness/` 是工作流装配图和注入内容，不是 Python 编排实现。编排引擎在 `src/backend/core/`。要改加载、派工或界面时，改读 `.agents/skills/code-dev/SKILL.md`。

编排在 `harness/workflows/`（`orchestrations/` / `nodes/` / `agents/`）。YAML 只写 ID 和路径，不写任务长文。自然语言放 `rules/`，机器契约放 `specs/`，冲突以 spec 为准。
**默认最佳实践**：有编排节点用三件套（不改文件的 orchestrator 作主 agent + executor 写产物 + reviewer）；薄档可单 executor。详见 [references/workflow.md](references/workflow.md)。

先确定要动的元素，只读那一份参考：

| 元素 | 再读 |
| --- | --- |
| 工作流 YAML：阶段、角色、默认绑定 | [references/workflow.md](references/workflow.md) |
| 给模型看的提示词 | [references/rules.md](references/rules.md) |
| 交付物、验收、权限 | [references/specs.md](references/specs.md) |
| MCP 或 Host Action | [references/tools.md](references/tools.md) |
| 计划与参考资料的存放 | [references/knowledge.md](references/knowledge.md) |
| 输出语言等偏好 | [references/settings.md](references/settings.md) |

改完绑定后跑 `uv run pytest src/tests/t_core -q`。目录约定的长说明在 `docs/guide/lang_CN/harness.md`，只在参考文件不够时再打开。
