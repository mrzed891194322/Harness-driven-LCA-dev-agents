# 仓库环境引导

你是当前会话的根 agent。只执行本文件。不要委派 `major-orchestrator` / `sub-executor`，不要启动 whole-lca / revise-lca，不要读取 `.env` 中的密钥并写进对话。

## 禁止

- 不得安装 uv（不得执行官方安装脚本、`pip install uv`、包管理器安装或其它代装动作）。
- 不得把 uv 安装命令写进你自己要跑的步骤里。安装说明只存在于 `docs/lang_CN/env_setup.md`，留给用户。
- 不得清理 workspace、不得构建 RAG、不得连接或要求 openLCA。
- 不得把 `.env` 的密钥、完整 URL 以外的敏感值打印出来。

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
uv run python src/scripts/setup_env/main.py
```

以脚本退出码和结尾 `--- json ---` 之后的 JSON 为准。

- 退出码 `1`：必要项失败（无 uv、sync 失败、Python 版本不对、MCP import 失败）。按脚本输出汇报，不要自行安装软件。
- 退出码 `0`：必要项通过。若 JSON 里 `rag_embedding.ok` 为 false，把 `rag_embedding.reminder` **原样**输出给用户，不要改写、不要展开成长篇排障。脚本会给出下面两句之一：
  - `RAG 模型未配置：请在仓库根目录 .env 填写有效的 EMBEDDING_API_KEY、EMBEDDING_API_URL、EMBEDDING_MODEL。`
  - `RAG 模型无法调用：请检查 .env 中的 Embedding 接口、密钥和模型名是否可用。`
- 脚本若因缺少 `.env` 而从 `.env.example` 复制，只报告「已从模板创建，请填写 Embedding 配置」，不要打开 `.env` 把值贴进对话。

## 汇报（中文）

逐项给出 `通过 / 已修复 / 需你动手`：

1. uv
2. 项目依赖（`uv sync` / Python）
3. `.env` 与 RAG Embedding
4. MCP 接线

最后一句：下一步启动 GUI 完成初始化检查（见 `README.md`），openLCA IPC 见 `docs/lang_CN/project_prep.md`，不要启动 whole-lca。
