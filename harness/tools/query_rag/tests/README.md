# query_rag tests

Run the offline test suite from the repository root:

    uv run python -m unittest discover -s harness/tools/query_rag/tests -v

The tests validate schema, model and dimension checks, distance filtering, empty libraries and traceable metadata without network access.
