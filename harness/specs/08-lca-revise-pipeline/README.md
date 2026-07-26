# 08 Revise-LCA 修订工作流规范

本包只定义从既有 Whole-LCA 结果启动修订所新增的契约。证据检索、LCI
制定与审查、openLCA 预检/导入/读回及 LCIA 计算仍以编号 02–07 阶段包为
唯一来源，不在此复制。

执行 revise-lca 时按顺序完整读取：

1. `references/revise-lca-spec.md`；
2. 写 revision brief 前读取
   `references/schemas/revision-brief.schema.json`；
3. 创建 manifest 前读取
   `references/schemas/workflow-manifest.schema.json`；
4. 生成最终报告前读取
   `references/templates/revision-report-sections.md`。

维护者可使用 `schema_mapping.md` 核对跨目录依赖；它不是运行规范。
