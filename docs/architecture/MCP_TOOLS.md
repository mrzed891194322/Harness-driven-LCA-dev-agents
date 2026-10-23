# v5 MCP 工具清单（基于 master da96ab1，2026-10-20）

实际启用的入口：`harness/tools/mcp/control_openlca/workflow_mcp.py`（mcp.yaml 指向它；`main.py` 是旧的独立入口，工具是它的子集）。
“现用阶段”的依据：工作流 YAML 中 03、04 的 executor 和 reviewer 挂 control_openlca，01–04 都挂 lca_artifacts，外加 stage/spec 提示词里提到该工具的地方。
读写一栏：R = 只读；W = 写 openLCA 或 workspace；W! = 破坏性写（删除或覆盖）。

## control_openlca（openLCA IPC）
| 工具 | 用途 | 读写 | 现用阶段 | v5 建议 |
|---|---|---|---|---|
| health_check | 探测 IPC 和当前数据库 | R | 01, 04 | 保留 |
| query_descriptors | 按名称/类型搜描述符，带 outside_project 标记 | R | 03, 04 | 保留 |
| query_descriptors_batch | 一次查最多 50 个关键词 | R | 03 | 保留 |
| get_process_details | 读一个 Process 的元数据和参考交换 | R | 03, 04 | 保留 |
| get_flow_providers | 列出某 Flow 的 provider 过程 | R | 03 | 保留 |
| validate_providers_batch | 校验最多 200 对 process/flow，记录 provider 单位证据 | R（写 workspace 证据） | 03 | 保留 |
| preflight_import_lci | 校验 LCI 目录，列出将新建/覆盖/删除的范围 | R | 03, 04 | 保留 |
| import_lci | 按 preflight 导入 LCI | W!（仅在项目分类内） | 03, 04 | 保留；宿主锁 ③ 再校验分类 |
| reconcile_import | 中断导入后的只读对账 | R | 04 | 保留 |
| resume_import | 续做/替换导入 | W! | 04 | 保留，受锁 ③ 约束 |
| import_status / get_import_operation | 读导入日志 | R | 04 | 合并为一个 |
| get_model_graph | 读 Product System 图、断链 | R | 04 | 保留 |
| calculate_product_system | 计算 LCIA | R（只读计算，会释放结果资源） | 04 | 保留 |
| cleanup_output | 预览/删除项目分类下的实体 | W! | 宿主清理用；agent 不应调用 | agent 不暴露，只给宿主 |

审核者白名单（建议）：只给 R 类工具。

## lca_artifacts
| 工具 | 用途 | 读写 | 现用阶段 | v5 建议 |
|---|---|---|---|---|
| read_artifact | 带校验和读取 workspace 产物片段 | R | 01–04 | 删除：v5 用 pi 的 read 工具 + 宿主读权限 |
| render_report_tables | 用证据替换报告里的表格 | W（报告文件） | 04 | 暂留；以后改成 skill 或格式化 MCP |
| get_rework_status | 04 返工能否复用 raw 证据 | R | 04 | 删除（v5 节点重跑会整体清空） |

## spec_mcp
| 工具 | 用途 | 读写 | 现用阶段 | v5 建议 |
|---|---|---|---|---|
| get_spec | 读本阶段交付规格 | R | 01–04 | 删除：spec 通过 `<deliverable_*>` 分段注入 |
| submit | 提交交付物并验收 | W | 01–04 | 删除：改为固定提交工具 `submit`（宿主内置，见提交计划） |
| status | 交付物状态 | R | 01, 02, 04 | 删除 |
| submit_handoff | 交卷 | W | 02–04 | 删除：并入宿主内置的 `submit`（执行者交付 / 审核者给结论） |

## openLCA 红线（宿主锁 ③）
只允许在分类 `202606-harness-agent-LCA` 内新建/修改/删除；常量 `OPENLCA_PROJECT_CATEGORY` 统一定义（替换现在 `PROJECT_ROOT.name` 的 3 处推导和 `attempt_cleanup.PROJECT_CATEGORY`）。

## openLCA project category (single constant)

`harness/tools/shared/control_openlca/category.py` defines `OPENLCA_PROJECT_CATEGORY = "202606-harness-agent-LCA"` and
`locked_category()`. The three former `PROJECT_ROOT.name` derivations (`mcp/control_openlca/main.py`,
`mcp/control_openlca/workflow_mcp.py`, `shared/control_openlca/cleanup_service.py`) and the copy in `attempt_cleanup.py`
all use it (since C3). The checkout folder name no longer matters (test `t_v5/test_category_constant.py`).
