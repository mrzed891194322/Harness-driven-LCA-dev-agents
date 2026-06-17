# 项目目录与文件规范（总览）

> **上下文提示**：本文件约 6KB。如需了解 `src/` 的内部规范，请另读同目录下的 `src-structure.md`；不要提前读取本文件全部内容。
>
> 本文件由 `project-convention` skill 维护，聚焦**项目整体结构**与**通用约定**。

---

## 1. 根目录结构

```
.
├── .venv/                  # Python 虚拟环境（由 uv 管理，勿提交）
├── .opencode/              # opencode 配置与 skills
│   ├── agents/             # agent 定义文件
│   └── skills/             # 本地 skills
├── src/                    # 模型训练代码入口
│   ├── train/              # 训练代码（主训练脚本、数据处理）
│   ├── eval/               # 评估工具（指标、验收规则）
│   ├── model/              # 模型实现（按模型族分目录）
│   ├── harness/            # 领域规则与约束（仅 Python 脚本）
│   ├── config/             # 配置目录（存放模型训练的各项参数）
│   ├── history/            # 训练历史归档（按 run1、run2... 分轮次）
│   ├── output/             # 最终确定的交付物「方案选单」
│   ├── data/               # 预处理代码与预处理后的数据
│   └── temp/               # 临时文件及 AI agent 临时脚本
├── data/                   # 原始数据目录（仅限原始数据）
├── docs/                   # 全局文档
├── plan/                   # 项目规划与设计文档
├── repo/                   # 代码参考或相关库
├── main.py                 # 主运行脚本
├── pyproject.toml          # uv 项目配置与依赖声明
├── uv.lock                 # uv 依赖锁定
├── .gitignore              # Git 忽略规则
├── .python-version         # Python 版本声明
└── README.md               # 项目总说明
```


---

## 2. 各目录详细约定

### 2.1 `.venv/` — Python 虚拟环境

- **用途**：项目虚拟环境，由 `uv` 管理。
- **读取方式**：使用 bash 工具调用 `.venv\Scripts\python.exe`（Windows）或 `.venv/bin/python`（Linux/macOS）运行 Python。
- **禁止**：不要在代码中硬编码虚拟环境路径；agent 应通过 `pyproject.toml` 或用户确认获取环境信息。

### 2.2 `.opencode/` — opencode 配置

