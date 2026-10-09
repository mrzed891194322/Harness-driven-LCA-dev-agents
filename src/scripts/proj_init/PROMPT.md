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
npm install
npm run build -w @harness/pi-runtime
uv run python src/scripts/proj_init/main.py
```

以脚本退出码和结尾 `--- json ---` 之后的 JSON 为准。

- 退出码 `1`：必要项失败（无 uv、sync 失败、Python 版本不对、`control_openlca` MCP import 失败）。按脚本输出汇报，不要自行安装软件。
- 退出码 `0`：必要项通过。脚本若因缺少 `.env` 而从 `.env.example` 复制，只报告「已从模板创建」，不要打开 `.env` 把内容贴进对话。
- JSON 中的 `harness_clis` 表示 **Pi SDK runtime**（Node + `src/pi_agents/pi-runtime`）是否就绪。不可用时不要把本次引导打成退出码 1，但要提醒用户安装 Node 并构建 pi-runtime。
- 提醒用户检查 `.env` 的 `PI_MODEL`（档案 id，见 `src/shared/config/model_profiles.json`），并在 Web「设置」或 `.local/credentials/pi-auth.json` 配置 Provider API Key（BYOK）。字段说明只指向 `.env.example`，不要打印密钥。

## Phase 2：Pi SDK runtime

根据 Phase 1 JSON 的 `harness_clis.clis`，汇报 Pi SDK runtime「可用」或「不可用」。

- 不可用：标明 **Web / 编排 worker 路径不可用**（需要 Node.js 与已构建的 `@harness/pi-runtime`）。当前会话仍可完成引导。
- 可用时由主编排器经 `src/shared/core/agents` → `pi_agents` 调用；不要再找 PATH 上的 `codex` / `claude` / `opencode` / `pi` 可执行文件。

## Phase 3：openLCA IPC

在仓库根目录执行：

```bash
uv run python src/scripts/check_status.py --only openlca
```

（此检查仅供引导自动化；用户日常连通性以 Web 控制面板「设置 / 项目状态」为准。）

- 成功：openLCA 记为通过。
- 失败：记为「需你动手」——打开 openLCA 桌面客户端、打开目标数据库、启用 IPC Server（默认 `127.0.0.1:8080`），说明见 `docs/lang_CN/env_setup.md`。**不要**因此把 Phase 1 的退出码改写成失败；IPC 失败不是 uv / 依赖 / MCP import 失败。
- 不要对 openLCA 做写入、清理或导入。

## 汇报（中文）

逐项给出 `通过 / 已修复 / 需你动手`：

1. uv
2. 项目依赖（`uv sync` / Python / npm pi-runtime）
3. `.env`（已存在，或已从模板创建；提醒核对 `PI_MODEL` 与 BYOK 凭证，不要贴出内容）
4. MCP 接线（`control_openlca`）
5. Pi SDK runtime
6. openLCA IPC

最后一句：下一步启动 Web 控制面板（见 `README.md` 的 `npm run dev`），在面板内完成设置、计划与执行。不要在本次引导里启动 whole-lca。
