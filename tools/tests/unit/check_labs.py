"""Read-only development smoke check; not the public CyberLab CLI."""

import argparse
from pathlib import Path
import sys

from cyberlab.lab import LabError, get_lab, list_labs


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--catalog", type=Path, required=True,
        help="Explicit directory of Lab definitions to validate read-only; no default catalog"
    )
    parser.add_argument("--lab", help="Inspect a Lab by metadata ID")
    arguments = parser.parse_args()

    try:
        labs = list_labs(arguments.catalog)
        selected = get_lab(arguments.catalog, arguments.lab) if arguments.lab else None
    except LabError as error:
        print(f"FAIL: {error}", file=sys.stderr)
        return 1

    print(f"PASS: {len(labs)} valid lab(s)")
    for lab in labs:
        print(
            f"  {lab.metadata.id} | {lab.metadata.name!r} | v{lab.metadata.version} "
            f"| {len(lab.nodes)} node(s) | {len(lab.networks)} network(s)"
        )
    if selected is not None:
        print(f"PASS: found {selected.metadata.id}")
        for node in selected.nodes:
            print(f"  {node.id} -> {', '.join(node.networks) or '(disconnected)'}")
    print("Read-only engine check. No containers or networks were created.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
