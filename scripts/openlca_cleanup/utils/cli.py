# -*- coding: utf-8 -*-

import argparse
from pathlib import Path


def add_arguments(parser: argparse.ArgumentParser) -> argparse.ArgumentParser:
    parser.add_argument(
        "--project",
        "-P",
        default=Path.cwd().name or "auto_LCA_project",
        help="openLCA project category to clean up. Defaults to the current working directory name.",
    )
    parser.add_argument(
        "--host",
        "-H",
        default="127.0.0.1",
        help="openLCA IPC Server host. Default: 127.0.0.1.",
    )
    parser.add_argument(
        "--port",
        "-p",
        type=int,
        default=8080,
        help="openLCA IPC Server port. Default: 8080.",
    )
    parser.add_argument(
        "--include-supporting",
        action="store_true",
        help="Also delete FlowProperty and UnitGroup entities under the same category. By default only ProductSystem, Process, and Flow are deleted.",
    )
    parser.add_argument(
        "--yes",
        action="store_true",
        help="Confirm deletion. Without this flag, the script only previews matching entities.",
    )
    return parser
