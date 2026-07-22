# 05 Whole-LCA openLCA 写入预检与确认规范

## 1. 进入条件

只有第 04 阶段 review 状态为 `passed`，且不存在 `critical` 或 `major` 未解决问题时，才允许执行写入预检。

## 2. 预检

- 必须使用 `preflight_import_lci`，保存完整返回值、`preflight_hash`、活动数据库标识、目标分类、待创建实体及覆盖/删除范围。
- 预检不授权任何数据库写入；在确认门禁通过前不得调用 `import_lci`。
- manifest 置为 `awaiting_confirmation`，向用户原样展示活动数据库、目标分类、创建数量、更新/覆盖/删除实体和 `preflight_hash`。

## 3. 确认门禁

- 确认必须明确覆盖当前 `preflight_hash`、活动数据库和完整变更范围；沉默或模糊批准不视为确认。
- 用户拒绝、未确认或未明确覆盖完整范围时，保留已通过审查的 LCI，manifest 置为 `needs_review` 并停止。
- 确认只覆盖对应预检哈希。导入前必须重新预检；文件、数据库目标、分类或覆盖范围变化时哈希必须变化，旧确认立即失效。
- 只有重新预检结果与获批范围及哈希一致时，才可把 `user_confirmed=true` 交给第 06 阶段的专用执行 Agent。
