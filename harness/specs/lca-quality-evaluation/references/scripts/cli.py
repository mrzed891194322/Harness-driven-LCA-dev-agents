from __future__ import annotations

import argparse
import sys
from pathlib import Path

from contract import QualityContractError, load_and_validate, render_markdown


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Validate an LCA quality score JSON and render its Markdown report."
    )
    parser.add_argument("--input", required=True, type=Path, help="Score JSON path")
    parser.add_argument("--output", type=Path, help="New Markdown output path")
    parser.add_argument(
        "--validate-only", action="store_true", help="Validate without rendering"
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.validate_only == (args.output is not None):
        print("Choose exactly one of --validate-only or --output", file=sys.stderr)
        return 2
    try:
        data, rubric = load_and_validate(args.input)
        if args.output is not None:
            if args.output.exists():
                raise QualityContractError(f"Refusing to overwrite {args.output}")
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(render_markdown(data, rubric), encoding="utf-8")
    except QualityContractError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
