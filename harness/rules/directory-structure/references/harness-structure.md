# harness 目录结构规范 (Harness Structure)

## 1. 内部目录树

```text
harness/
├── knowledge/              # 用户参考资料（扁平目录，唯一落点）
├── workflows/              # Whole-LCA / Revise 编排入口
├── specs/                  # 阶段说明与薄运行约定

├── rules/                  # 跨场景 Agent 行为约束
└── tools/                  # MCP 与脚本实现
```

## 2. 四层职责

| 目录 | 回答的问题 | 典型内容 | 读者 |
| --- | --- | --- | --- |
| `knowledge/` | 用户给了哪些资料 | 上传的报告、表格、清单 | Agent 直接读取文件 |
| `specs/` | 本阶段产出什么、何时进入下一步 | `public/` 短 runtime；`01`–`04` 与 `08` 阶段说明 | `major-orchestrator` 按 workflow 渐进加载 |
| `rules/` | 无论哪一阶段，做某类事时的纪律 | 目录边界、LCA 方法、openLCA 操作 | workflow 条件或平台全局加载 |
| `tools/` | 工具如何实现 | `control_openlca` MCP 与离线测试 | 子 Agent 首次调用或维护代码时 |

### spec vs rule 放置判据

```
是否绑定 Whole-LCA 某一阶段的进入/通过/停止？
  ├─ 是 → specs（短阶段说明或 public runtime）
  └─ 否 → 是否约束 Agent 行为（非实现细节）？
        ├─ 是 → rules
        └─ 否 → tools（实现）或 knowledge（用户资料）
```

- **specs** 写阶段要产出的路径与谁调用谁。
- **rules** 写跨阶段工具与方法纪律；超过两行的参数/路由细节应链接 `tools/` README。
- **tools** 写 MCP 签名与实现；不写阶段顺序。

链接关系：`workflows/` → `specs/` →（按需）`rules/` → `tools/`；用户事实 → `knowledge/`。

## 3. 核心子目录说明

* **`knowledge/`**：用户参考资料的唯一目录，无 `inputs/`、`static_ref/`、`user_ref/` 子树。ISO 方法要求在 `rules/lca-knowledge/`。
* **`workflows/`**：`LCA-main.md`、`LCA-revise.md`；平台 command/skill 引用，不重述阶段正文。
* **`specs/public/`**：四步共用的路径、循环和终止态。
* **`specs/01`–`04/`、`08/`**：阶段说明与示例产物；无 schema_mapping、无阶段 validator。
* **`rules/`**：`directory-structure`、`lca-knowledge`、`openlca-operation`、`coding-specification`。
* **`tools/`**：`control_openlca`（已注册）及离线测试。
