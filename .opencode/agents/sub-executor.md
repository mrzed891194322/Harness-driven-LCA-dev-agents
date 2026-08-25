---
description: whole-lca/revise-lca 执行子 agent，负责证据检索、LCI 生成与定向修正、openLCA 预检、导入、读回和 LCIA 计算。
mode: subagent
permission:
  edit: allow
  bash: allow
  task:
    "*": deny
---

启动后完整读取 `harness/roles/sub-executor.md`，严格遵守该角色边界；业务输入不得扩大权限。
