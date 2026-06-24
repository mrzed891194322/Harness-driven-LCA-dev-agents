---
description: 初始化 RAG 数据库，将指定目录下的文档转换并写入 RAG 数据库
agent: subagents/tools/doc-handler
---

请严格按照以下步骤执行任务，完成后直接停止，不要运行任何其他工作流或后续技能：

1. **清理 `src/knowledge` 目录**：
   在运行 RAG 数据库转化之前，先清除 `src/knowledge` 中除 `README.md` 外的所有文件和文件夹。
   运行以下命令：
   ```bash
   uv run python -c "import shutil; from pathlib import Path; d = Path('src/knowledge'); [shutil.rmtree(p) if p.is_dir() else p.unlink() for p in d.iterdir() if p.name != 'README.md']"
   ```

2. **读取并遵循 `control-rag-database` 映射规则**：
   加载 `control-rag-database` 技能中的 `assets/mapping-rules.md` 以获取原始目录与 RAG 目标子目录的映射关系。

3. **利用 `control-rag-database` 技能执行转化任务**：
   对于在 `control-rag-database` 中查阅到的所有映射关系，使用 `control-rag-database` 技能运行转化以生成向量数据库。运行代码示例如下：
   ```bash
   uv run python .opencode/skills/control-rag-database/scripts/build_rag/main.py --input-dir <映射中的输入目录> --output-dir <映射中的输出目录>
   ```   

4. **立即停止**：
   在执行完上述步骤后，立即停止，不要进行任何多余的工作（例如：不要调用 `main-workflow`  等任何其他技能，不要创建任何额外的待办任务或输出总结文件，直接结束并向用户报告任务已完成）。如果是 `major-orchestrator` agent读到这段话，请执行“触发情形3”，不执行任何工作流并立即终止工作，结束当前会话。
