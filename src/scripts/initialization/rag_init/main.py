"""
Batch entry point for atomically rebuilding mapped RAG knowledge libraries.
"""

import argparse
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
INIT_DIR = SCRIPT_DIR.parent
for path in (str(SCRIPT_DIR), str(INIT_DIR)):
    if path not in sys.path:
        sys.path.insert(0, path)

from mapping_rules import DEFAULT_MAPPING
from private_utils.builder import build_rag
from private_utils.embedding import load_embedding_config
from private_utils.models import BuildResult
from utils.encoding import setup_io_encoding


def _validate_mapping(mapping: list[dict[str, object]]) -> None:
    outputs: set[str] = set()
    libraries: set[str] = set()
    for index, item in enumerate(mapping):
        input_path = item.get("input")
        output_path = item.get("output")
        library = item.get("library", f"mapping-{index}")
        if not isinstance(input_path, str) or not input_path.strip():
            raise ValueError(f"Mapping item {index} has an invalid input path")
        if not isinstance(output_path, str) or not output_path.strip():
            raise ValueError(f"Mapping item {index} has an invalid output path")
        if not isinstance(library, str) or not library.strip():
            raise ValueError(f"Mapping item {index} has an invalid library name")
        if output_path in outputs:
            raise ValueError(f"Duplicate RAG output path: {output_path}")
        if library in libraries:
            raise ValueError(f"Duplicate RAG library name: {library}")
        outputs.add(output_path)
        libraries.add(library)


def build_all_rag(
    project_root: Path,
    mapping: list[dict[str, object]],
    clean: bool = False,
) -> list[BuildResult]:
    """Build every mapping and fail the caller if any live library was not replaced."""
    _validate_mapping(mapping)
    config = load_embedding_config()
    print(f"Project root: {project_root}")
    print(f"Embedding model: {config.model}")
    print(f"Number of mapping entries: {len(mapping)}")
    if clean:
        print(
            "Note: --clean is retained for compatibility; staged builds replace "
            "each database only after validation."
        )

    results: list[BuildResult] = []
    failed_libraries: list[str] = []
    for index, item in enumerate(mapping):
        library = str(item.get("library", f"mapping-{index}"))
        input_dir = project_root / str(item["input"])
        output_dir = project_root / str(item["output"])
        raw_excludes = item.get("exclude_globs", [])
        if not isinstance(raw_excludes, (list, tuple)) or not all(
            isinstance(pattern, str) for pattern in raw_excludes
        ):
            raise ValueError(f"Mapping {library} exclude_globs must be a list of strings")

        print(f"\n--- Building [{library}]: {input_dir} -> {output_dir} ---")
        result = build_rag(
            input_dir,
            output_dir,
            project_root=project_root,
            exclude_globs=tuple(raw_excludes),
            allow_empty=bool(item.get("allow_empty", False)),
            embedding_config=config,
        )
        results.append(result)
        print(f"Build report: {result.manifest_path}")
        if result.success:
            print(
                f"Published [{library}] with {result.processed_files} file(s) "
                f"and {result.total_chunks} chunk(s)."
            )
        else:
            failed_libraries.append(library)
            print(f"[Error] [{library}] failed; the previous live database was preserved.")

    if failed_libraries:
        names = ", ".join(failed_libraries)
        raise RuntimeError(f"RAG build failed for {len(failed_libraries)} library/libraries: {names}")

    print("\nAll RAG mappings were atomically published.")
    return results


def main() -> None:
    setup_io_encoding()
    parser = argparse.ArgumentParser(description="Atomically build mapped RAG knowledge libraries")
    parser.add_argument(
        "--project-root",
        type=str,
        default=None,
        help="Project root; defaults to the repository containing this script.",
    )
    parser.add_argument(
        "--clean",
        action="store_true",
        help="Compatibility flag; staged builds always replace a library after success.",
    )
    args = parser.parse_args()
    project_root = (
        Path(args.project_root).resolve()
        if args.project_root
        else next(
            parent
            for parent in Path(__file__).resolve().parents
            if (parent / "pyproject.toml").is_file()
        )
    )
    build_all_rag(project_root, DEFAULT_MAPPING, clean=args.clean)


if __name__ == "__main__":
    main()
