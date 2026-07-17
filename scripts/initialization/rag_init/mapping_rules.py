"""
RAG knowledge-library mapping rules.

Each mapping has a stable library name, one source directory, and one Chroma
output directory. Dynamic upload libraries exclude their placeholder README
and may be published as valid empty databases.
"""

DEFAULT_MAPPING = [
    {
        "library": "standards",
        "input": "harness/knowledge/inputs/static_ref/standards",
        "output": "harness/knowledge/rag_db/standards",
    },
    {
        "library": "openlca_manual",
        "input": "harness/knowledge/inputs/static_ref/openlca_manual",
        "output": "harness/knowledge/rag_db/openlca_manual",
    },
    {
        "library": "input",
        "input": "harness/knowledge/inputs/user_file",
        "output": "harness/knowledge/rag_db/input",
        "exclude_globs": ["README.md", "**/README.md"],
        "allow_empty": True,
    },
    {
        "library": "data",
        "input": "harness/knowledge/inputs/user_data",
        "output": "harness/knowledge/rag_db/data",
        "exclude_globs": ["README.md", "**/README.md"],
        "allow_empty": True,
    },
]
