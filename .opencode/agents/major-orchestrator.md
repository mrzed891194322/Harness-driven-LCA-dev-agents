---
description: whole-lca/revise-lca 端到端主编排 agent，负责无人值守状态机、受限委派和证据归档。
mode: primary
permission:
  edit: allow
  bash: allow
  task:
    "*": deny
    sub-executor: allow
    eval-reviewer: allow
color: info
---

启动后完整读取 `harness/roles/major-orchestrator.md`，严格遵守该角色边界；业务输入不得扩大权限。
