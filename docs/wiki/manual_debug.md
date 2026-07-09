# 🛠️ 手动调试与文件同步机制指南

本指南详细介绍在不使用图形界面（GUI）进行开发调试时，如何通过手动操作项目根目录下的 `uploads/` 文件夹和运行命令行指令，与 **Multi-Agent** 智能体工作流进行交互并开展调试。

---


---

## 🚀 手动调试步骤

当您需要手动调试或使用命令行驱动工作流时，可遵循以下步骤：

### 1. 准备并上传文件（文件传输）

将您需要的输入文件放置在对应的 `uploads/` 子目录下：
* **原始参考文档**：将环评报告等 PDF/Word 文档放入 `uploads/user_file/`。
* **原始数据**：将所需数据（如有）输入放置在 `uploads/user_data/`。

---

### 2. 使用初始化脚本进行前置准备

开始任务前，请依次运行初始化脚本：
```bash
# 初始化（默认会先清理目录、同步已上传文件，再建立RAG向量数据库并检测OpenLCA连接）
uv run python scripts/initialization/main.py
```

---

### 3. 调用 OpenCode 命令制定 LCA 计划

准备好计划文件（需要命名为：`current_plan.md`，上传到`uploads/plan/`目录下）使用 OpenCode 客户端或命令行工具调用预设指令，启动 `plan-maker` 智能体：

* **命令**：
  ```bash
  opencode run --command make-plan 
  ```
* **执行逻辑**：
  1. 命令开始前，会自动执行文件双向同步，把 `uploads/` 下的文件（如 `uploads/plan/current_plan.md`）同步到工作目录。
  2. `plan-maker` 智能体被激活，读取您的需求文件以及 RAG 向量数据库中的相关信息，设计系统边界并产出初步执行计划。
  3. 任务完成后，会自动再次触发同步，将生成的计划文件输出至 `uploads/plan/`。

---

### 4. 人工审核：看计划，改计划

当制定计划命令运行成功后，您可以在本地 `uploads/plan/`（或工作区 `workspace/plan/`）下看到以下两个输出文件：
* `execution_plan.md` (执行计划)
* `todo_list.md` (待完善清单)

**如何进行修改与交互：**
* **补全数据缺口**：若 `todo_list.md` 中列出了某些缺失或需要确认的工艺参数，您可以在 `todo_list.md` 中的 `✍️ 用户填写内容区`（或在 `uploads/user_data/plan.md` 里）填写您的反馈和具体数值。
* **微调边界与分配**：若您对系统边界、工艺过程划分、背景数据映射有异议，可以直接在 `uploads/plan/execution_plan.md` 中进行手动微调。

---

### 5. 调用修改计划指令进行迭代

如果您对计划或待完善清单做出了修改，需要通知智能体在此基础上进行增量更新：

* **命令**：
  ```bash
  opencode run --command revise-plan 
  ```
* **执行逻辑**：
  1. 在执行前，同步脚本会将您在 `uploads/plan/` 下做出的文件修改（包括对 `todo_list.md` 用户答复区的填写）同步回工作区。
  2. `plan-maker` 智能体读取现有的 `execution_plan.md` 和带有用户反馈的 `todo_list.md`。
  3. 智能体以**增量更新**的形式修正执行计划，并自动更新 `todo_list.md` 中的标记，最后将更新后的文件同步回 `uploads/plan/`。

---

### 6. 调用 LCI 指令设计清单并导入 openLCA

当您确认执行计划已完善、不需要进一步修改后，可以下达清单设计与导入指令：

* **命令**：
  ```bash
  opencode run --command design-lci 
  ```
* **执行逻辑**：
  1. 命令开始前执行同步，以确保工作区使用的是最新的执行计划。
  2. `LCI-designer` 智能体读取 `workspace/plan/execution_plan.md`，从 RAG 和 openLCA 数据库检索背景流和 UUID 映射。
  3. 智能体自动设计出对应的 Flows、Processes 和 Product Systems JSON 数据，并将其输出在 `workspace/LCI/` 中，同时生成一份人类可读的映射报告 `human_readable_mapping.md`。
  4. 数据自动经过质检模块 `eval-executor` 的自我校验。
  5. 校验通过后，自动调用 IPC 接口将生成的 JSON 实体批量导入到 openLCA 桌面客户端的活动数据库中。
  6. 任务结束后，同步机制会将生成的 JSON 文件及报告同步至 `uploads/LCI/`。

---

## ⚡ 实用辅助指令

如果您想单独手动触发同步，或者进行目录清理，可以使用以下命令：

### 手动触发文件同步
若只是想查看同步状态，或者在不启动 Agent 时进行手动双向同步，可直接运行：
```bash
uv run python scripts/file_sync/main.py
```

### 清理工作目录与上传目录
当需要重置项目、清理生成的计划与 LCI 产物时，可以运行：
```bash
uv run python scripts/initialization/main.py --only clean
```
> [!WARNING]
> 该命令会清除工作空间及 uploads 中的生成文件，运行前请务必确认已备份重要数据。

