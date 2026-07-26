#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
openLCA project entity cleanup entry point.

By default, this script matches the current working directory name as the
openLCA category and previews or deletes ProductSystem, Process, and Flow
entities created under that category.

uv run python src/scripts/openlca_cleanup/main.py --project "202606-Multi-agent-LCA" --yes
"""

import argparse
import sys
from pathlib import Path

try:
    import olca_schema
except ImportError:
    print("Error: Required package 'olca-schema' is not installed.")
    sys.exit(1)


SCRIPT_DIR = Path(__file__).parent
sys.path.append(str(SCRIPT_DIR))

from utils.cleanup import collect_entities, delete_entities, print_entities
from utils.cli import add_arguments
from utils.encoding import setup_io_encoding
from utils.openlca import connect_ipc


def main():
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
