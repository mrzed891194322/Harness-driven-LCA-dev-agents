# Whole-LCA 公共契约索引

本目录只保存 `whole-lca` 多个阶段共同使用的运行、状态和证据契约。阶段独占的 schema、模板与确定性校验脚本随对应的 `harness/specs/01-*` 至 `harness/specs/07-*` 阶段包保存；公共目录不代表独立业务阶段。

## References

1. **运行、状态与证据**
   - `references/workflow-runtime-spec.md`
   - `references/handshake-common.md`（handoff / stage / manifest / review 公共握手机制）
2. **JSON Schema**
   - `references/schemas/common.schema.json`（共享 `artifact` 定义）
   - `references/schemas/workflow-manifest.schema.json`
   - `references/schemas/stage.schema.json`
   - `references/schemas/review.schema.json`
   - `references/schemas/handoff.schema.json`

## 公共测试

- `references/scripts/tests/`：公共 schema、全部阶段契约、阶段路由和平台配置的回归测试。
- 测试命令：`uv run python -m unittest discover -s harness/specs/public/references/scripts/tests -v`。

阶段专属资源由各阶段 README 路由；每个阶段的 `schema_mapping.md` 只记录阶段特有的握手与工具依赖，公共部分见 `references/handshake-common.md`。
