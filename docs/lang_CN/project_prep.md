# 🚀 Multi-Agent LCA Orchestrator 项目准备说明

本文档说明在运行 LCA 工作流前需要准备的输入资料与环境。

---

## 🛠️ 项目准备步骤

### 1. 准备 `workspace/inputs` 下的文件

在开始建模前，先整理以下内容：

1. **放置输入资料**
   * 原始参考文档：`workspace/inputs/references/file/`
   * 结构化参考数据：`workspace/inputs/references/data/`
   * 资料同步后会进入 `harness/knowledge/inputs/user_ref/file/` 与 `harness/knowledge/inputs/user_ref/data/`。
   * 标准与方法可放 `harness/knowledge/inputs/static_ref/` 相关目录。

2. **准备计划文件**
   * 使用模板 [src/GUI/ui/assets/template/plan.md](src/GUI/ui/assets/template/plan.md) 生成/编辑 `workspace/inputs/plan.md`。
   * 关键内容包括：
     * 研究主体
     * 功能单位
     * 系统边界
     * 背景数据库与 LCIA 方法

---

### 2. 打开 openLCA 与 IPC

确保 openLCA 已启动，并在客户端中开启 IPC Server（默认端口 `8080`）。

> 相关说明：`harness/rules/openlca-operation/README.md` 与 `harness/tools/control_openlca/README.md`

![openLCA IPC Service](../assets/images/project_prep/openlca-ipc.png)

---

### 3. 构建 RAG 数据库

执行：
```bash
uv run python src/scripts/initialization/main.py --only rag
```

### 底层逻辑

1. 读取 `src/scripts/initialization/rag_init/mapping_rules.py`。
2. 分块、向量化并写入 ChromaDB。
3. 校验成功后原子替换活动库；失败则保留旧库。

更多说明见：[RAG 数据库使用指南](rag_guide.md)。
