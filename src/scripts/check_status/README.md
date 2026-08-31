# 就绪状态检查脚本

`src/scripts/check_status` 负责 harness CLI 与 openLCA IPC 连接检查。GUI
直接 import `agents_check` 与 `openlca_check`；本目录的 `main.py` 仅供命令行手动检查。

## 模块

| 模块 | 职责 |
| :--- | :--- |
| `agents_check/` | 检查 codex / claude / opencode / dsh 是否在 PATH 且可调用 |
| `openlca_check/` | 检查 openLCA IPC Server 连接（与 MCP 共用有界重试） |
| `main.py` | CLI 编排：可选 pre-clean、agents、openlca 健康检查 |

Agent 路径直接读取 `harness/knowledge/` 用户资料。bootstrap-env（`src/scripts/proj_init/PROMPT.md`）会调用 `--only openlca` 做 IPC 探测。openLCA 前景清理由 GUI 或用户在启动 agent 前通过 `src/scripts/clean_dir/main.py -t openlca` 或 `--preset` 执行。

## 环境变量

~~~text
HARNESS_AGENT="opencode"  # 可选：codex / claude / opencode / dsh
OPENLCA_IPC_PORT=8080     # 可选；GUI 与 CLI 共用
~~~

## 使用方式

在项目根目录执行：

~~~bash
# 完整检查（清理 + Agent 检查 + openLCA）
uv run python src/scripts/check_status/main.py

# 仅执行 Agent CLI 检查
uv run python src/scripts/check_status/main.py --only agents

# 仅检查 openLCA
uv run python src/scripts/check_status/main.py --only openlca --port 8080

# 仅清理工作目录
uv run python src/scripts/check_status/main.py --only clean
~~~

openLCA 检查默认连接 `127.0.0.1:8080`，首次失败后新建客户端重连 3 次。4 次均失败时
命令返回非零，GUI 保持执行门禁锁定。

## 离线测试

~~~bash
uv run python -m unittest discover -s src/test -v -k check_status
~~~
