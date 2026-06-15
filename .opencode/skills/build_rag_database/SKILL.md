---
name: build-rag-database
description: Use this skill to convert files in the input/ directory to markdown using markitdown, and then store their embeddings in a Chroma RAG database in src/knowledge/.
---

# Build RAG Database

This skill converts raw files into markdown format and stores their embeddings in a vector database.

## When to Use

Use this skill when the user asks to "build the RAG database", "process the input files", or convert the `input/` directory into a vector database in `src/knowledge/`.

## Prerequisites

- Ensure the python packages are installed (`markitdown`, `chromadb`, `openai`, `langchain`, `python-dotenv`).
- Ensure `.env` is configured with `EMBEDDING_API_KEY`, `EMBEDDING_API_URL`, and `EMBEDDING_MODEL`.

## Execution

Run the Python script provided in the `assets` folder:

```bash
uv run python .opencode/skills/build_rag_database/assets/build_rag.py
```
