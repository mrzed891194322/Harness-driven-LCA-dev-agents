from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[5]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from harness.tools.control_openlca.utils.workflow import validate_lci_directory


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate the Whole-LCA entity-per-file LCI contract."
    )
    parser.add_argument(
        "lci_dir",
        nargs="?",
        default="workspace/outputs/LCI",
    )
    args = parser.parse_args()
    path = Path(args.lci_dir)
    if not path.is_absolute():
        path = PROJECT_ROOT / path
    result = validate_lci_directory(path)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
