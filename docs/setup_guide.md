# 🛠️ 环境准备与配置详解

本文档详细介绍了运行 **Multi-Agent LCA Orchestrator (202606-harness-agent-lca)** 项目所需的环境搭建及配置步骤。

---

## 1. 准备核心工具

运行本项目需要安装 `uv` 和 `opencode` 客户端。

### 1.1 安装 uv (高性能 Python 包管理工具)
`uv` 能够极速创建虚拟环境和同步依赖：
* **macOS / Linux**:
  ```bash
  curl -LsSf https://astral.sh/uv/install.sh | sh
  ```
* **Windows (PowerShell)**:
  ```powershell
  powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
  ```
* **验证安装**:
  ```bash
  uv --version
  ```
  更多安装方式请参考 [uv 官方文档](https://github.com/astral-sh/uv)。

### 1.2 安装 opencode (AI 编码智能体客户端)
根据您的开发环境进行全局安装。您可以访问 [OpenCode 官网](https://opencode.ai/) 下载对应的客户端或通过其官方安装指南进行安装。

推荐在命令行中直接进行全局安装，如果您已安装 [Node.js (npm)](https://nodejs.org/)，可按下列方式执行安装：
```bash
npm install -g opencode-ai
```

* **验证安装**:  
  ```bash
  opencode --version
  ```


---

## 2. 配置 OpenCode API 与 Agent

在使用智能体服务前，您需要配置好 OpenCode 对应的 API 密钥。

### 2.1 登录并配置 API Key & 模型
在 OpenCode 中配置服务商与具体模型（具体配置案例可参考 [第 5 节](#5-可选服务商配置案例)）：
* **命令行方式 (推荐)**：
  在终端中执行以下命令进行认证和连接：
  ```bash
  opencode auth login
  ```
* **交互界面方式**：
  在 OpenCode 交互界面中，输入 `/connect` 指令按照提示添加您的 API Providers（例如 OpenAI、Anthropic、Gemini 等）。

### 2.2 项目级 Agent 配置
* **全局/项目行为规则**：
  本项目智能体的行为与规范遵循根目录下的 [AGENT.md](../AGENT.md)。项目级opencode配置文件位于 [.opencode/opencode.json](../.opencode/opencode.json)。 
* **智能体模型配置**：
  项目级 Agent 的模型配置推荐直接在 [.opencode/agents/](../.opencode/agents/) 目录下的各智能体定义文件（例如 [.opencode/agents/major-orchestrator.md](../.opencode/agents/major-orchestrator.md)）中进行修改。
  更详细的配置介绍请参阅 [OpenCode 官方配置文档](https://opencode.ai/)。

---

## 3. 配置项目虚拟环境

项目基于 [pyproject.toml](../pyproject.toml) 管理 Python 依赖包。在确保安装了 `uv` 之后，在项目根目录下运行以下命令：

```bash
uv sync
```

该命令会自动执行以下操作：
1. 在项目根目录下自动创建 `.venv` 虚拟环境。
2. 根据 [pyproject.toml](../pyproject.toml) 的配置，自动下载并同步项目所需的所有 Python 依赖。


---

## 4. 本地环境变量配置

在运行项目前，需要配置本地环境变量（主要用于配置 **Embedding 检索服务商**）。程序在运行时只会读取项目根目录下的 `.env` 文件，因此我们需要通过复制模板文件 [.env.example](../.env.example) 并将其重命名为 `.env` 来存放您自己的配置：

1. **复制并生成 `.env` 文件**（这一步也可以手动执行）：
   ```bash
   cp .env.example .env
   ```
2. **编辑 `.env` 文件**，填入您的 Embedding API 密钥、接口地址以及模型配置：
   ```env
   EMBEDDING_API_KEY="your-api-key"
   EMBEDDING_API_URL="your-api-url"
   EMBEDDING_MODEL="your-embedding-model"
   ```

---

## 5. 可选服务商配置案例

为了帮助您快速上手，以下提供了运行此项目所需服务商的典型配置案例（包括 LLM 智能体和 Embedding 模型）：

### 5.1 OpenCode 智能体服务商配置案例
以下以 **DeepSeek** 为例介绍如何设置 OpenCode 智能体服务商：
* **API 平台官网**：[DeepSeek 开放平台](https://platform.deepseek.com/)
* **如何设置 OpenCode 关联 DeepSeek**：详细步骤请参考 [DeepSeek 官方的 OpenCode 集成文档](https://api-docs.deepseek.com/quick_start/agent_integrations/opencode)，简要配置流程如下：
  1. 在 [DeepSeek API Key 管理页面](https://platform.deepseek.com/api_keys) 注册并生成您的 API Key。
  2. 运行 `opencode` 启动客户端。
  3. 在输入框中输入 `/connect` 指令，然后搜索并选择 `deepseek` 服务商。
  4. 粘贴您在第一步中获取的 DeepSeek API Key。
  5. 接着根据提示选择需要的模型，如 `DeepSeek-V4-Pro`（您也可以在项目级 `opencode.json` 中配置）。

### 5.2 Embedding 检索服务商配置案例
以下以 **硅基流动 (SiliconFlow)** 为例介绍如何配置 Embedding 检索服务商：
* **平台官网**：[硅基流动官网](https://siliconflow.cn/)
* **配置步骤**：
  1. 在硅基流动平台注册并进行充值，在其 API 密钥管理页面创建并获取您的 API Key。
  2. 访问硅基流动的**模型广场**，选择符合项目要求的合适 Embedding 模型（例如 `Qwen/Qwen3-VL-Embedding-8B`）。
* **主要参数**：
  * **API URL**：`https://api.siliconflow.cn/v1`
  * **所用模型 (Model)**：`Qwen/Qwen3-VL-Embedding-8B`
* **`.env` 配置文件设置**：
  ```env
  EMBEDDING_API_KEY="您的硅基流动 API Key"
  EMBEDDING_API_URL="https://api.siliconflow.cn/v1"
  EMBEDDING_MODEL="Qwen/Qwen3-VL-Embedding-8B"
  ```