- **用途**：存放 opencode 的 agent 定义、skills 等配置。
- **agents/**：agent prompt 文件。
- **skills/**：本地定义的 skills，每个 skill 一个子目录。
- **修改方式**：使用 `Read`/`Write` 工具直接编辑。

### 2.3 `src/` — 模型训练代码入口

- **用途**：模型训练项目核心代码。
- **详细规范**：见同目录 `src-structure.md`。编码 agent 在实现代码时，应优先阅读该文件。
- **快速参考**：
  - 训练入口：`src/train/train.py`
  - 评估工具：`src/eval/regression.py`
  - 模型定义：`src/model/{family}/`
  - 领域规则：`src/harness/`
  - 参数配置：`src/config/`
  - 训练历史：`src/history/runN/`（如 `history/run1/`、`history/run2/`）
  - 最终交付：`src/output/`
  - 数据处理：`src/data/`
  - 临时文件：`src/temp/`

### 2.4 `data/` — 原始数据目录

- **用途**：仅用于存放项目所需的原始数据。不要在这里存放预处理代码或预处理后的中间数据。
- **注意**：预处理后的数据和数据预处理脚本应当放在 `src/data/` 目录下。

### 2.5 `docs/` — 全局文档

- **用途**：仓库级别的文档，如论文笔记、技术调研、评审记录等。

### 2.6 `plan/` — 项目规划文档

- **用途**：存放项目的计划和设计文档。

---

## 3. 文件命名规范

| 类型 | 规范 | 示例 |
|------|------|------|
| Python 模块 | 全小写，下划线分隔 | `boosted_trees.py`, `feature_regressors.py` |
| 类名 | PascalCase | `FeatureColumnRegressor`, `AcceptanceRule` |
| 函数/变量 | 小写下划线 | `build_daily_dataset()`, `min_mae_improvement_pct` |
| 实验脚本 | 动词开头，小写下划线 | `train.py`, `extract_indicators.py` |
| 模型目录 | 小写下划线，`_models` 后缀 | `baseline_models/`, `gbdt_models/` |
| 模型文件 | `best_model_<target>.joblib` | `best_model_system_water.joblib` |
| 训练历史目录 | 轮次格式 `runN`，从 `run1` 开始递增 | `run1/`, `run2/` |

---

## 4. 工具使用推荐

### 4.1 文件操作工具选择

| 场景 | 推荐工具 | 说明 |
|------|----------|------|
| 读取文件内容 | `Read` | 首选，支持代码文件和 Markdown |
| 搜索文件路径 | `Glob` | 按模式匹配文件名，如 `**/*.py` |
| 搜索文件内容 | `Grep` | 按正则表达式搜索代码内容 |
| 写入新文件 | `Write` | 创建新文件或完全覆盖 |
| 修改现有文件 | `Edit` | 对现有文件做增量修改 |
| 执行命令 | `bash` | 运行 git、uv、python 等命令 |
| 批量任务 | `Task` | 调用子 agent 执行复杂任务 |

### 4.2 读取规范

- **代码文件**：使用 `Read` 读取，一次读取完整文件或按需分段（`offset` + `limit`）。
- **数据文件**：
  - CSV：先用 `Read` 查看前几行，了解结构；再用 Python 脚本读取。
  - Excel：需用 `pandas.read_excel`（`openpyxl` 已安装）。
- **配置文件**：`pyproject.toml`、`.gitignore` 等可直接用 `Read` 读取。

### 4.3 写入规范

- **新文件**：使用 `Write` 创建。
- **修改文件**：优先使用 `Edit` 做增量修改；若需大幅重构，可用 `Write` 覆盖。
- **禁止**：不要用 `bash` 中的 `echo` 或 `cat` 做文件写入；始终使用专门的 `Write` 或 `Edit` 工具。

---

## 5. 环境与依赖约定

- **Python 版本**：声明在 `.python-version` 和 `pyproject.toml` 中。
- **依赖管理**：优先使用 `uv`。
  - 安装：`uv sync`
  - 运行：`uv run python <script.py>` 或 `.venv\Scripts\python.exe <script.py>`
- **依赖声明**：所有依赖应写入 `pyproject.toml` 的 `[project.dependencies]` 或 `[dependency-groups]` 中。

---

## 6. 代码规范

- **语言**：所有代码注释使用中文。
- **文档字符串**：函数和类应包含中文 docstring，说明功能、参数和返回值。
- **类型提示**：推荐使用 Python 类型提示（`typing` 模块）。
- **导入顺序**：标准库 → 第三方库 → 本地模块，每组之间空一行。
- **可选依赖**：对 LightGBM、XGBoost 等可选库，使用 `try/except` 导入，模型工厂函数内做可用性判断。

---

## 7. Git 相关

- **根级 `.gitignore`**：排除 `.venv/`、`__pycache__/`、`*.pkl`、IDE 配置、日志文件等。
- **项目级 `.gitignore`**：不应默认排除 `data/` 目录。若原始数据文件过大，按用户确认后排除具体大文件；预处理中间产物应放在 `src/data/` 并按需排除。`history/` 是否提交由项目交付要求决定；若包含大型模型文件，应在用户确认后决定是否排除。
- **提交原则**：仅在用户明确要求时执行 `git commit`，不主动提交。
- **安全**：不提交包含密钥、密码的文件。

---

## 8. 修改本规范

若需调整目录结构、命名规范或工具使用方式，直接编辑本文件（`skills/project-convention/assets/global-structure.md`）或 `src-structure.md` 即可。所有按需加载本 skill 的 agent 都会读取最新版本。
