# 05 Whole-LCA openLCA 写入预检规范

## 1. 进入条件

只有第 04 阶段 review 状态为 `passed`，且不存在 `critical` 或 `major` 未解决问题时，才允许执行写入预检。

## 2. 预检

- 必须使用 `preflight_import_lci`，保存完整返回值、`preflight_hash`、活动数据库标识、目标分类、待创建实体及覆盖/删除范围。
- 预检本身不写数据库。启动 whole-LCA 即授权在本次预检范围与哈希完全一致时执行导入。
- 保存完整预检证据后保持 manifest 为 `running`，并立即把当前 `preflight_hash` 交给第 06 阶段；不得设置 `awaiting_confirmation` 或等待用户输入。

## 3. 哈希门禁

- `preflight_hash` 只覆盖对应的 LCI 文件、活动数据库、目标分类和完整变更范围。
- 导入前必须重新预检；文件、数据库目标、分类或覆盖范围变化时哈希必须变化，旧哈希立即失效。
- 只有重新预检结果与当前哈希一致时才可写入。哈希不一致时保存结构化拒绝报告，将 manifest 置为 `failed` 并结束，不得请求用户确认。
