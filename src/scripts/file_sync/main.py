#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
File Synchronization Entry Script

Description:
    Synchronizes workspace reference inputs with the harness knowledge sources.
    Supports authoritative one-way synchronization and the legacy mtime-based
    bidirectional synchronization mode. Direction names remain compatible with
    the previous CLI.
"""

import argparse
import sys
from pathlib import Path

# Add the script parent directory to sys.path to enable local imports
SCRIPT_DIR = Path(__file__).parent
sys.path.append(str(SCRIPT_DIR))

from config import SYNC_TARGETS, PROJECT_ROOT
from utils.sync import SYNC_DIRECTIONS, sync_directories


def parse_args(argv=None):
    parser = argparse.ArgumentParser(
        description="Synchronize workspace reference inputs and knowledge sources."
    )
    parser.add_argument(
        "--direction",
        choices=SYNC_DIRECTIONS,
        default="bidirectional",
        help=(
            "Synchronization direction: upload-to-work, work-to-upload, "
            "or bidirectional (default)."
        ),
    )
    return parser.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)

    print("=" * 60)
    print("File Sync Started")
    print(f"Direction: {args.direction}")
    print("=" * 60)

    total_stats = {
        "copied_a_to_b": 0,
        "copied_b_to_a": 0,
        "in_sync": 0,
        "errors": 0,
        "ignored": 0,
    }

    for target in SYNC_TARGETS:
        name = target["name"]
        knowledge_dir = target["knowledge_dir"]
        input_dir = target["input_dir"]

        print(f"\nSyncing target [{name}]:")
        print(f"  knowledge_dir: {knowledge_dir.relative_to(PROJECT_ROOT)}")
        print(f"  input_dir:     {input_dir.relative_to(PROJECT_ROOT)}")
        
        stats = sync_directories(knowledge_dir, input_dir, direction=args.direction)
        
        for k in total_stats:
            total_stats[k] += stats.get(k, 0)

    print("\n" + "=" * 60)
    print("Synchronization Completed! Total Summary:")
    print(f"- Synced knowledge -> inputs: {total_stats['copied_a_to_b']} file(s)")
    print(f"- Synced inputs -> knowledge: {total_stats['copied_b_to_a']} file(s)")
    print(f"- Already in sync: {total_stats['in_sync']} file(s)")
    print(f"- Ignored (readme): {total_stats['ignored']} file(s)")
    if total_stats["errors"] > 0:
        print(f"- Errors encountered: {total_stats['errors']} file(s)")
    print("=" * 60)


if __name__ == "__main__":
    main()
