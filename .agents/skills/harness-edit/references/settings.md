# 偏好

`harness/settings.yaml` 只提供生成式提示词的变量。当前是 `language.output` 与 `language.documents`，默认都是中文。模板在 `harness/rules/generated/language.md.tmpl`，变量缺失会在建会话时直接报错。

面板保存写 `harness/.user/settings.yaml`。读取时用户版优先，删除用户版即恢复仓库默认。不要把 `.user` 提交进 git。接口是 `GET/PUT/DELETE /api/prompts/generated`；预览用 `GET /api/prompts/generated/preview?stage=&role=`，且只支持 `harness/LCA-main.yaml` 的阶段。

改模板措辞或变量名时，默认文件和用户版一起核对，并跑 `npm run doctor`。
