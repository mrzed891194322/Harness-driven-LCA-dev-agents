import json
import sys
from pathlib import Path
from typing import Any

from mcp.server import MCPServer

QUERY_ROOT = Path(__file__).resolve().parent
PROJECT_ROOT = QUERY_ROOT.parents[2]
if str(QUERY_ROOT) not in sys.path:
    sys.path.insert(0, str(QUERY_ROOT))

from utils.embedding import create_embedding_function, load_embedding_config
from utils.query import DEFAULT_MAX_DISTANCE, embed_query, retrieve_rag_chunks, validate_query


LIBRARY_DIRS = {
    "standards": "harness/knowledge/rag_db/standards",
    "openlca_manual": "harness/knowledge/rag_db/openlca_manual",
    "input": "harness/knowledge/rag_db/input",
    "data": "harness/knowledge/rag_db/data",
}

mcp = MCPServer("LCA-RAG-Helper")


def _normalize_libraries(libraries: list[str] | None) -> list[str]:
    selected = libraries or ["standards"]
    normalized: list[str] = []
    for library in selected:
        if library not in LIBRARY_DIRS:
            available = ", ".join(sorted(LIBRARY_DIRS))
            raise ValueError(f"Unknown RAG library {library!r}; available: {available}")
        if library not in normalized:
            normalized.append(library)
    if not normalized:
        raise ValueError("At least one RAG library must be selected")
    return normalized


def _library_path(library: str) -> Path:
    root = (PROJECT_ROOT / "harness/knowledge/rag_db").resolve()
    path = (PROJECT_ROOT / LIBRARY_DIRS[library]).resolve()
    try:
        path.relative_to(root)
    except ValueError as exc:
        raise RuntimeError(f"RAG library path escapes the allowed root: {path}") from exc
    return path


@mcp.tool(structured_output=True)
def list_rag_libraries() -> dict[str, Any]:
    """List whitelisted RAG libraries without creating or opening databases."""
    libraries: list[dict[str, Any]] = []
    for name, relative_path in LIBRARY_DIRS.items():
        path = _library_path(name)
        manifest_path = path / "build_manifest.json"
        manifest: dict[str, Any] = {}
        if manifest_path.is_file():
            try:
                parsed = json.loads(manifest_path.read_text(encoding="utf-8"))
                if isinstance(parsed, dict):
                    manifest = parsed
            except (OSError, json.JSONDecodeError):
                manifest = {}
        libraries.append(
            {
                "name": name,
                "path": relative_path,
                "available": (path / "chroma.sqlite3").is_file(),
                "status": manifest.get("status", "legacy" if path.exists() else "missing"),
                "chunks": (manifest.get("totals") or {}).get("chunks"),
                "embedding_model": manifest.get("embedding_model"),
                "build_id": manifest.get("build_id"),
            }
        )
    return {"ok": True, "libraries": libraries}


@mcp.tool(structured_output=True)
def query_rag(
    query: str,
    libraries: list[str] | None = None,
    n_results: int = 5,
    max_distance: float = DEFAULT_MAX_DISTANCE,
) -> dict[str, Any]:
    """Query one or more whitelisted RAG libraries and return traceable chunks."""
    selected = _normalize_libraries(libraries)
    validate_query(query, n_results, max_distance)
    selected_paths = {library: _library_path(library) for library in selected}
    for library, path in selected_paths.items():
        if not (path / "chroma.sqlite3").is_file():
            raise FileNotFoundError(
                f"RAG library {library!r} is not built; run project initialization"
            )
    config = load_embedding_config()
    embedding_function = create_embedding_function(config)
    vector = embed_query(embedding_function, query)

    combined: list[dict[str, Any]] = []
    for library in selected:
        results = retrieve_rag_chunks(
            selected_paths[library],
            query,
            n_results,
            max_distance=max_distance,
            embedding_config=config,
            embedding_function=embedding_function,
            query_embedding=vector,
        )
        for result in results:
            result["library"] = library
            combined.append(result)

    combined.sort(
        key=lambda item: (
            float("inf") if item.get("distance") is None else float(item["distance"]),
            str(item.get("source", "")),
            int(item.get("chunk_index", 0)),
        )
    )
    combined = combined[:n_results]
    return {
        "ok": True,
        "query": query,
        "libraries": selected,
        "max_distance": max_distance,
        "results": combined,
        "message": (
            f"Found {len(combined)} reliable result(s)."
            if combined
            else "No reliable results found within the distance threshold."
        ),
    }


if __name__ == "__main__":
    mcp.run()
