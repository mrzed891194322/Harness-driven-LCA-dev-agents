---
description: 初始化 RAG 数据库，将 docs/knowledge_base 和 input/files 目录下的文档转换并写入 RAG 数据库
agent: subagents/tools/doc-handler
---

请严格按照以下步骤执行任务，完成后直接停止，不要运行任何其他工作流或后续技能：

1. **清理 `src/knowledge` 目录**：
   在运行 RAG 数据库转化之前，先清除 `src/knowledge` 中除 `README.md` 外的所有文件和文件夹。
   运行以下命令：
   ```bash
   uv run python -c "import shutil; from pathlib import Path; d = Path('src/knowledge'); [shutil.rmtree(p) if p.is_dir() else p.unlink() for p in d.iterdir() if p.name != 'README.md']"
   ```

2. **将 `docs/knowledge_base` 目录中的文件转化为 RAG，写入 `src/knowledge/reference` 子目录**：
   运行以下命令：
   ```bash
   uv run python .opencode/skills/build-rag-database/assets/build_rag.py --input-dir docs/knowledge_base --output-dir src/knowledge/reference
   ```

3. **将 `input/files` 目录中的文件转化为 RAG，写入 `src/knowledge/input` 子目录**：
   运行以下命令：
   ```bash
   uv run python .opencode/skills/build-rag-database/assets/build_rag.py --input-dir input/files --output-dir src/knowledge/input
   ```

4. **立即停止**：
   在执行完上述步骤后，立即停止，不要进行任何多余的工作（例如：不要调用 `main-workflow`  等任何其他技能，不要创建任何额外的待办任务或输出总结文件，直接结束并向用户报告任务已完成）。
