# harness 目录结构规范 (Harness Structure)

## 1. 内部目录树

```text
harness/
├── knowledge/              # 用户参考资料（扁平目录，唯一落点）
├── workflows/              # Whole-LCA / Revise 编排入口
├── specs/                  # 工作流契约：阶段门禁、schema、校验脚本
├── rules/                  # 跨场景 Agent 行为约束
└── tools/                  # MCP 与脚本实现
```

## 2. 四层职责

| 目录 | 回答的问题 | 典型内容 | 读者 |
| --- | --- | --- | --- |
| `knowledge/` | 用户给了哪些资料 | 上传的报告、表格、清单 | Agent 直接读取文件 |
| `specs/` | 本阶段/全流程必须产出什么、何时通过或停止 | `public/` 状态机与 JSON schema；`01`–`08` 阶段 spec、`validation.py` | `major-orchestrator` 按 workflow 渐进加载 |
| `rules/` | 无论哪一阶段，做某类事时的纪律 | 目录边界、LCA 方法、openLCA 操作 | workflow 条件或平台全局加载 |
| `tools/` | 工具如何实现 | `control_openlca` MCP、未注册的 `query_rag`、测试 | 子 Agent 首次调用或维护代码时 |

### spec vs rule 放置判据

```
是否绑定 Whole-LCA 某一阶段的进入/通过/停止？
  ├─ 是 → specs（阶段 spec 或 public 契约）
  └─ 否 → 是否约束 Agent 行为（非实现细节）？
        ├─ 是 → rules
        └─ 否 → tools（实现）或 knowledge（用户资料）
```

- **specs** 写阶段门禁、结构化产物、handoff 与下一阶段输入（如 `import_scope` → 06）。
- **rules** 写跨阶段工具与方法纪律；超过两行的参数/路由细节应链接 `tools/` README。
- **tools** 写 MCP 签名与实现；不写 manifest 状态或阶段顺序。

链接关系：`workflows/` → `specs/` →（按需）`rules/` → `tools/`；用户事实 → `knowledge/`。

## 3. 核心子目录说明

* **`knowledge/`**：用户参考资料的唯一目录，无 `inputs/`、`static_ref/`、`user_ref/` 子树。ISO 方法要求在 `rules/lca-knowledge/`。
* **`workflows/`**：`LCA-main.md`、`LCA-revise.md`；平台 command/skill 引用，不重述阶段正文。
* **`specs/public/`**：多阶段共享的运行时契约、`handshake-common.md`、公共 JSON schema。
* **`specs/01`–`08/`**：阶段 normative spec、`schema_mapping.md`（阶段特有握手）、阶段本地 schema/模板。
* **`rules/`**：`directory-structure`、`lca-knowledge`、`openlca-operation`、`coding-specification`。
* **`tools/`**：`control_openlca`（已注册）、`query_rag`（实现保留、当前不注册到 agent）及离线测试。
