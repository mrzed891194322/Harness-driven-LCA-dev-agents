# `src/` 源码说明

本目录是仓库的**正式 Python 源码与测试**根。`harness/` 管契约与 YAML；`workspace/` 是运行产物。

验证用单元测试与 mock，不要用跑一遍 whole-lca 代替回归。

## 依赖边界

```text
scripts / gui
      ↓
   core  ←── harness（仅 YAML 装配 + stdio MCP + rules MD；core 永不 import harness Python）
      ↓
   utils
```

- `core` **不得**静态或动态 import `harness.tools`
- 确定性业务检查 / lifecycle action 只能经 stage `spec.yaml` 声明的 stdio MCP 调用
- 会话契约在 `core/contracts/`

## 目录结构

| 路径 | 职责 |
| --- | --- |
| [`core/workflow/`](core/workflow/) | YAML 装配、stage spec 解析、执行循环、checkpoint |
| [`core/runtime/`](core/runtime/) | 知识注入、宿主 MCP（`mcp_host`）、上下文 |
| [`core/agents/`](core/agents/) | worker 会话 |
| [`app_settings.py`](app_settings.py) / [`diagnostics.py`](diagnostics.py) / [`workspace_clean.py`](workspace_clean.py) | 应用级设置与清理 |
| [`gui/`](gui/) / [`scripts/`](scripts/) / [`tests/`](tests/) | GUI、薄 CLI、回归 |

## 常用入口

```bash
uv run python src/scripts/workflow.py --workflow harness/LCA-main.yaml
uv run python src/scripts/workflow.py --workflow harness/LCA-revise.yaml
```

两张 YAML 彼此独立（无 reuse）。详情见 [`docs/lang_CN/harness.md`](../docs/lang_CN/harness.md)。
