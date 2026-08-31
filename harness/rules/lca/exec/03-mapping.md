# 03 背景映射与 LCI（sub-executor）

产物字段与 JSON-LD 写入约定见 `harness/specs/03-dataset-mapping/`。本文件只写执行口径。

- 首次调用 openLCA 前做 `health_check`。名称与 UUID 必须用正式工具查询，禁止编造。
- 不得用错误功能冒充（再生粒料不得代替原生，除非计划要求）。
- 精确地域无候选时自行选区域市场或 `RoW`/`GLO`，记下请求值、选用值和理由。
- 可留档的匹配自行选择并写入 mapping。审查通过前禁止 `import_lci`。
