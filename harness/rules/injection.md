# 规则注入

运行时不再使用本文件按角色×阶段抄路径。任务绑定的规则由 `harness/LCA-main.yaml` 的 `registry.rules`、`defaults.rules`、`assignment.rules` 以及工具关联规则组装。

主编排把规则正文纳入 SDK 任务输入。agent 不要自己扫描 `harness/rules/` 未绑定的文件。
