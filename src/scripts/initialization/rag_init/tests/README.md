# RAG build tests

Run the offline test suite from the repository root:

    uv run python -m unittest discover -s src/scripts/initialization/rag_init/tests -v

The tests use a deterministic local embedding function. They do not call the configured embedding API.
