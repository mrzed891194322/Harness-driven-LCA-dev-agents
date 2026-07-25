# 🛠️ 手动调试与文件同步机制指南

当无需 GUI 时，可通过命令行直接驱动工作流。

---

## 1. 准备输入文件

将文件放入 `workspace/inputs`：

- 参考文档：`workspace/inputs/references/file/`
- 结构化数据：`workspace/inputs/references/data/`
- 计划文件：`workspace/inputs/plan.md`

---

## 2. 初始化前置

执行初始化脚本（默认会清理工作目录、同步 inputs 与知识库映射并检查 openLCA）：

```bash
uv run python src/scripts/initialization/main.py
```

只构建 RAG 时可指定：

```bash
uv run python src/scripts/initialization/main.py --only rag
```

---

## 3. 启动阶段任务





```bash
opencode run --command whole-lca
```

该命令基于 `workspace/inputs/plan.md` 作为唯一计划输入，完成 plan 读取、LCI 生成、预检、导入、读回与计算，并在固定路径保留证据：

- `workspace/memory/`
- `workspace/outputs/LCI/`
- `workspace/outputs/reports/`

---

## 4. 手动同步与清理




```bash
uv run python src/scripts/clean_dir/main.py -y
```

> 注意：清理会删除生成产物，请确认后执行。
