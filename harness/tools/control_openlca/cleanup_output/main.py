import argparse
import sys
from pathlib import Path

# Add control_openlca to sys.path for shared utils.
sys.path.append(str(Path(__file__).parent.parent))
# Add this tool directory to sys.path for private_utils.
sys.path.append(str(Path(__file__).parent))

try:
    import olca_schema
except ImportError:
    print("Error: Required package 'olca-schema' is not installed.")
    sys.exit(1)

from utils.connection import connect_ipc

from private_utils.cleanup import collect_entities, delete_entities, print_entities
from private_utils.cli import add_arguments


def main():
    from utils.encoding import setup_io_encoding
    setup_io_encoding()

    parser = argparse.ArgumentParser(
        description="Delete ProductSystem, Process, and Flow entities created under an openLCA project category."
    )
    add_arguments(parser)
    args = parser.parse_args()

    project_name = args.project.strip()
    if not project_name:
        print("[ERROR] Project name cannot be empty.")
        sys.exit(1)

    model_types = [
        olca_schema.ProductSystem,
        olca_schema.Process,
        olca_schema.Flow,
    ]
    if args.include_supporting:
        model_types.extend([olca_schema.FlowProperty, olca_schema.UnitGroup])

    print(f"Target project category: {project_name}")
    print("Target entity types: " + ", ".join(model_type.__name__ for model_type in model_types))

    client = connect_ipc(args.host, args.port, olca_schema.ProductSystem)
    entities = collect_entities(client, project_name, model_types)

    if not entities:
        print("No matching entities found. Nothing to delete.")
        return

    print(f"Found {len(entities)} entities to clean up:")
    print_entities(entities)

    if not args.yes:
        print("\nPreview mode only. No entities were deleted. Add --yes to execute deletion.")
        return

    deleted_count = delete_entities(client, entities, model_types)
    print(f"\nCleanup completed. Deleted {deleted_count}/{len(entities)} entities.")


if __name__ == "__main__":
    main()
