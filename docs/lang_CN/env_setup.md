# 🛠️ 环境准备与配置详解

本文档详细介绍运行 **Multi-Agent LCA Orchestrator (202606-harness-agent-lca)** 所需环境与配置。

---

## 1. 运行依赖

项目至少需要 `uv` 与 `opencode`：

### 1.1 安装 uv
* **macOS / Linux**:
  ```bash
  curl -LsSf https://astral.sh/uv/install.sh | sh
  ```
* **Windows (PowerShell)**:
  ```powershell
  powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
  ```
* **验证**:
  ```bash
  uv --version
  ```

### 1.2 安装 opencode
推荐使用 npm 全局安装：
```bash
npm install -g opencode-ai
```
或按官方文档进行安装。

* **验证**：
  ```bash
  opencode --version
  ```

---

## 2. OpenCode 与智能体配置

### 2.1 认证与登录
- 运行 `opencode auth login`
- 或在终端/GUI 输入 `/connect` 配置服务商。

### 2.2 模型与项目配置
- 核心配置文件是 [.opencode/opencode.json](.opencode/opencode.json)。
- 项目级规则位于 [.codex/AGENTS.md](.codex/AGENTS.md)。

建议策略：
- 核心流程智能体使用质量更高、稳定性更好的模型；工具执行类使用更轻量模型。

---

## 3. Python 与环境变量

在项目根目录执行：
```bash
uv sync
```

`src/scripts/initialization/main.py` 会检查运行环境并准备脚本运行所需的运行环境。

### 3.1 环境变量
- 复制 `.env.example` 到 `.env`：
  ```bash
  cp .env.example .env
  ```
- 按需填写：
  ```env
  EMBEDDING_API_KEY="your-api-key"
  EMBEDDING_API_URL="https://.../v1"
  EMBEDDING_MODEL="your-embedding-model"
  ```

---

## 4. 示例供应商（可选）

可用任意你已接入的 LLM 与 Embedding 服务。

```md
示例：
- EMBEDDING_API_URL="https://api.siliconflow.cn/v1"
- EMBEDDING_MODEL="Qwen/Qwen3-Embedding-8B"
```

> 说明：项目中 embedding 配置用于 RAG 检索，变更模型后需重新构建知识库。
