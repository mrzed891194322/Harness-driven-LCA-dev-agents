---
name: query-rag-database
description: Use this skill to query the RAG database stored in src/knowledge/ using a query string to retrieve relevant information from the embedded documents.
---

# Query RAG Database

This skill searches the local Chroma vector database for information relevant to the provided query.

## When to Use

Use this skill when the user asks questions about the contents of their processed documents or explicitly asks to "search the RAG database", "query the knowledge base", etc.

## Prerequisites

- The database must have been built first using the `build-rag-database` skill.
- `.env` must be configured with `EMBEDDING_API_KEY`, `EMBEDDING_API_URL`, and `EMBEDDING_MODEL`.

## Execution

Run the Python script provided in the `assets` folder, passing the query string as an argument:

```bash
uv run python .opencode/skills/query_rag_database/assets/query_rag.py "Your search query here"
```
