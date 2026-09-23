# `src/` 源码说明

本目录是仓库的**正式 Python 源码与测试**根。`harness/` 管契约与 YAML；`workspace/` 是运行产物。改行为优先改这里的包，不要改 `workspace/` 里某次运行的结果（除非用户点名那次）。

验证用单元测试与 mock，不要用跑一遍 whole-lca 代替回归。

## 依赖边界

```text
scripts / gui
      ↓
   core  ←── harness/tools（YAML provider / MCP）
      ↓
   utils
```

- `core` **不得**依赖 `gui`、`scripts` 或 `harness.tools`（LCA 能力经 YAML `provider:` 懒加载）
- 会话契约在 `core/contracts/`；不要再引入顶层 `schema/` / `services/` / `domains/`
- 业务代码统一 `from core...` / `from gui...`；入口脚本可自补 `src` 到 path

## 目录结构

| 路径 | 职责 | 不要当成 |
| --- | --- | --- |
| [`core/`](core/) | 业务无关编排引擎：`workflow/`、`runtime/`、`agents/`、`contracts/` | GUI 或 LCA 业务规则堆放处 |
| [`../harness/tools/`](../harness/tools/) | LCA checker / 产物 / openLCA MCP（standalone + workflow 适配） | 通用状态机 |
| [`app_settings.py`](app_settings.py) / [`diagnostics.py`](diagnostics.py) / [`workspace_clean.py`](workspace_clean.py) | 应用级 .env、就绪检查、清理预设 | 编排状态机 |
| [`utils/`](utils/) | 通用能力：`.env`、文件系统清理 | 带 LCA/openLCA 业务规则的代码 |
| [`gui/`](gui/) | Gradio 面板（细节见 [`gui/README.md`](gui/README.md)） | 主编排实现 |
| [`scripts/`](scripts/) | 薄 CLI（直接把 `--workflow` 交给 core） | 正式库逻辑正文 |
| [`tests/`](tests/) | 回归测试（布局见 [`tests/README.md`](tests/README.md)） | 金标 workspace |

`core` 再拆：

| 子目录 | 内容 |
| --- | --- |
| `core/workflow/` | YAML 加载（`config/`）、阶段循环（`execution/`）、checkpoint / fingerprint（`persistence/`）；入口 `main.py` |
| `core/runtime/` | provider 组合、钩子、知识/工具上下文等通用运行时 |
| `core/agents/` | worker provider、session 执行、inspect/MCP；模型默认在 `config.py` |
| `core/contracts/` | SessionRef / SessionConfig / TurnResult 等跨模块契约 |

## 常用入口

在仓库根目录：

```bash
uv sync

# GUI
uv run python src/gui/main.py

# 工作流（直接注入 YAML 路径，无 index / --task 别名）
uv run python src/scripts/workflow.py --workflow harness/LCA-main.yaml
uv run python src/scripts/workflow.py --workflow harness/LCA-revise.yaml
# 或等价：uv run python -m core.workflow.main --workflow harness/LCA-main.yaml

# 清理（注意 revise 与 whole 预设不同）
uv run python src/scripts/clean.py -y --preset whole-lca
uv run python src/scripts/clean.py -y --preset revise-lca

# 就绪检查
uv run python src/scripts/check_status.py

# 环境引导
uv run python src/scripts/proj_init/main.py
```

MCP（由 `harness/LCA-*.yaml` 的 `registry.tools` 注册）入口：

- `harness/tools/control_openlca/workflow_mcp.py`
- `harness/tools/lca_artifacts/workflow_mcp.py`

## 怎么改（按意图找入口）

| 你要改的 | 先改 | 一并看 |
| --- | --- | --- |
| 阶段顺序、任务绑定、工具/规则/checker 注册 | `harness/LCA-*.yaml` | `harness/specs/`；**不要**把状态机抄进 GUI |
| 验收 / 产物路径 / 角色任务正文 | `harness/specs/` | 对应 YAML |
| 编排循环、handoff、resume、指纹 | `core/workflow/` | `persistence/config_fingerprint.py` 的 `IMPLEMENTATION_ROOTS` |
| worker CLI / session / 模型默认 | `core/agents/`、`core/agents/config.py` | `core/contracts/session.py`、`utils/env.py` |
| LCA 检查、产物失效、openLCA 适配 | `harness/tools/lca_artifacts/`、`harness/tools/control_openlca/` | `harness/LCA-*.yaml` registry |
| 启动工作流 | `scripts/workflow.py` → `core.workflow.main`（仅 `--workflow`） | GUI `executor_utils.WORKFLOW_YAML_BY_TASK` 只做按钮→路径映射 |
| whole/revise 清理策略与顺序 | `workspace_clean.py` | `utils/filesystem.py`、`harness/tools/control_openlca/cleanup_service.py`、`scripts/clean.py` |
| Agent / 端口等应用级 .env 键 | `app_settings.py` | GUI `functions/settings/settings.py`、`scripts/check_status.py` |
| 按钮、Tab、门禁、终端流式日志 | `gui/`（组件 → 事件 → functions） | [`gui/README.md`](gui/README.md) |
| 环境探测 / GUI 启停 / Gitee 同步 | `scripts/proj_init`、`gui_control`、`gitee_upload` | 运维逻辑，不进 core |

改路径或实现后：全仓搜旧字符串（YAML、README、subprocess argv、fingerprint 根），并跑对应测试。

## 导入约定

```python
from core.workflow.config.loader import load_workflow
from core.agents.session import default_client
from core.contracts.session import SessionConfig
from harness.tools.lca_artifacts.bootstrap import lca_capabilities
from workspace_clean import run_clean
from app_settings import load_port_settings
from utils.env import upsert_env_keys
```

测试目录用 `t_core` / `t_domains` / `t_services` 前缀，避免与包名 `core` 在 `pythonpath=["src"]` 下冲突。

## 验证

```bash
uv run pytest
uv run pytest src/tests/gui -v
uv run pytest src/tests/t_core -v
uv run ruff check .
uv run pyright
```

更细的仓库级约定见 [`.cursor/rules/cursor-dev.mdc`](../.cursor/rules/cursor-dev.mdc)；产品使用与环境见根目录 [`README.md`](../README.md)。
