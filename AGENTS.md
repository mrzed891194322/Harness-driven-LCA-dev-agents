# AGENTS.md

本仓库用 Web 控制面板驱动一次完整 LCA。用户不通过 IDE 当主编排。

本文件只做路由。接到指令后，按用户要做的事选下面一行，只读那一个技能的 `SKILL.md`，再按技能里的「再读」打开当前需要的文件。不要预读其他技能，也不要一次打开某个技能的全部参考。

| 用户要做的事 | 先读 |
| --- | --- |
| 打开或关闭项目，或环境配置过程中出现问题 | `.agents/skills/proj-ops/SKILL.md` |
| 使用过程中出错，要看后端日志或 openLCA 并给建议 | `.agents/skills/issue-diag/SKILL.md` |
| 改控制面板、启动、编排、进度或结果展示，或把闭环的某一跳接上 | `.agents/skills/code-dev/SKILL.md` |
| 改工作流装配、规则、规格、工具、知识或偏好等 harness 元素 | `.agents/skills/harness-edit/SKILL.md` |

一件事先定一个主技能。打开和关闭项目只走 `proj-ops`。使用中的报错只走 `issue-diag`。改 `src/` 或接通闭环只走 `code-dev`。改 `harness/` 里的装配和注入内容只走 `harness-edit`。主技能做完仍缺另一侧时，再读第二个 `SKILL.md`。

`.agents/skills/` 只给在本仓库里改代码的 agent 用。LCA 工作会话不加载这里的技能。
