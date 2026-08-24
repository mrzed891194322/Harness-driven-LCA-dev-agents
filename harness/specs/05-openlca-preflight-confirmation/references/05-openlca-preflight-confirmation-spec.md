# 05 Whole-LCA openLCA 写入预检规范

## 1. 进入条件

只有第 04 阶段 review 状态为 `passed`，且不存在 `critical` 或 `major` 未解决问题时，才允许执行写入预检。

## 2. 预检

openLCA 工具调用纪律见 `harness/rules/openlca-operation/README.md`。本阶段 additionally 要求：

- 必须使用 `preflight_import_lci`，保存活动数据库标识、目标分类、LCI 目录、待创建实体及覆盖/删除范围。
- 必须显式传入 `database_name` 或配置 `OPENLCA_DATABASE_NAME`；仅有 IPC endpoint 不能证明活动数据库身份。
- 必须保存逐项 Provider 检查。背景 Provider 不存在或不输出引用 flow 时预检失败；`expectedProviderGeography` 与数据库地域代码/名称不一致只保留为诊断，不得在 UUID 与输出 flow 均一致时单独阻断预检。
- 预检必须重新执行 Stage 03 确定性校验；exchange 方向不是显式布尔 `isInput`、前景输入缺少有效 `defaultProvider`，或 Product System 不是统一 auto-link 契约时，在任何数据库读写前返回 `invalid_lci`。
- 预检本身不写数据库。保存 `import_scope`（`database_name`、`category`、`lci_dir`）后保持 manifest 为 `running`，并立即把同一范围交给第 06 阶段；不得设置 `awaiting_confirmation` 或等待用户输入。不要记录 SHA-256 或分项指纹。

## 3. 范围门禁

- 导入范围只覆盖对应的 LCI 目录、明确数据库身份和目标分类。
- 导入前工具会重新预检；库名、分类或 LCI 目录变化时旧范围立即失效。
- 只有重新预检范围与当前 `import_scope` 一致时才可写入。范围不一致时保存结构化拒绝报告，将 manifest 置为 `failed` 并结束，不得请求用户确认。
