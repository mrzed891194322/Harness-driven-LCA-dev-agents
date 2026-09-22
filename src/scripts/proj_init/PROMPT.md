# 仓库环境引导

你是当前会话的根 agent。只执行本文件。不要委派 `major-orchestrator` / `sub-executor`，不要启动 whole-lca / revise-lca。

## 禁止

- 不得安装 uv（不得执行官方安装脚本、`pip install uv`、包管理器安装或其它代装动作）。
- 不得把 uv 安装命令写进你自己要跑的步骤里。安装说明只存在于 `docs/lang_CN/env_setup.md`，留给用户。
- 不得清理 workspace，不得启动 whole-lca / revise-lca。
- 不要把 `.env` 全文贴进对话。
- 不得改写用户全局配置。只建议，不代改。

## Phase 0：检查 uv

在仓库根目录执行：

```bash
command -v uv || where uv
uv --version
```

若命令不存在或 `uv --version` 失败：整次引导 **不通过**。原样输出下面这一句，然后停止，不要继续 `uv sync`：

`环境检测不通过：未找到 uv。请按 docs/lang_CN/env_setup.md 手动安装 uv 后重试。`

## Phase 1：同步并检查项目环境

uv 可用之后，在仓库根目录执行：

```bash
uv sync
uv run python src/scripts/proj_init/main.py
```

以脚本退出码和结尾 `--- json ---` 之后的 JSON 为准。

- 退出码 `1`：必要项失败（无 uv、sync 失败、Python 版本不对、`control_openlca` MCP import 失败）。按脚本输出汇报，不要自行安装软件。
- 退出码 `0`：必要项通过。脚本若因缺少 `.env` 而从 `.env.example` 复制，只报告「已从模板创建」，不要打开 `.env` 把内容贴进对话。
- JSON 中的 `harness_clis` 列出 `codex` / `claude` / `opencode` / `pi` 各自的 CLI 是否在 PATH 上。缺某一个不失败；四个都没有也不把本次引导打成退出码 1。
- 提醒用户检查 `.env`：`HARNESS_AGENT`、对应模型（`CODEX_MODEL` / `CLAUDE_MODEL` / `OPENCODE_MODEL` / `PI_MODEL`）。认证走各 CLI 本机登录。字段说明只指向 `.env.example`，不要打印密钥。

## Phase 2：Worker CLI

根据 Phase 1 JSON 的 `harness_clis.clis`，逐项汇报每个 CLI「可用」或「未安装」。

- 四个都没有：标明 **GUI 路径不可用**（GUI 必须能在 PATH 上找到所选 CLI）。当前会话仍可完成引导。
- 可用的 CLI 由主编排器经 `src/scripts/agent_sdk` 会话接口调用；不要再找仓库内平台 skill 目录。

## Phase 3：openLCA IPC

在仓库根目录执行：

```bash
uv run python src/scripts/check_status/main.py --only openlca
```

- 成功：openLCA 记为通过。
- 失败：记为「需你动手」——打开 openLCA 桌面客户端、打开目标数据库、启用 IPC Server（默认 `127.0.0.1:8080`），说明见 `docs/lang_CN/env_setup.md`。**不要**因此把 Phase 1 的退出码改写成失败；IPC 失败不是 uv / 依赖 / MCP import 失败。
- 不要对 openLCA 做写入、清理或导入。

## 汇报（中文）

逐项给出 `通过 / 已修复 / 需你动手`：

1. uv
2. 项目依赖（`uv sync` / Python）
3. `.env`（已存在，或已从模板创建；提醒核对模型，不要贴出内容）
4. MCP 接线（`control_openlca`）
5. Worker CLI：分别列出 codex / claude / opencode / pi
6. openLCA IPC

最后一句：下一步可启动 GUI（见 `README.md`），或在完成 `clean_dir` 并放入资料后执行 `uv run python src/scripts/workflows/orchestrator/main.py --task whole-lca`。不要在本次引导里启动 whole-lca。
