# 全局目录结构规范 (Global Structure)

## 1. 根目录结构树

```text
.
├── .opencode/              # opencode 配置与 agent-skills
├── docs/                   # 全局文档与说明
├── harness/                # Agent 执行核心（规范与工具只读；knowledge/ 为用户资料）
├── src/
│   ├── GUI/                # GUI 界面前端与控制面板代码
│   ├── scripts/            # 辅助部署与环境脚本
│   └── test/               # GUI 与 scripts 运行测试入口
├── workspace/              # 运行工作区（授权可写）
├── README.md               # 项目说明
└── (环境/配置文件)           # .venv/, pyproject.toml, uv.lock 等
```

## 2. 核心目录说明

* **`.venv/`**：由 `uv` 自动管理的虚拟环境。严禁在代码中硬编码此路径。
* **`harness/`**：LCA 核心哈纳斯。`rules/`、`specs/`、`tools/` 只读加载；`knowledge/` 存放用户参考资料。
* **`workspace/`**：核心运行工作区，允许脚本运行、数据清洗与结果输出。
* **`src/scripts/` 与 `src/GUI/`**：辅助清理部署脚本及 Gradio 控制面板界面代码。
* **`docs/`**：仓库级别的静态文档。
