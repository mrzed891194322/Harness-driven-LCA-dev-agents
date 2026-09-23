# `src/` 源码说明

本目录是仓库的**正式 Python 源码与测试**根。`harness/` 管契约与 YAML；`workspace/` 是运行产物。改行为优先改这里的包，不要改 `workspace/` 里某次运行的结果（除非用户点名那次）。

验证用单元测试与 mock，不要用跑一遍 whole-lca 代替回归。

## 依赖边界

```text
scripts / gui
        ↓
     services
        ↓
  core + domains
        ↓
  schema + utils
```

- `core` **不得**依赖 `gui` 或 `scripts`
- `schema` 只放跨模块纯数据结构，避免 `schema → core → schema` 循环
- 业务代码统一 `from core...` / `from gui...` 等正式包导入；不要依赖 cwd / `sys.path` 的模糊导入（入口脚本可自补 `src` 到 path）

## 目录结构

| 路径 | 职责 | 不要当成 |
| --- | --- | --- |
| [`core/`](core/) | 通用编排与 worker：`orchestrator/`、`runtime/`、`agents/` | GUI 或 LCA 业务规则堆放处 |
| [`domains/lca/`](domains/lca/) | LCA checker、产物/验收、openLCA MCP 适配、前景清理 | 通用状态机 |
| [`services/`](services/) | 薄应用层：`workflow` / `workspace` / `diagnostics` / `settings` | 再造一套编排器 |
| [`schema/`](schema/) | 共享契约（如 SessionRef / SessionConfig / TurnResult） | 所有 dataclass 的垃圾桶 |
| [`utils/`](utils/) | 通用能力：`.env`、文件系统清理 | 带 LCA/openLCA 业务规则的代码 |
| [`gui/`](gui/) | Gradio 面板（细节见 [`gui/README.md`](gui/README.md)） | 主编排实现 |
| [`scripts/`](scripts/) | 薄 CLI / 运维入口（argparse、启停、引导） | 正式库逻辑正文 |
| [`tests/`](tests/) | 回归测试（布局见 [`tests/README.md`](tests/README.md)） | 金标 workspace |

`core` 再拆：

| 子目录 | 内容 |
| --- | --- |
| `core/orchestrator/` | 加载 YAML / TaskBundle（`load`）、阶段循环（`loop`）、checkpoint / manifest / fingerprint（`persist`） |
| `core/runtime/` | 能力注册、钩子、知识/工具上下文等通用运行时 |
| `core/agents/` | worker provider、session 执行、inspect/MCP；模型默认在 `config.py` |

## 常用入口

在仓库根目录：

```bash
uv sync

# GUI
uv run python src/gui/main.py

# 工作流
uv run python src/scripts/workflow.py --task whole-lca
uv run python src/scripts/workflow.py --task revise-lca

# 清理（注意 revise 与 whole 预设不同）
uv run python src/scripts/clean.py -y --preset whole-lca
uv run python src/scripts/clean.py -y --preset revise-lca

# 就绪检查
uv run python src/scripts/check_status.py

# 环境引导
uv run python src/scripts/proj_init/main.py
```

MCP（由 `harness/LCA-main.yaml` 注册）入口：

- `src/domains/lca/openlca_mcp.py`
- `src/domains/lca/artifacts/main.py`

## 怎么改（按意图找入口）

| 你要改的 | 先改 | 一并看 |
| --- | --- | --- |
| 阶段顺序、任务绑定、工具/规则注册 | `harness/LCA-*.yaml` | `harness/specs/`；**不要**把状态机抄进 GUI |
| 验收 / 产物路径 / 角色任务正文 | `harness/specs/` | 对应 YAML |
| 编排循环、handoff、resume、指纹 | `core/orchestrator/` | `persist/config_fingerprint.py` 的 `IMPLEMENTATION_ROOTS` |
| worker CLI / session / 模型默认 | `core/agents/`、`core/agents/config.py` | `schema/session.py`、`utils/env.py` |
| LCA 检查、产物失效、openLCA 适配 | `domains/lca/` | `harness/tools/control_openlca/` |
| 启动/恢复工作流的组合逻辑 | `services/workflow.py` | `scripts/workflow.py`（保持很薄） |
| whole/revise 清理策略与顺序 | `services/workspace.py` | `utils/filesystem.py`、`domains/lca/cleanup.py`、`scripts/clean.py` |
| Agent / 端口等应用级 .env 键 | `services/settings.py` | GUI `functions/settings/settings.py`、`scripts/check_status.py` |
| 按钮、Tab、门禁、终端流式日志 | `gui/`（组件 → 事件 → functions） | [`gui/README.md`](gui/README.md)；subprocess 模型保持即可 |
| 环境探测 / GUI 启停 / Gitee 同步 | `scripts/proj_init`、`gui_control`、`gitee_upload` | 只放运维逻辑，业务回调 services |

改路径或实现后：全仓搜旧字符串（YAML、README、subprocess argv、fingerprint 根），并跑对应测试。

## 导入约定

```python
from core.orchestrator.load.loader import load_workflow
from core.agents.session import default_client
from domains.lca.bootstrap import register_lca
from services.workspace import run_clean
from schema.session import SessionConfig
from utils.env import upsert_env_keys
from services.settings import load_port_settings
```

测试目录用 `t_core` / `t_domains` / `t_services` 前缀，避免与包名 `core` / `domains` / `services` 在 `pythonpath=["src"]` 下冲突。

## 验证

```bash
uv run pytest
uv run pytest src/tests/gui -v
uv run pytest src/tests/t_core -v
uv run ruff check .
uv run pyright
```

更细的仓库级约定见 [`.cursor/rules/cursor-dev.mdc`](../.cursor/rules/cursor-dev.mdc)；产品使用与环境见根目录 [`README.md`](../README.md)。
