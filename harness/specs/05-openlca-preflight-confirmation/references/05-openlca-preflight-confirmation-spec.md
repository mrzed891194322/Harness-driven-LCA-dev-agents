# 05 Whole-LCA openLCA 写入预检规范

## 1. 进入条件

只有第 04 阶段 review 状态为 `passed`，且不存在 `critical` 或 `major` 未解决问题时，才允许执行写入预检。

## 2. 预检

- 必须使用 `preflight_import_lci`，保存完整返回值、`preflight_hash`、活动数据库标识、目标分类、待创建实体及覆盖/删除范围。
- 必须显式传入 `database_name` 或配置 `OPENLCA_DATABASE_NAME`；仅有 IPC endpoint 不能证明活动数据库身份。
- 必须保存 `lci_fingerprint`、`target_scope_fingerprint`、`background_provider_fingerprint` 和逐项 Provider 检查。背景 Provider 不存在或不输出引用 flow 时预检失败；`expectedProviderGeography` 与数据库地域代码/名称不一致只保留为诊断，不得在 UUID 与输出 flow 均一致时单独阻断预检。
- `lci_dir` 默认且规范位置为 `workspace/outputs/LCI`。为连续改进运行中可追踪的兼容转换，工具也可读取 `workspace/tmp/` 下的具体子目录；不得直接使用 `workspace/tmp` 根目录、`workspace/inputs` 或项目外路径。预检哈希必须覆盖实际传入目录的完整 LCI。
- 预检本身不写数据库。启动 whole-LCA 即授权在本次预检范围与哈希完全一致时执行导入。
- 保存完整预检证据后保持 manifest 为 `running`，并立即把当前 `preflight_hash` 交给第 06 阶段；不得设置 `awaiting_confirmation` 或等待用户输入。

## 3. 哈希门禁

- `preflight_hash` 只覆盖对应的 LCI 文件、明确数据库身份、目标分类变更范围和实际引用的背景 Provider；活动数据库中无关实体的变化不得使哈希漂移。
- 导入前必须重新预检；文件、数据库目标、分类或覆盖范围变化时哈希必须变化，旧哈希立即失效。
- 只有重新预检结果与当前哈希一致时才可写入。哈希不一致时保存结构化拒绝报告，将 manifest 置为 `failed` 并结束，不得请求用户确认。
