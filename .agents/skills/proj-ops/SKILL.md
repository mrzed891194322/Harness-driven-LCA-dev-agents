---
name: proj-ops
description: >-
  打开或关闭本仓库的 Web 控制面板；面板打不开时诊断启动失败；
  使用过程中读后端日志、检查 openLCA，并用文字给出建议。
  用户要打开/关闭项目、面板无法启动，或报告运行报错、导入/计算失败、
  openLCA 连不上或 IPC 忙时使用。
---

# 项目运维

按用户要做的事只打开一份参考，不要一次预读全部：

| 用户要做的事 | 再读 |
| --- | --- |
| 打开、关闭、重启控制面板，或面板打不开 | [references/process.md](references/process.md) |
| 使用中报错、导入或计算失败、openLCA 连不上 / 占用中 | [references/advise.md](references/advise.md) |

只执行参考里的命令与步骤。改控制面板代码或接通闭环时改读 `.agents/skills/code-dev/SKILL.md`。
